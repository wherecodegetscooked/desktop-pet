"""Background polling of media playback state.

Two signals the pet's app-awareness needs but can't get cheaply on the main
thread:

* ``music_playing`` — whether Spotify or Apple Music is actually *playing*
  (not merely running). Read with ``osascript`` player-state queries, which
  cost ~100 ms each — enough to hitch the 60 fps loop — so they run on a daemon
  thread and the loop just reads the latest cached boolean.

* ``audio_active`` — whether any process is currently driving the default
  output device, via CoreAudio's ``kAudioDevicePropertyDeviceIsRunningSomewhere``.
  This is a permission-free "sound is playing right now" flag, used to tell a
  playing video tab from a paused one.

The ``osascript`` queries guard with ``application "X" is running`` so they
never launch a closed app; the first real query for a running app triggers a
one-time macOS Automation permission prompt (denied -> treated as not playing).
"""

import ctypes
import ctypes.util
import subprocess
import threading
import time


def _fourcc(code):
    return (ord(code[0]) << 24) | (ord(code[1]) << 16) | (ord(code[2]) << 8) | ord(code[3])


_DEFAULT_OUTPUT_DEVICE = _fourcc("dOut")        # kAudioHardwarePropertyDefaultOutputDevice
_DEVICE_IS_RUNNING = _fourcc("gone")            # kAudioDevicePropertyDeviceIsRunningSomewhere
_SCOPE_GLOBAL = _fourcc("glob")                 # kAudioObjectPropertyScopeGlobal
_SYSTEM_OBJECT = 1                              # kAudioObjectSystemObject

# AppleScript application names whose player state we poll, in priority order.
_MUSIC_APPS = ("Spotify", "Music")

_PLAYER_STATE_SCRIPT = (
    'if application "{app}" is running then '
    'tell application "{app}" to return player state as text'
)


class _PropertyAddress(ctypes.Structure):
    _fields_ = [
        ("selector", ctypes.c_uint32),
        ("scope", ctypes.c_uint32),
        ("element", ctypes.c_uint32),
    ]


class PlaybackMonitor:
    """Polls media playback on a daemon thread; expose the latest as booleans."""

    def __init__(self, interval=1.0, audio_grace=2.5):
        self._interval = interval
        # CoreAudio's "device running" flag can briefly drop mid-playback, so we
        # hold audio "active" for a grace window after the last positive reading
        # to keep the popcorn from flickering off while a video keeps playing.
        self._audio_grace = audio_grace
        self._lock = threading.Lock()
        self._music_playing = False
        self._audio_last_true = float("-inf")
        self._ca = self._load_core_audio()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _load_core_audio(self):
        try:
            ca = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreAudio"))
            ca.AudioObjectGetPropertyData.restype = ctypes.c_int
            ca.AudioObjectGetPropertyData.argtypes = [
                ctypes.c_uint32,
                ctypes.POINTER(_PropertyAddress),
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_void_p,
            ]
            return ca
        except (OSError, AttributeError):
            return None

    @property
    def music_playing(self):
        with self._lock:
            return self._music_playing

    @property
    def audio_active(self):
        with self._lock:
            return (time.monotonic() - self._audio_last_true) < self._audio_grace

    def stop(self):
        self._running = False

    # -- polling -----------------------------------------------------------

    def _run(self):
        while self._running:
            music = self._read_music_playing()
            audio = self._read_audio_active()
            now = time.monotonic()
            with self._lock:
                self._music_playing = music
                if audio:
                    self._audio_last_true = now
            time.sleep(self._interval)

    def _read_music_playing(self):
        for app in _MUSIC_APPS:
            if self._osascript(_PLAYER_STATE_SCRIPT.format(app=app)) == "playing":
                return True
        return False

    def _osascript(self, script):
        try:
            result = subprocess.run(
                ["/usr/bin/osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return result.stdout.strip().lower()
        except (OSError, subprocess.SubprocessError):
            return ""

    def _read_audio_active(self):
        if self._ca is None:
            return False
        device = self._get_uint32(_SYSTEM_OBJECT, _DEFAULT_OUTPUT_DEVICE)
        if not device:
            return False
        return bool(self._get_uint32(device, _DEVICE_IS_RUNNING))

    def _get_uint32(self, object_id, selector):
        """Read a single UInt32 CoreAudio property; 0 on any failure."""
        address = _PropertyAddress(selector, _SCOPE_GLOBAL, 0)
        value = ctypes.c_uint32(0)
        size = ctypes.c_uint32(ctypes.sizeof(value))
        status = self._ca.AudioObjectGetPropertyData(
            object_id, ctypes.byref(address), 0, None, ctypes.byref(size), ctypes.byref(value)
        )
        return value.value if status == 0 else 0
