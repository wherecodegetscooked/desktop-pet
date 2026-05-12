import pygame
import sys
import random
import math
import os
import time

SCALE = 4
FPS = 60
SPRITE_W, SPRITE_H = 9, 10  # pixel canvas size before scale

class State:
    IDLE = "idle"
    WALK = "walk"
    RUN  = "run"
    JUMP = "jump"

PET_COLOR  = (232, 132, 92, 255)
EYE_COLOR  = (30,  20,  10, 255)
CLEAR      = (0, 0, 0, 0)

# ---------------------------------------------------------------------------
# Sprite drawing
# ---------------------------------------------------------------------------

def draw_pet_pixels(px, facing_right, anim_frame, state, blink):
    """Draw onto a 9×10 SRCALPHA surface (pixel art, no scaling)."""
    px.fill(CLEAR)
    C = PET_COLOR
    E = EYE_COLOR

    # Body 5×3 at (2,2)
    for bx in range(5):
        for by in range(3):
            px.set_at((2 + bx, 2 + by), C)

    # Arm stubs
    px.set_at((1, 3), C)
    px.set_at((7, 3), C)

    # 4 legs, x = 2,3,5,6
    leg_xs = [2, 3, 5, 6]
    if state in (State.WALK, State.RUN):
        speed = 3 if state == State.WALK else 2
        phase = (anim_frame // speed) % 2
    else:
        phase = 0  # both legs down when idle/jump

    for i, lx in enumerate(leg_xs):
        up = (state in (State.WALK, State.RUN)) and ((i % 2) == phase)
        if up:
            px.set_at((lx, 5), C)               # 1-pixel-up leg
        else:
            px.set_at((lx, 5), C)
            px.set_at((lx, 6), C)               # 2-pixel leg

    # Eyes (2 pixels on upper body row y=2)
    if not blink:
        if facing_right:
            px.set_at((6, 2), E)
            px.set_at((8, 2), E)
        else:
            px.set_at((2, 2), E)
            px.set_at((3, 2), E)


def make_sprite(facing_right, anim_frame, state, blink):
    small = pygame.Surface((SPRITE_W, SPRITE_H), pygame.SRCALPHA)
    draw_pet_pixels(small, facing_right, anim_frame, state, blink)
    big = pygame.transform.scale(small, (SPRITE_W * SCALE, SPRITE_H * SCALE))
    return big


# ---------------------------------------------------------------------------
# Pet entity
# ---------------------------------------------------------------------------

class Pet:
    def __init__(self, sw, sh):
        self.sw = sw
        self.sh = sh
        self.x = float(sw // 2)
        self.y = float(sh // 2)
        self.vx = 0.0
        self.vy = 0.0
        self.state = State.WALK
        self.facing_right = True
        self.frame = 0
        self.state_timer = 0
        self.blink = False
        self.blink_timer = random.randint(100, 250)
        # jump state
        self.jump_vy = 0.0
        self.ground_y = self.y
        self._pick_state()

    def _pick_state(self):
        r = random.random()
        if r < 0.45:
            self.state = State.WALK
            spd = random.uniform(0.8, 1.8)
            angle = random.uniform(-0.25, 0.25)
            d = 1 if random.random() > 0.5 else -1
            self.vx = d * spd * math.cos(angle)
            self.vy = spd * math.sin(angle)
            self.state_timer = random.randint(90, 300)
        elif r < 0.65:
            self.state = State.IDLE
            self.vx = 0.0
            self.vy = 0.0
            self.state_timer = random.randint(60, 180)
        elif r < 0.82:
            self.state = State.RUN
            spd = random.uniform(3.0, 5.5)
            d = 1 if random.random() > 0.5 else -1
            self.vx = d * spd
            self.vy = random.uniform(-0.4, 0.4)
            self.state_timer = random.randint(45, 120)
        else:
            self.state = State.JUMP
            self.ground_y = self.y
            self.jump_vy = random.uniform(-9, -5)
            self.vx = random.uniform(-2.5, 2.5)
            self.vy = 0.0
            self.state_timer = 600

    def update(self):
        self.frame += 1
        self.state_timer -= 1

        # Blink
        self.blink_timer -= 1
        if self.blink_timer <= 0:
            if self.blink:
                self.blink = False
                self.blink_timer = random.randint(120, 280)
            else:
                self.blink = True
                self.blink_timer = 5

        GRAVITY = 0.45
        W = SPRITE_W * SCALE
        H = SPRITE_H * SCALE

        if self.state == State.JUMP:
            self.jump_vy += GRAVITY
            self.y += self.jump_vy
            self.x += self.vx
            if self.y >= self.ground_y:
                self.y = self.ground_y
                self._pick_state()
        else:
            self.x += self.vx
            self.y += self.vy

        # Facing
        if self.vx > 0.1:
            self.facing_right = True
        elif self.vx < -0.1:
            self.facing_right = False

        # Bounce off edges
        if self.x < 0:
            self.x = 0
            self.vx = abs(self.vx)
        elif self.x + W > self.sw:
            self.x = self.sw - W
            self.vx = -abs(self.vx)

        if self.y < 0:
            self.y = 0
            if self.state == State.JUMP:
                self.jump_vy = abs(self.jump_vy) * 0.4
            else:
                self.vy = abs(self.vy)
        elif self.y + H > self.sh:
            self.y = self.sh - H
            if self.state == State.JUMP:
                self.y = self.sh - H
                self.jump_vy = 0
            else:
                self.vy = -abs(self.vy)

        # State transition
        if self.state_timer <= 0:
            self._pick_state()

    def draw(self, screen):
        sprite = make_sprite(self.facing_right, self.frame, self.state, self.blink)
        screen.blit(sprite, (int(self.x), int(self.y)))


# ---------------------------------------------------------------------------
# macOS window transparency via Objective-C runtime
# ---------------------------------------------------------------------------

def _objc_setup():
    import ctypes, ctypes.util
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
    objc.objc_getClass.restype   = ctypes.c_void_p
    objc.objc_getClass.argtypes  = [ctypes.c_char_p]
    objc.sel_registerName.restype  = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    # Leave objc_msgSend without fixed argtypes — we cast per call.
    return objc


def _msg(objc, obj, sel_name, *args, restype=None, argtypes=None):
    """Call obj_msgSend with a per-call cast so we never mutate shared state.

    By default the third argument (if present) is treated as a pointer (id).
    Pass `argtypes` to override (e.g. [c_bool] for setOpaque:, [c_long] for setLevel:).
    """
    import ctypes
    sel = objc.sel_registerName(sel_name.encode())
    if restype is None:
        restype = ctypes.c_void_p

    if not args:
        proto = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p)
        fn = ctypes.cast(objc.objc_msgSend, proto)
        return fn(obj, sel)

    if argtypes is None:
        # Default: each extra arg is a pointer
        argtypes = [ctypes.c_void_p] * len(args)

    proto = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)
    fn = ctypes.cast(objc.objc_msgSend, proto)
    converted = [t(a) if not isinstance(a, ctypes._SimpleCData) else a
                 for t, a in zip(argtypes, args)]
    return fn(obj, sel, *converted)


def _get_sdl_nswindow(objc):
    """Extract NSWindow pointer via SDL2's SDL_GetWindowWMInfo."""
    import ctypes, ctypes.util

    # Extract SDL_Window* from pygame capsule
    PyCapsule_GetPointer = ctypes.pythonapi.PyCapsule_GetPointer
    PyCapsule_GetPointer.restype  = ctypes.c_void_p
    PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
    wm = pygame.display.get_wm_info()
    sdl_win = PyCapsule_GetPointer(wm['window'], b'window')
    if not sdl_win:
        return None

    # SDL_SysWMinfo on macOS (SDL 2.x):
    # struct: version (3 bytes + 1 pad) + subsystem (Uint32) + union { cocoa { NSWindow* } ... }
    # Total offset to NSWindow pointer: 8 bytes (version+pad+subsystem) on 64-bit
    class SDL_version(ctypes.Structure):
        _fields_ = [('major', ctypes.c_uint8),
                    ('minor', ctypes.c_uint8),
                    ('patch', ctypes.c_uint8)]

    class SDL_SysWMinfo_cocoa(ctypes.Structure):
        _fields_ = [('window', ctypes.c_void_p)]

    class SDL_SysWMinfo(ctypes.Structure):
        _fields_ = [('version',   SDL_version),
                    ('_pad',      ctypes.c_uint8),
                    ('subsystem', ctypes.c_uint32),
                    ('window',    SDL_SysWMinfo_cocoa)]

    sdl2_path = ctypes.util.find_library('SDL2')
    if not sdl2_path:
        # pygame ships its own SDL2
        import pygame as _pg
        pkg_dir = os.path.dirname(_pg.__file__)
        # Common location inside pygame package
        candidates = [
            os.path.join(pkg_dir, 'libSDL2-2.0.0.dylib'),
            os.path.join(pkg_dir, '.dylibs', 'libSDL2-2.0.0.dylib'),
        ]
        import glob
        for pat in [os.path.join(pkg_dir, '**', '*SDL2*.dylib')]:
            found = glob.glob(pat, recursive=True)
            if found:
                sdl2_path = found[0]
                break
    if not sdl2_path:
        return None

    sdl2 = ctypes.cdll.LoadLibrary(sdl2_path)
    sdl2.SDL_GetWindowWMInfo.restype  = ctypes.c_int
    sdl2.SDL_GetWindowWMInfo.argtypes = [ctypes.c_void_p,
                                          ctypes.POINTER(SDL_SysWMinfo)]

    info = SDL_SysWMinfo()
    # Fill version via SDL_VERSION macro equivalent
    info.version.major = 2
    info.version.minor = 0
    info.version.patch = 0
    ret = sdl2.SDL_GetWindowWMInfo(ctypes.c_void_p(sdl_win), ctypes.byref(info))
    if ret == 0:
        return None
    return info.window.window  # NSWindow*


# Globals so the main loop can re-assert window state each frame.
_MAC_OBJC = None
_MAC_WINDOW = None


def configure_macos_window():
    global _MAC_OBJC, _MAC_WINDOW
    import ctypes
    try:
        objc = _objc_setup()

        window = _get_sdl_nswindow(objc)
        if not window:
            # Fallback: last window in NSApp.windows
            NSApp = _msg(objc, objc.objc_getClass(b'NSApplication'),
                         'sharedApplication')
            windows = _msg(objc, NSApp, 'windows')
            count = _msg(objc, windows, 'count', restype=ctypes.c_ulong)
            if count and count > 0:
                window = _msg(objc, windows, 'objectAtIndex:', count - 1,
                              argtypes=[ctypes.c_ulong])

        if not window:
            print("Warning: no NSWindow found — transparency not applied.")
            return

        # Transparent background
        NSColor   = objc.objc_getClass(b'NSColor')
        clear_col = _msg(objc, NSColor, 'clearColor')
        _msg(objc, window, 'setBackgroundColor:', clear_col)
        _msg(objc, window, 'setOpaque:', False, argtypes=[ctypes.c_bool])

        # Click-through
        _msg(objc, window, 'setIgnoresMouseEvents:', True,
             argtypes=[ctypes.c_bool])

        # Always on top — NSScreenSaverWindowLevel = 1000
        # (kCGMaximumWindowLevel = 2147483630 if you want above OS chrome too)
        _msg(objc, window, 'setLevel:', 1000, argtypes=[ctypes.c_long])

        # Float across all Spaces + sit above full-screen apps.
        #   NSWindowCollectionBehaviorCanJoinAllSpaces      = 1 << 0  = 1
        #   NSWindowCollectionBehaviorStationary            = 1 << 4  = 16
        #   NSWindowCollectionBehaviorIgnoresCycle          = 1 << 6  = 64
        #   NSWindowCollectionBehaviorFullScreenAuxiliary   = 1 << 8  = 256
        behavior = 1 | 16 | 64 | 256
        _msg(objc, window, 'setCollectionBehavior:', behavior,
             argtypes=[ctypes.c_ulong])

        # Hide from Dock / Cmd-Tab so it really feels like an overlay.
        # NSApplicationActivationPolicyAccessory = 1
        NSApp = _msg(objc, objc.objc_getClass(b'NSApplication'),
                     'sharedApplication')
        _msg(objc, NSApp, 'setActivationPolicy:', 1,
             argtypes=[ctypes.c_long], restype=ctypes.c_bool)

        # Make sure the window is actually ordered to the front.
        _msg(objc, window, 'orderFrontRegardless')

        _MAC_OBJC   = objc
        _MAC_WINDOW = window

        print("macOS overlay configured: transparent, click-through, always-on-top.")
    except Exception as e:
        print(f"macOS window config error: {e}")


def reassert_window_level():
    """Re-apply window level + orderFront. Called every ~1s from the main loop
    to defeat SDL/AppKit resets when the app loses focus."""
    import ctypes
    if _MAC_OBJC is None or _MAC_WINDOW is None:
        return
    try:
        _msg(_MAC_OBJC, _MAC_WINDOW, 'setLevel:', 1000, argtypes=[ctypes.c_long])
        _msg(_MAC_OBJC, _MAC_WINDOW, 'orderFrontRegardless')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.environ.setdefault('SDL_VIDEO_WINDOW_POS', '0,0')

    pygame.init()
    info = pygame.display.Info()
    SW, SH = info.current_w, info.current_h

    screen = pygame.display.set_mode((SW, SH), pygame.NOFRAME | pygame.SRCALPHA)
    pygame.display.set_caption("Desktop Pet")

    # Pump events so the NSWindow is created before we try to fetch it
    pygame.event.pump()
    time.sleep(0.05)

    configure_macos_window()

    clock = pygame.time.Clock()
    pet = Pet(SW, SH)

    frame_count = 0
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    pygame.quit(); sys.exit()

        pet.update()
        screen.fill(CLEAR)
        pet.draw(screen)
        pygame.display.flip()

        # Re-assert window level every second so we stay on top
        frame_count += 1
        if frame_count % FPS == 0:
            reassert_window_level()

        clock.tick(FPS)


if __name__ == '__main__':
    main()
