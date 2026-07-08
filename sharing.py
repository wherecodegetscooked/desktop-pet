"""Best-effort-Erkennung eines laufenden Bildschirm-Teilens (Zoom/Teams/Meet).

Es gibt KEINE zuverlaessige, oeffentliche macOS-API fuer "wird mein Bildschirm
gerade geteilt". Dieser Monitor pollt — nach demselben Muster wie
``playback.PlaybackMonitor`` — auf einem Daemon-Thread die On-Screen-Fensterliste
(``CGWindowListCopyWindowInfo``) und sucht nach den verraeterischen
Schwebe-Toolbars/Baendern, die die Call-Apps waehrend des Teilens zeigen
("is sharing your screen", "Stop sharing", "Bildschirm wird geteilt", ...).

Das ist eine Heuristik, keine Garantie: Fenstertitel brauchen die
Screen-Recording-Berechtigung, variieren je nach App-Version und UI-Sprache, und
manche Apps legen den Freigabe-Hinweis gar nicht als Fenstertitel ab. Darum
ergaenzt dieser Monitor nur den manuellen Menue-Toggle "Bildschirm-Teilen-Modus"
— der bleibt der verlaessliche Weg, die Pets vor dem Teilen auszublenden.

Es werden ausschliesslich Fenster-*Titel* gelesen (kein Screen-Capture), also
wird die System-Berechtigungs-Nachfrage nie neu ausgeloest; ohne die Berechtigung
liefern die Titel schlicht nichts und die Heuristik meldet dauerhaft "nein".
"""

import ctypes
import ctypes.util
import threading
import time

from config import WINDOW_LIST_EXCLUDE_DESKTOP, WINDOW_LIST_ON_SCREEN_ONLY

_UTF8 = 0x08000100          # kCFStringEncodingUTF8
_CFNUMBER_INT = 3           # kCFNumberSInt32Type
_NULL_WINDOW = 0            # kCGNullWindowID

# Titel-Phrasen (lowercase), die ziemlich eindeutig fuer ein aktives Teilen
# stehen. Bewusst spezifisch gehalten, um Fehlalarme zu vermeiden — ein blosses
# "screen sharing" waere zu breit. EN + DE abgedeckt.
_SHARE_PHRASES = (
    "is sharing your screen",
    "are sharing your screen",
    "you are screen sharing",
    "you're sharing your screen",
    "sharing your screen",
    "stop sharing",
    "stop share",
    "you are presenting",
    "bildschirm wird geteilt",
    "du teilst deinen bildschirm",
    "teilt den bildschirm",
    "bildschirmfreigabe",
    "freigabe beenden",
)


class ScreenShareMonitor:
    """Pollt die Fensterliste off-thread; meldet ``sharing`` als Boolean.

    Ist die noetige Berechtigung nicht erteilt oder CoreGraphics nicht ladbar,
    bleibt ``sharing`` dauerhaft False — der manuelle Toggle traegt dann allein.
    """

    def __init__(self, interval=1.5, grace=2.5):
        self._interval = interval
        # Die Freigabe-Toolbar kann kurz aus der Fensterliste fallen (z. B. beim
        # Umschalten des geteilten Fensters); wie beim Audio-Flag halten wir das
        # Signal ein paar Sekunden nach, damit die Pets nicht kurz aufblitzen.
        self._grace = grace
        self._lock = threading.Lock()
        self._last_true = float("-inf")
        self._running = True
        self._cf, self._cg = self._load_frameworks()
        self._keys = self._make_keys()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def sharing(self):
        with self._lock:
            return (time.monotonic() - self._last_true) < self._grace

    def stop(self):
        self._running = False

    # -- Setup -------------------------------------------------------------

    def _load_frameworks(self):
        try:
            cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
            cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        except OSError:
            return None, None

        cf.CFArrayGetCount.restype = ctypes.c_long
        cf.CFArrayGetCount.argtypes = [ctypes.c_void_p]
        cf.CFArrayGetValueAtIndex.restype = ctypes.c_void_p
        cf.CFArrayGetValueAtIndex.argtypes = [ctypes.c_void_p, ctypes.c_long]
        cf.CFDictionaryGetValue.restype = ctypes.c_void_p
        cf.CFDictionaryGetValue.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        cf.CFStringCreateWithCString.restype = ctypes.c_void_p
        cf.CFStringCreateWithCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32
        ]
        cf.CFStringGetCStringPtr.restype = ctypes.c_char_p
        cf.CFStringGetCStringPtr.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFStringGetCString.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32
        ]
        cf.CFNumberGetValue.restype = ctypes.c_bool
        cf.CFNumberGetValue.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p
        ]
        cf.CFRelease.argtypes = [ctypes.c_void_p]

        cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
        cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        return cf, cg

    def _make_keys(self):
        if self._cf is None:
            return {}
        return {
            name: self._cf.CFStringCreateWithCString(None, name.encode(), _UTF8)
            for name in ("kCGWindowName", "kCGWindowLayer")
        }

    # -- Polling -----------------------------------------------------------

    def _run(self):
        while self._running:
            if self._read_sharing():
                with self._lock:
                    self._last_true = time.monotonic()
            time.sleep(self._interval)

    def _read_sharing(self):
        if self._cg is None or not self._keys:
            return False
        options = WINDOW_LIST_ON_SCREEN_ONLY | WINDOW_LIST_EXCLUDE_DESKTOP
        array = self._cg.CGWindowListCopyWindowInfo(options, _NULL_WINDOW)
        if not array:
            return False
        try:
            count = self._cf.CFArrayGetCount(array)
            for i in range(count):
                info = self._cf.CFArrayGetValueAtIndex(array, i)
                if not info:
                    continue
                # Nur normale Fenster-Ebenen; Schwebe-Toolbars der Call-Apps
                # liegen ueber Ebene 0, extrem hohe Ebenen (Menuebar etc.)
                # ueberspringen wir aber, um Rauschen zu sparen.
                layer = self._dict_int(info, "kCGWindowLayer")
                if layer is not None and layer > 25:
                    continue
                title = self._dict_str(info, "kCGWindowName")
                if not title:
                    continue
                low = title.lower()
                if any(phrase in low for phrase in _SHARE_PHRASES):
                    return True
            return False
        finally:
            self._cf.CFRelease(array)

    # -- CF-Helfer ---------------------------------------------------------

    def _dict_str(self, info, key):
        value = self._cf.CFDictionaryGetValue(info, self._keys[key])
        if not value:
            return ""
        ptr = self._cf.CFStringGetCStringPtr(value, _UTF8)
        if ptr is not None:
            return ptr.decode("utf-8", "replace")
        buf = ctypes.create_string_buffer(512)
        if self._cf.CFStringGetCString(value, buf, len(buf), _UTF8):
            return buf.value.decode("utf-8", "replace")
        return ""

    def _dict_int(self, info, key):
        value = self._cf.CFDictionaryGetValue(info, self._keys[key])
        if not value:
            return None
        out = ctypes.c_int32(0)
        if self._cf.CFNumberGetValue(value, _CFNUMBER_INT, ctypes.byref(out)):
            return out.value
        return None
