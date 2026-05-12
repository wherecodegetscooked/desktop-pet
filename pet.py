import ctypes
import ctypes.util
import math
import random
import signal
import sys
import time

import pygame


FPS = 60
SCALE = 3
SPRITE_W = 20
SPRITE_H = 18
WINDOW_W = SPRITE_W * SCALE
WINDOW_H = SPRITE_H * SCALE

PET_COLOR = (236, 145, 92, 255)
PET_SHADE = (195, 92, 72, 255)
BELLY_COLOR = (255, 198, 139, 255)
EYE_COLOR = (26, 20, 18, 255)
HIGHLIGHT = (255, 221, 176, 255)
CLEAR = (0, 0, 0, 0)

NS_BACKING_STORE_BUFFERED = 2
NS_WINDOW_STYLE_BORDERLESS = 0
NS_WINDOW_STYLE_NONACTIVATING_PANEL = 1 << 7
NS_WINDOW_COLLECTION_CAN_JOIN_ALL_SPACES = 1 << 0
NS_WINDOW_COLLECTION_IGNORES_CYCLE = 1 << 6
NS_WINDOW_COLLECTION_FULLSCREEN_AUXILIARY = 1 << 8
NS_APPLICATION_ACTIVATION_POLICY_ACCESSORY = 1
CG_WINDOW_LEVEL_ASSISTIVE_TECH_HIGH = 20
WINDOW_LIST_ON_SCREEN_ONLY = 1
WINDOW_LIST_EXCLUDE_DESKTOP = 16
GROUND_PLATFORM_NAME = "Desktop"
GRAVITY = 0.42

# Jump tuning ---------------------------------------------------------------
# Increase these to make the pet jump more often or jump higher.
RANDOM_JUMP_STATE_CHANCE = 0.1      # Chance that a new random state is JUMP.
WINDOW_JUMP_CHANCE = 0.006           # Per-frame chance to jump to another window.
NORMAL_JUMP_POWER_MIN = 5.5          # Smaller hop when jumping without a target.
NORMAL_JUMP_POWER_MAX = 6.0
TARGET_JUMP_POWER_MIN = 7.0          # Minimum power for window-to-window jumps.
MAX_TARGET_JUMP_POWER = 38.0         # Raise this to reach very high windows.
TARGET_JUMP_EXTRA_HEIGHT = 72        # Extra arc height above the destination edge.
MAX_TARGET_JUMP_SPEED_X = 12.5       # Horizontal speed cap for long jumps.
MAX_TARGET_DISTANCE = 1.0            # Fraction of screen width considered reachable.
MAX_TARGET_HEIGHT = 1.0              # Fraction of screen height considered reachable.


class State:
    IDLE = "IDLE"
    WALK = "WALK"
    RUN = "RUN"
    JUMP = "JUMP"


class NSPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class NSSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class NSRect(ctypes.Structure):
    _fields_ = [("origin", NSPoint), ("size", NSSize)]


class CGRect(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_double),
        ("y", ctypes.c_double),
        ("w", ctypes.c_double),
        ("h", ctypes.c_double),
    ]


def _objc_setup():
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    return objc


def _msg(objc, obj, selector, *args, restype=None, argtypes=None):
    sel = objc.sel_registerName(selector.encode())
    if restype is None:
        restype = ctypes.c_void_p
    if argtypes is None:
        argtypes = [ctypes.c_void_p] * len(args)

    proto = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)
    fn = ctypes.cast(objc.objc_msgSend, proto)
    converted = []
    for argtype, value in zip(argtypes, args):
        if isinstance(value, ctypes._SimpleCData) or isinstance(value, argtype):
            converted.append(value)
        else:
            converted.append(argtype(value))
    return fn(obj, sel, *converted)


def _nsstring(objc, text):
    NSString = objc.objc_getClass(b"NSString")
    return _msg(
        objc,
        NSString,
        "stringWithUTF8String:",
        text.encode(),
        argtypes=[ctypes.c_char_p],
    )


def _nsnumber_double(objc, number):
    if not number:
        return 0.0
    return _msg(objc, number, "doubleValue", restype=ctypes.c_double)


def _nsnumber_int(objc, number):
    if not number:
        return 0
    return _msg(objc, number, "intValue", restype=ctypes.c_int)


