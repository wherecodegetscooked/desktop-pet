import pygame
import sys
import random
import math
import os
import time

SCALE = 4
FPS = 60
SPRITE_W, SPRITE_H = 16, 10  # pixel canvas size before scale

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
    """Draw onto a 16×10 SRCALPHA surface (pixel art, no scaling).

    Design coords are bottom-left origin; pygame is top-left so pg_y = 9 -
    cart_y. Resulting pygame coords:
      body   x 2..13   y 0..7      (cart y 2..9)
      L arm  x 0..1    y 4..5      (cart y 4..5)
      R arm  x 14..15  y 3..5      (cart y 4..6)
      eyes   (4, 2-3) and (11, 2-3)  (cart y 6..7)
      legs   at x 3, 5, 10, 12;  y 8..9 (cart y 0..1)
    """
    px.fill(CLEAR)
    C = PET_COLOR
    E = EYE_COLOR

    # Body
    for bx in range(2, 14):
        for by in range(0, 8):
            px.set_at((bx, by), C)

    # Left arm  (2×2)
    for ax in range(0, 2):
        for ay in range(4, 6):
            px.set_at((ax, ay), C)

    # Right arm  (2×3)
    for ax in range(14, 16):
        for ay in range(3, 6):
            px.set_at((ax, ay), C)

    # Legs — 1×2 normally, 1×1 when "up" during walk/run.
    leg_xs = [3, 5, 10, 12]
    if state in (State.WALK, State.RUN):
        speed = 3 if state == State.WALK else 2
        phase = (anim_frame // speed) % 2
    else:
        phase = 0  # both pairs down when idle/jump

    for i, lx in enumerate(leg_xs):
        up = (state in (State.WALK, State.RUN)) and ((i % 2) == phase)
        if up:
            px.set_at((lx, 8), C)             # shortened — 1 pixel
        else:
            px.set_at((lx, 8), C)
            px.set_at((lx, 9), C)             # 2-pixel leg

    # Eyes — 1×2 each at x=4 and x=11. Sprite is symmetric so we draw both
    # regardless of facing direction; blink hides them.
    if not blink:
        px.set_at((4, 2), E)
        px.set_at((4, 3), E)
        px.set_at((11, 2), E)
        px.set_at((11, 3), E)


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
        # Window is sprite-sized; draw at (0, 0). Window itself is moved to
        # the pet's screen position each frame via SDL_SetWindowPosition.
        sprite = make_sprite(self.facing_right, self.frame, self.state, self.blink)
        screen.blit(sprite, (0, 0))


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
_SDL2 = None
_SDL_WINDOW = None  # SDL_Window* as an integer
_PRIMARY_HEIGHT = 0  # primary display height in points, set in main()


def _load_sdl2():
    """Locate and load the SDL2 dylib pygame is using."""
    import ctypes, ctypes.util, glob
    path = ctypes.util.find_library('SDL2')
    if not path:
        import pygame as _pg
        pkg_dir = os.path.dirname(_pg.__file__)
        for found in glob.glob(os.path.join(pkg_dir, '**', '*SDL2*.dylib'),
                               recursive=True):
            path = found
            break
    if not path:
        return None
    sdl2 = ctypes.cdll.LoadLibrary(path)
    sdl2.SDL_SetWindowPosition.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
    sdl2.SDL_SetWindowPosition.restype  = None
    return sdl2


def _get_sdl_window_ptr():
    """Extract SDL_Window* (as int) from pygame's wm_info capsule."""
    import ctypes
    PyCapsule_GetPointer = ctypes.pythonapi.PyCapsule_GetPointer
    PyCapsule_GetPointer.restype  = ctypes.c_void_p
    PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]
    wm = pygame.display.get_wm_info()
    return PyCapsule_GetPointer(wm['window'], b'window')


