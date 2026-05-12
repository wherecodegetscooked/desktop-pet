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
            px.set_at((5, 2), E)
            px.set_at((6, 2), E)
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
    """Return (objc_lib, msg_fn) with restype set to void_p."""
    import ctypes, ctypes.util
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
    objc.objc_getClass.restype   = ctypes.c_void_p
    objc.objc_getClass.argtypes  = [ctypes.c_char_p]
    objc.sel_registerName.restype  = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    objc.objc_msgSend.restype  = ctypes.c_void_p
    objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    return objc


def _msg(objc, obj, sel_name, *args):
    import ctypes
    sel = objc.sel_registerName(sel_name.encode())
    fn = objc.objc_msgSend
    if not args:
        fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        fn.restype  = ctypes.c_void_p
        return fn(obj, sel)
    elif len(args) == 1 and isinstance(args[0], bool):
        # bool message
        proto = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)
        return proto(fn)(obj, sel, args[0])
    elif len(args) == 1 and isinstance(args[0], int):
        import ctypes
        proto = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)
        return proto(fn)(obj, sel, ctypes.c_long(args[0]))
    elif len(args) == 1:
        fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        fn.restype  = ctypes.c_void_p
        return fn(obj, sel, args[0])
    else:
        raise ValueError(f"Unhandled arg types: {args}")


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


def configure_macos_window():
    try:
        objc = _objc_setup()

        window = _get_sdl_nswindow(objc)

        if not window:
            # Fallback: grab last window from NSApp.windows array
            import ctypes
            NSApp = _msg(objc, objc.objc_getClass(b'NSApplication'), 'sharedApplication')
            windows = _msg(objc, NSApp, 'windows')
            fn = objc.objc_msgSend
            fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            fn.restype = ctypes.c_ulong
            count = fn(windows, objc.sel_registerName(b'count'))
            fn.restype = ctypes.c_void_p
            if count > 0:
                get_at = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_void_p, ctypes.c_ulong)
                window = get_at(objc.objc_msgSend)(
                    windows,
                    objc.sel_registerName(b'objectAtIndex:'),
                    ctypes.c_ulong(count - 1)
                )

        if not window:
            print("Warning: no NSWindow found — transparency not applied.")
            return

        # Transparent background
        NSColor   = objc.objc_getClass(b'NSColor')
        clear_col = _msg(objc, NSColor, 'clearColor')
        _msg(objc, window, 'setBackgroundColor:', clear_col)
        _msg(objc, window, 'setOpaque:', False)

        # Click-through
        _msg(objc, window, 'setIgnoresMouseEvents:', True)

        # Always on top
        _msg(objc, window, 'setLevel:', 1000)

        print("macOS transparency + click-through applied.")
    except Exception as e:
        print(f"macOS window config error: {e}")


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
        clock.tick(FPS)


if __name__ == '__main__':
    main()