def _nsstring_text(objc, ns_string):
    if not ns_string:
        return ""
    value = _msg(objc, ns_string, "UTF8String", restype=ctypes.c_char_p)
    return value.decode(errors="ignore") if value else ""


class WindowTracker:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.objc = _objc_setup()
        self.cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        self.cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        self.cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
        self.cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        self.cf.CFRelease.argtypes = [ctypes.c_void_p]
        self.keys = {
            name: _nsstring(self.objc, name)
            for name in (
                "kCGWindowBounds",
                "kCGWindowLayer",
                "kCGWindowAlpha",
                "kCGWindowOwnerName",
                "kCGWindowNumber",
                "X",
                "Y",
                "Width",
                "Height",
            )
        }

    def platforms(self):
        platforms = [
            {
                "id": "desktop",
                "base_id": "desktop",
                "x": 0,
                "y": self.screen_h,
                "w": self.screen_w,
                "h": 1,
                "name": GROUND_PLATFORM_NAME,
                "edge": "ground",
            }
        ]

        options = WINDOW_LIST_ON_SCREEN_ONLY | WINDOW_LIST_EXCLUDE_DESKTOP
        array = self.cg.CGWindowListCopyWindowInfo(options, 0)
        if not array:
            return platforms

        try:
            occluders = []
            count = _msg(self.objc, array, "count", restype=ctypes.c_ulong)
            for i in range(count):
                info = _msg(
                    self.objc,
                    array,
                    "objectAtIndex:",
                    i,
                    argtypes=[ctypes.c_ulong],
                )
                window = self._window_from_info(info)
                if not window:
                    continue
                platforms.extend(self._platforms_from_window(window, occluders))
                occluders.append(window)
        finally:
            self.cf.CFRelease(array)

        platforms.sort(key=lambda item: item["y"])
        return platforms

    def _dict_value(self, dictionary, key):
        return _msg(self.objc, dictionary, "objectForKey:", self.keys[key])

    def _window_from_info(self, info):
        layer = _nsnumber_int(self.objc, self._dict_value(info, "kCGWindowLayer"))
        alpha = _nsnumber_double(self.objc, self._dict_value(info, "kCGWindowAlpha"))
        if layer != 0 or alpha <= 0.05:
            return None

        bounds = self._dict_value(info, "kCGWindowBounds")
        if not bounds:
            return None

        x = _nsnumber_double(self.objc, self._dict_value(bounds, "X"))
        y = _nsnumber_double(self.objc, self._dict_value(bounds, "Y"))
        w = _nsnumber_double(self.objc, self._dict_value(bounds, "Width"))
        h = _nsnumber_double(self.objc, self._dict_value(bounds, "Height"))
        if w < WINDOW_W * 1.4 or h < WINDOW_H * 0.9:
            return None

        window_id = _nsnumber_int(self.objc, self._dict_value(info, "kCGWindowNumber"))
        owner = _nsstring_text(self.objc, self._dict_value(info, "kCGWindowOwnerName"))
        px = int(max(0, x))
        pw = int(min(w, self.screen_w - px))
        py = int(max(0, y))
        ph = int(h)
        return {
            "id": window_id,
            "x": px,
            "y": py,
            "w": pw,
            "h": ph,
            "name": owner or "Window",
        }

    def _platforms_from_window(self, window, occluders):
        platforms = []
        top_y = window["y"]
        bottom_y = window["y"] + window["h"]
        if WINDOW_H + 8 <= top_y <= self.screen_h - 24:
            platforms.extend(
                self._edge_platforms(window, "top", top_y, occluders)
            )
        if WINDOW_H + 8 <= bottom_y <= self.screen_h - 24:
            platforms.extend(
                self._edge_platforms(window, "bottom", bottom_y, occluders)
            )
        return platforms

    def _edge_platforms(self, window, edge, edge_y, occluders):
        segments = [(window["x"], window["x"] + window["w"])]
        for occluder in occluders:
            if not (occluder["y"] <= edge_y <= occluder["y"] + occluder["h"]):
                continue
            segments = self._subtract_interval(
                segments,
                occluder["x"],
                occluder["x"] + occluder["w"],
            )
            if not segments:
                return []

        platforms = []
        min_width = int(WINDOW_W * 1.25)
        for index, (left, right) in enumerate(segments):
            width = right - left
            if width < min_width:
                continue
            platforms.append(
                {
                    "id": f"{window['id']}:{edge}:{index}:{left}",
                    "base_id": f"{window['id']}:{edge}",
                    "x": left,
                    "y": edge_y,
                    "w": width,
                    "h": 1,
                    "name": window["name"],
                    "edge": edge,
                }
            )
        return platforms

    def _subtract_interval(self, segments, cut_left, cut_right):
        result = []
        for left, right in segments:
            if cut_right <= left or cut_left >= right:
                result.append((left, right))
                continue
            if cut_left > left:
                result.append((left, max(left, cut_left)))
            if cut_right < right:
                result.append((min(right, cut_right), right))
        return result