def move_window(x, y):
    """Move pet window to top-left screen coords (x, y).

    AppKit windows use a bottom-left origin so we flip y against the primary
    display height. Goes via NSWindow.setFrameOrigin: because
    SDL_SetWindowPosition becomes a no-op once we tweak window level. An
    NSPoint (struct of 2 CGFloats) is ABI-compatible with two consecutive
    c_doubles on both x86_64 SysV and AArch64, so we send two doubles."""
    import ctypes
    if _MAC_OBJC is None or _MAC_WINDOW is None:
        return
    flipped_y = _PRIMARY_HEIGHT - y - SPRITE_H * SCALE
    sel = _MAC_OBJC.sel_registerName(b'setFrameOrigin:')
    proto = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                              ctypes.c_double, ctypes.c_double)
    fn = ctypes.cast(_MAC_OBJC.objc_msgSend, proto)
    fn(_MAC_WINDOW, sel,
       ctypes.c_double(float(x)), ctypes.c_double(float(flipped_y)))


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

        # Float across all Spaces + sit above full-screen apps.
        # Do NOT include NSWindowCollectionBehaviorStationary — it freezes
        # the window's position so setFrameOrigin: becomes a no-op.
        #   NSWindowCollectionBehaviorCanJoinAllSpaces    = 1 << 0  = 1
        #   NSWindowCollectionBehaviorFullScreenAuxiliary = 1 << 8  = 256
        behavior = 1 | 256
        _msg(objc, window, 'setCollectionBehavior:', behavior,
             argtypes=[ctypes.c_ulong])

        # Always on top — NSStatusWindowLevel = 25 sits above normal app
        # windows but below the system menu bar, so the menu stays usable.
        _msg(objc, window, 'setLevel:', 25, argtypes=[ctypes.c_long])

        # Transparent background  (do this AFTER level/behavior changes)
        NSColor   = objc.objc_getClass(b'NSColor')
        clear_col = _msg(objc, NSColor, 'clearColor')
        _msg(objc, window, 'setOpaque:', False, argtypes=[ctypes.c_bool])
        _msg(objc, window, 'setBackgroundColor:', clear_col)
        _msg(objc, window, 'setHasShadow:', False, argtypes=[ctypes.c_bool])

        # Mark the Metal/CA layer non-opaque so per-pixel alpha reaches
        # the compositor — without this, SDL2's Metal layer renders as
        # opaque and transparent pixels show as black.
        content_view = _msg(objc, window, 'contentView')
        if content_view:
            _msg(objc, content_view, 'setWantsLayer:', True,
                 argtypes=[ctypes.c_bool])
            layer = _msg(objc, content_view, 'layer')
            if layer:
                _msg(objc, layer, 'setOpaque:', False,
                     argtypes=[ctypes.c_bool])
                clear_cg = _msg(objc, clear_col, 'CGColor')
                if clear_cg:
                    _msg(objc, layer, 'setBackgroundColor:', clear_cg)
                # Diagnostic: what kind of layer is SDL2 giving us?
                cls = _msg(objc, layer, 'class')
                if cls:
                    name_sel = objc.sel_registerName(b'description')
                    proto = ctypes.CFUNCTYPE(ctypes.c_void_p,
                                             ctypes.c_void_p,
                                             ctypes.c_void_p)
                    fn = ctypes.cast(objc.objc_msgSend, proto)
                    ns_str = fn(cls, name_sel)
                    if ns_str:
                        utf8_sel = objc.sel_registerName(b'UTF8String')
                        utf8_proto = ctypes.CFUNCTYPE(ctypes.c_char_p,
                                                     ctypes.c_void_p,
                                                     ctypes.c_void_p)
                        utf8_fn = ctypes.cast(objc.objc_msgSend, utf8_proto)
                        s = utf8_fn(ns_str, utf8_sel)
                        if s:
                            print(f"contentView.layer class = {s.decode()}")

        # Click-through (mouse events pass to the app below)
        _msg(objc, window, 'setIgnoresMouseEvents:', True,
             argtypes=[ctypes.c_bool])

        _MAC_OBJC   = objc
        _MAC_WINDOW = window

        print("macOS overlay configured: transparent, click-through, always-on-top.")
    except Exception as e:
        print(f"macOS window config error: {e}")


def reassert_window_level():
    """Re-apply window level + transparency. Called periodically to defeat
    any AppKit/SDL resets that push us behind apps or make us opaque."""
    import ctypes
    if _MAC_OBJC is None or _MAC_WINDOW is None:
        return
    try:
        _msg(_MAC_OBJC, _MAC_WINDOW, 'setLevel:', 25, argtypes=[ctypes.c_long])
        _msg(_MAC_OBJC, _MAC_WINDOW, 'setOpaque:', False,
             argtypes=[ctypes.c_bool])
        NSColor   = _MAC_OBJC.objc_getClass(b'NSColor')
        clear_col = _msg(_MAC_OBJC, NSColor, 'clearColor')
        _msg(_MAC_OBJC, _MAC_WINDOW, 'setBackgroundColor:', clear_col)
        content_view = _msg(_MAC_OBJC, _MAC_WINDOW, 'contentView')
        if content_view:
            layer = _msg(_MAC_OBJC, content_view, 'layer')
            if layer:
                _msg(_MAC_OBJC, layer, 'setOpaque:', False,
                     argtypes=[ctypes.c_bool])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _screen_bounds():
    """Return (origin_x, origin_y, width, height) for the primary display
    in macOS global screen coordinates."""
    import ctypes, ctypes.util
    cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library('CoreGraphics'))

    class CGRect(ctypes.Structure):
        _fields_ = [('x', ctypes.c_double), ('y', ctypes.c_double),
                    ('w', ctypes.c_double), ('h', ctypes.c_double)]

    cg.CGMainDisplayID.restype  = ctypes.c_uint32
    cg.CGDisplayBounds.restype  = CGRect
    cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
    r = cg.CGDisplayBounds(cg.CGMainDisplayID())
    return int(r.x), int(r.y), int(r.w), int(r.h)


def main():
    global _SDL2, _SDL_WINDOW, _PRIMARY_HEIGHT

    pygame.init()

    ox, oy, SW, SH = _screen_bounds()
    _PRIMARY_HEIGHT = SH  # needed for AppKit y-flip in move_window
    W = SPRITE_W * SCALE
    H = SPRITE_H * SCALE

    # Position the window initially at the center of the primary display.
    os.environ['SDL_VIDEO_WINDOW_POS'] = f'{ox + SW // 2},{oy + SH // 2}'

    screen = pygame.display.set_mode((W, H), pygame.NOFRAME | pygame.SRCALPHA)
    pygame.display.set_caption("Desktop Pet")
    print(f"display flags = 0x{screen.get_flags():x} "
          f"(SRCALPHA={bool(screen.get_flags() & pygame.SRCALPHA)}) "
          f"bitsize={screen.get_bitsize()} "
          f"masks={screen.get_masks()}")

    pygame.event.pump()
    time.sleep(0.05)

    _SDL2 = _load_sdl2()
    _SDL_WINDOW = _get_sdl_window_ptr()

    configure_macos_window()

    clock = pygame.time.Clock()
    # Pet bookkeeping uses local (0..SW, 0..SH) coordinates; we translate to
    # global screen coords when moving the window.
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

        # Render sprite into the tiny window
        screen.fill(CLEAR)
        pet.draw(screen)
        pygame.display.flip()

        # Move the window to follow the pet (translate to global coords)
        move_window(ox + int(pet.x), oy + int(pet.y))

        frame_count += 1
        if frame_count % FPS == 0:
            reassert_window_level()

        clock.tick(FPS)


if __name__ == '__main__':
    main()