class MacOverlay:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.objc = _objc_setup()
        self.cg = self._load_core_graphics()
        self.colorspace = self.cg.CGColorSpaceCreateDeviceRGB()
        self.nsapp = None
        self.window = None
        self.layer = None
        self.last_buffer = None
        self.level = self.cg.CGWindowLevelForKey(CG_WINDOW_LEVEL_ASSISTIVE_TECH_HIGH)

        self._create_window()

    def _load_core_graphics(self):
        cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        cg.CGMainDisplayID.restype = ctypes.c_uint32
        cg.CGDisplayBounds.restype = CGRect
        cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
        cg.CGWindowLevelForKey.restype = ctypes.c_int
        cg.CGWindowLevelForKey.argtypes = [ctypes.c_int]
        cg.CGColorSpaceCreateDeviceRGB.restype = ctypes.c_void_p
        cg.CGDataProviderCreateWithData.restype = ctypes.c_void_p
        cg.CGDataProviderCreateWithData.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
        ]
        cg.CGDataProviderRelease.argtypes = [ctypes.c_void_p]
        cg.CGImageCreate.restype = ctypes.c_void_p
        cg.CGImageCreate.argtypes = [
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_bool,
            ctypes.c_int,
        ]
        cg.CGImageRelease.argtypes = [ctypes.c_void_p]
        return cg

    def _create_window(self):
        objc = self.objc
        NSApplication = objc.objc_getClass(b"NSApplication")
        NSPanel = objc.objc_getClass(b"NSPanel")
        NSColor = objc.objc_getClass(b"NSColor")
        NSString = objc.objc_getClass(b"NSString")

        self.nsapp = _msg(objc, NSApplication, "sharedApplication")
        _msg(objc, self.nsapp, "finishLaunching")
        _msg(
            objc,
            self.nsapp,
            "setActivationPolicy:",
            NS_APPLICATION_ACTIVATION_POLICY_ACCESSORY,
            argtypes=[ctypes.c_long],
            restype=ctypes.c_bool,
        )

        rect = NSRect(NSPoint(200, 200), NSSize(self.width, self.height))
        style = NS_WINDOW_STYLE_BORDERLESS | NS_WINDOW_STYLE_NONACTIVATING_PANEL
        panel = _msg(objc, NSPanel, "alloc")
        self.window = _msg(
            objc,
            panel,
            "initWithContentRect:styleMask:backing:defer:",
            rect,
            style,
            NS_BACKING_STORE_BUFFERED,
            False,
            argtypes=[NSRect, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_bool],
        )

        clear = _msg(objc, NSColor, "clearColor")
        _msg(objc, self.window, "setOpaque:", False, argtypes=[ctypes.c_bool])
        _msg(objc, self.window, "setBackgroundColor:", clear)
        _msg(objc, self.window, "setHasShadow:", False, argtypes=[ctypes.c_bool])
        _msg(objc, self.window, "setIgnoresMouseEvents:", True, argtypes=[ctypes.c_bool])
        _msg(objc, self.window, "setCanHide:", False, argtypes=[ctypes.c_bool])
        _msg(objc, self.window, "setReleasedWhenClosed:", False, argtypes=[ctypes.c_bool])
        _msg(objc, self.window, "setAlphaValue:", 1.0, argtypes=[ctypes.c_double])

        behavior = (
            NS_WINDOW_COLLECTION_CAN_JOIN_ALL_SPACES
            | NS_WINDOW_COLLECTION_IGNORES_CYCLE
            | NS_WINDOW_COLLECTION_FULLSCREEN_AUXILIARY
        )
        _msg(objc, self.window, "setCollectionBehavior:", behavior, argtypes=[ctypes.c_ulong])
        self.reassert_top()

        view = _msg(objc, self.window, "contentView")
        _msg(objc, view, "setWantsLayer:", True, argtypes=[ctypes.c_bool])
        self.layer = _msg(objc, view, "layer")
        _msg(objc, self.layer, "setOpaque:", False, argtypes=[ctypes.c_bool])
        clear_cg = _msg(objc, clear, "CGColor")
        _msg(objc, self.layer, "setBackgroundColor:", clear_cg)

        nearest = _msg(
            objc,
            NSString,
            "stringWithUTF8String:",
            b"nearest",
            argtypes=[ctypes.c_char_p],
        )
        _msg(objc, self.layer, "setMagnificationFilter:", nearest)
        _msg(objc, self.layer, "setMinificationFilter:", nearest)
        _msg(objc, self.window, "orderFrontRegardless")

    def screen_bounds(self):
        bounds = self.cg.CGDisplayBounds(self.cg.CGMainDisplayID())
        return int(bounds.x), int(bounds.y), int(bounds.w), int(bounds.h)

    def reassert_top(self):
        _msg(self.objc, self.window, "setLevel:", self.level, argtypes=[ctypes.c_long])
        _msg(self.objc, self.window, "orderFrontRegardless")

    def move(self, x, y):
        _, _, _, screen_h = self.screen_bounds()
        flipped_y = screen_h - y - self.height
        sel = self.objc.sel_registerName(b"setFrameOrigin:")
        proto = ctypes.CFUNCTYPE(
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_double,
            ctypes.c_double,
        )
        fn = ctypes.cast(self.objc.objc_msgSend, proto)
        fn(self.window, sel, ctypes.c_double(float(x)), ctypes.c_double(float(flipped_y)))

    def show_surface(self, surface):
        if hasattr(surface, "premul_alpha"):
            surface = surface.premul_alpha()
        pixels = pygame.image.tobytes(surface, "BGRA")
        buf = (ctypes.c_ubyte * len(pixels)).from_buffer_copy(pixels)
        provider = self.cg.CGDataProviderCreateWithData(None, buf, len(pixels), None)
        if not provider:
            return

        kCGImageAlphaPremultipliedFirst = 2
        kCGBitmapByteOrder32Little = 2 << 12
        image = self.cg.CGImageCreate(
            surface.get_width(),
            surface.get_height(),
            8,
            32,
            surface.get_width() * 4,
            self.colorspace,
            kCGImageAlphaPremultipliedFirst | kCGBitmapByteOrder32Little,
            provider,
            None,
            False,
            0,
        )
        if image:
            _msg(self.objc, self.layer, "setContents:", image)
            self.cg.CGImageRelease(image)
        self.cg.CGDataProviderRelease(provider)
        self.last_buffer = buf

    def pump_events(self):
        NSDate = self.objc.objc_getClass(b"NSDate")
        NSString = self.objc.objc_getClass(b"NSString")
        distant_past = _msg(self.objc, NSDate, "distantPast")
        mode = _msg(
            self.objc,
            NSString,
            "stringWithUTF8String:",
            b"kCFRunLoopDefaultMode",
            argtypes=[ctypes.c_char_p],
        )
        event = True
        while event:
            event = _msg(
                self.objc,
                self.nsapp,
                "nextEventMatchingMask:untilDate:inMode:dequeue:",
                (1 << 64) - 1,
                distant_past,
                mode,
                True,
                argtypes=[
                    ctypes.c_ulonglong,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                    ctypes.c_bool,
                ],
            )
            if event:
                _msg(self.objc, self.nsapp, "sendEvent:", event)
        _msg(self.objc, self.nsapp, "updateWindows")


class Pet:
    def __init__(self, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.x = float(screen_w // 2)
        self.y = float(screen_h // 2)
        self.vx = 0.0
        self.vy = 0.0
        self.state = State.IDLE
        self.state_timer = 0
        self.facing_right = True
        self.frame = 0
        self.blink = False
        self.blink_timer = random.randint(90, 240)
        self.look_offset = 0
        self.look_timer = random.randint(60, 180)
        self.ground_y = self.y
        self.jump_vy = 0.0
        self.airborne = False
        self.platform = None
        self.jump_target = None
        self.jump_cooldown = 0
        self.pick_state()

    def pick_state(self):
        r = random.random()
        if r < 0.55:
            self.state = State.WALK
            speed = random.uniform(0.7, 1.8)
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * speed
            self.vy = random.uniform(-0.25, 0.25)
            self.state_timer = random.randint(100, 300)
        elif r < 0.75:
            self.state = State.IDLE
            self.vx = 0.0
            self.vy = 0.0
            self.state_timer = random.randint(70, 190)
        elif r < 1.0 - RANDOM_JUMP_STATE_CHANCE:
            self.state = State.RUN
            speed = random.uniform(3.0, 5.6)
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * speed
            self.vy = random.uniform(-0.35, 0.35)
            self.state_timer = random.randint(45, 115)
        else:
            if self.jump_cooldown > 0:
                self.state = State.WALK
                self.vx = random.choice([-1, 1]) * random.uniform(0.7, 1.8)
                self.vy = random.uniform(-0.25, 0.25)
                self.state_timer = random.randint(80, 180)
            else:
                self.state = State.JUMP
                self.start_jump()

    def start_jump(self, target=None):
        self.state = State.JUMP
        self.airborne = True
        self.jump_target = target
        self.jump_vy = -random.uniform(NORMAL_JUMP_POWER_MIN, NORMAL_JUMP_POWER_MAX)
        if target:
            target_center = target["x"] + target["w"] * 0.5
            pet_center = self.x + WINDOW_W * 0.5
            target_feet_y = target["y"]
            current_feet_y = self.y + WINDOW_H
            rise = max(0, current_feet_y - target_feet_y)
            distance = target_center - pet_center
            clearance = max(4, min(TARGET_JUMP_EXTRA_HEIGHT, target_feet_y - WINDOW_H - 8))
            self.jump_vy = -min(
                MAX_TARGET_JUMP_POWER,
                max(TARGET_JUMP_POWER_MIN, math.sqrt(2 * GRAVITY * (rise + clearance))),
            )
            airtime = max(34, (abs(self.jump_vy) * 2) / GRAVITY)
            self.vx = max(
                -MAX_TARGET_JUMP_SPEED_X,
                min(MAX_TARGET_JUMP_SPEED_X, distance / airtime),
            )
        elif abs(self.vx) < 0.3:
            self.vx = random.uniform(-2.5, 2.5)
        self.vy = 0.0
        self.state_timer = 240

    def update(self, platforms):
        self.frame += 1
        self.state_timer -= 1
        self.jump_cooldown = max(0, self.jump_cooldown - 1)
        self._update_face()

        if not self.airborne and self.state != State.JUMP:
            self._maybe_jump_to_window(platforms)

        if self.airborne or self.state == State.JUMP:
            self.jump_vy += GRAVITY
            self.y += self.jump_vy
            self.x += self.vx
            self._land_if_possible(platforms)
        else:
            self.x += self.vx
            if self.platform and self._feet_inside_platform(self.platform):
                self.y = self.platform["y"] - WINDOW_H
            else:
                self.airborne = True
                self.state = State.JUMP
                self.jump_vy = 0.0

        if self.vx > 0.1:
            self.facing_right = True
        elif self.vx < -0.1:
            self.facing_right = False

        if self.x < 0:
            self.x = 0
            self.vx = abs(self.vx)
            self.facing_right = True
        elif self.x + WINDOW_W > self.screen_w:
            self.x = self.screen_w - WINDOW_W
            self.vx = -abs(self.vx)
            self.facing_right = False

        if self.y + WINDOW_H > self.screen_h:
            self.y = self.screen_h - WINDOW_H
            self.airborne = False
            self.platform = platforms[0] if platforms else None
            if self.state == State.JUMP:
                self.jump_cooldown = 30
                self.pick_state()

        if self.state_timer <= 0 and not self.airborne:
            self.pick_state()

    def _update_face(self):
        self.blink_timer -= 1
        if self.blink_timer <= 0:
            if self.blink:
                self.blink = False
                self.blink_timer = random.randint(100, 260)
            else:
                self.blink = True
                self.blink_timer = random.randint(5, 9)

        self.look_timer -= 1
        if self.look_timer <= 0:
            self.look_offset = random.choice([-1, 0, 1])
            self.look_timer = random.randint(45, 160)

    def place_on_best_platform(self, platforms):
        current = self._matching_platform(platforms, self.platform)
        if current and self._feet_inside_platform(current):
            self.platform = current
            self.y = current["y"] - WINDOW_H
            self.airborne = False
            return

        below = [
            platform
            for platform in platforms
            if self._feet_x() >= platform["x"]
            and self._feet_x() <= platform["x"] + platform["w"]
            and platform["y"] >= self.y + WINDOW_H - 4
        ]
        self.platform = min(below, key=lambda item: item["y"], default=platforms[0])
        self.y = self.platform["y"] - WINDOW_H
        self.airborne = False

    def sync_platforms(self, platforms):
        current = self._matching_platform(platforms, self.platform)
        if current and self._feet_inside_platform(current):
            self.platform = current
            self.y = current["y"] - WINDOW_H
            return

        self.platform = None
        self.airborne = True
        self.state = State.JUMP
        self.jump_target = None
        self.jump_vy = max(0.0, self.jump_vy)

    def _matching_platform(self, platforms, platform):
        if not platform:
            return None
        for candidate in platforms:
            if candidate.get("id") == platform.get("id"):
                return candidate
        for candidate in platforms:
            if candidate.get("base_id") == platform.get("base_id"):
                if self._feet_inside_platform(candidate):
                    return candidate
        return None

    def _feet_x(self):
        return self.x + WINDOW_W * 0.5

    def _feet_inside_platform(self, platform):
        foot = self._feet_x()
        return platform["x"] + 8 <= foot <= platform["x"] + platform["w"] - 8

    def _landing_platform(self, platforms):
        previous_feet_y = self.y + WINDOW_H - self.jump_vy
        feet_y = self.y + WINDOW_H
        foot_x = self._feet_x()
        candidates = []
        for platform in platforms:
            if not (platform["x"] <= foot_x <= platform["x"] + platform["w"]):
                continue
            if previous_feet_y <= platform["y"] <= feet_y:
                candidates.append(platform)
        return min(candidates, key=lambda item: item["y"], default=None)

    def _land_if_possible(self, platforms):
        if self.jump_vy < 0:
            return
        platform = self._landing_platform(platforms)
        if not platform:
            return
        self.platform = platform
        self.y = platform["y"] - WINDOW_H
        self.airborne = False
        self.jump_target = None
        self.jump_cooldown = 30
        self.pick_state()

    def _maybe_jump_to_window(self, platforms):
        if self.jump_cooldown > 0:
            return
        if self.state not in (State.IDLE, State.WALK):
            return
        if random.random() > WINDOW_JUMP_CHANCE:
            return

        foot = self._feet_x()
        current_y = self.y + WINDOW_H
        candidates = []
        for platform in platforms:
            if platform.get("id") == (self.platform or {}).get("id"):
                continue
            if platform.get("base_id") == (self.platform or {}).get("base_id"):
                continue
            if platform["name"] == GROUND_PLATFORM_NAME:
                continue
            center = platform["x"] + platform["w"] * 0.5
            distance = abs(center - foot)
            vertical = platform["y"] - current_y
            if (
                distance < self.screen_w * MAX_TARGET_DISTANCE
                and -self.screen_h * MAX_TARGET_HEIGHT < vertical < 260
            ):
                candidates.append(platform)

        if candidates:
            candidates.sort(
                key=lambda platform: (
                    platform["y"],
                    abs((platform["x"] + platform["w"] * 0.5) - foot),
                )
            )
            self.start_jump(random.choice(candidates[:3]))


def px(surface, x, y, color):
    if 0 <= x < SPRITE_W and 0 <= y < SPRITE_H:
        surface.set_at((x, y), color)


def rect(surface, x, y, w, h, color):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            px(surface, xx, yy, color)


def draw_pet_frame(pet):
    small = pygame.Surface((SPRITE_W, SPRITE_H), pygame.SRCALPHA)
    small.fill(CLEAR)

    bob = 0
    if pet.state in (State.WALK, State.RUN):
        step_speed = 7 if pet.state == State.WALK else 4
        bob = 1 if (pet.frame // step_speed) % 2 else 0
    if pet.state == State.JUMP:
        bob = -1

    body_y = 4 + bob
    rect(small, 5, body_y + 1, 10, 8, PET_COLOR)
    rect(small, 4, body_y + 3, 12, 5, PET_COLOR)
    rect(small, 7, body_y + 6, 6, 4, BELLY_COLOR)
    rect(small, 6, body_y + 1, 2, 1, HIGHLIGHT)
    rect(small, 13, body_y + 4, 2, 4, PET_SHADE)

    # Ears
    px(small, 5, body_y, PET_COLOR)
    px(small, 6, body_y - 1, PET_COLOR)
    px(small, 14, body_y, PET_COLOR)
    px(small, 13, body_y - 1, PET_COLOR)

    # Arms
    arm_swing = 1 if (pet.frame // 7) % 2 else 0
    if pet.state == State.IDLE:
        arm_swing = 0
    rect(small, 3, body_y + 6 - arm_swing, 2, 2, PET_COLOR)
    rect(small, 15, body_y + 5 + arm_swing, 2, 2, PET_COLOR)

    # Legs
    phase = (pet.frame // (7 if pet.state == State.WALK else 4)) % 2
    leg_lift = pet.state in (State.WALK, State.RUN)
    for i, leg_x in enumerate([6, 9, 12, 14]):
        lifted = leg_lift and (i % 2 == phase)
        leg_h = 1 if lifted else 3
        rect(small, leg_x, body_y + 9, 1, leg_h, PET_SHADE)

    # Face
    eye_y = body_y + 4
    left_eye_x = 7 + pet.look_offset
    right_eye_x = 12 + pet.look_offset
    if pet.blink:
        rect(small, left_eye_x, eye_y + 1, 2, 1, EYE_COLOR)
        rect(small, right_eye_x, eye_y + 1, 2, 1, EYE_COLOR)
    else:
        rect(small, left_eye_x, eye_y, 1, 2, EYE_COLOR)
        rect(small, right_eye_x, eye_y, 1, 2, EYE_COLOR)
        px(small, left_eye_x, eye_y, HIGHLIGHT)
        px(small, right_eye_x, eye_y, HIGHLIGHT)

    mouth_y = body_y + 7
    if pet.state == State.RUN:
        rect(small, 9, mouth_y, 2, 1, EYE_COLOR)
    elif pet.state == State.JUMP:
        px(small, 10, mouth_y, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
    else:
        px(small, 9, mouth_y, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
        px(small, 11, mouth_y, EYE_COLOR)

    if not pet.facing_right:
        small = pygame.transform.flip(small, True, False)

    return pygame.transform.scale(small, (WINDOW_W, WINDOW_H))


def main():
    if sys.platform != "darwin":
        raise SystemExit("This overlay implementation is for macOS.")

    running = True

    def stop(_signum=None, _frame=None):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    pygame.init()
    overlay = MacOverlay(WINDOW_W, WINDOW_H)
    _, _, screen_w, screen_h = overlay.screen_bounds()
    window_tracker = WindowTracker(screen_w, screen_h)
    platforms = window_tracker.platforms()
    pet = Pet(screen_w, screen_h)
    pet.place_on_best_platform(platforms)
    canvas = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    clock = pygame.time.Clock()
    last_reassert = 0.0
    last_window_scan = 0.0

    while running:
        now = time.monotonic()
        if now - last_window_scan > 0.75:
            platforms = window_tracker.platforms()
            if not pet.airborne:
                pet.sync_platforms(platforms)
            last_window_scan = now

        pet.update(platforms)
        canvas.fill(CLEAR)
        canvas.blit(draw_pet_frame(pet), (0, 0))

        overlay.move(round(pet.x), round(pet.y))
        overlay.show_surface(canvas)
        overlay.pump_events()

        if now - last_reassert > 0.5:
            overlay.reassert_top()
            last_reassert = now

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
