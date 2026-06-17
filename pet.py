import ctypes
import ctypes.util
import math
import os
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
NS_STATUS_ITEM_VARIABLE_LENGTH = -1.0
CG_WINDOW_LEVEL_ASSISTIVE_TECH_HIGH = 20
WINDOW_LIST_ON_SCREEN_ONLY = 1
WINDOW_LIST_EXCLUDE_DESKTOP = 16
GROUND_PLATFORM_NAME = "Desktop"
GRAVITY = 0.42
NSEVENT_LEFT_MOUSE_DOWN = 1
NSEVENT_LEFT_MOUSE_UP = 2
NSEVENT_LEFT_MOUSE_DRAGGED = 6
MENU_ICON_SIZE = 18.0
CLICK_MOVE_THRESHOLD = 5             # Px of motion that turns a click into a drag.

# Jump tuning ---------------------------------------------------------------
# Increase these to make the pet jump more often or jump higher.
RANDOM_JUMP_STATE_CHANCE = 0.03      # Chance that a new random state is JUMP.
WINDOW_JUMP_CHANCE = 0.002           # Per-frame chance to jump to another window.
PLATFORM_DROP_CHANCE = 0.002        # Per-frame chance to drop through current ledge.
NORMAL_JUMP_POWER_MIN = 5.5          # Smaller hop when jumping without a target.
NORMAL_JUMP_POWER_MAX = 6.0
TARGET_JUMP_POWER_MIN = 8.0          # Minimum power for window-to-window jumps.
MAX_TARGET_JUMP_POWER = 38.0         # Raise this to reach very high windows.
TARGET_JUMP_EXTRA_HEIGHT = 72        # Extra arc height above the destination edge.
MAX_TARGET_JUMP_SPEED_X = 6.0        # Horizontal speed cap for long jumps.
MAX_TARGET_DISTANCE = 0.3           # Fraction of screen width considered reachable.
MAX_TARGET_HEIGHT = 1.5              # Fraction of screen height considered reachable.
MIN_PLATFORM_Y = 0                   # Allows high ledges where pet stands off-screen.

# Speech tuning -------------------------------------------------------------
SPEAK_CHANCE = 0.012                  # Per-frame chance to start talking (off cooldown).
SPEAK_COOLDOWN_MIN = 360              # Min frames of silence between lines (~6s).
SPEAK_COOLDOWN_MAX = 1200             # Max frames of silence between lines (~20s).
SPEECH_MIN_FRAMES = 150              # Shortest time a bubble stays up (~2.5s).
SPEECH_PER_CHAR = 6                  # Extra frames shown per character of text.

# Pixel speech bubble dimensions.
BUBBLE_SCALE = 3                     # Nearest-neighbour upscale for the pixel look.
BUBBLE_MAX_TEXT_W = 96               # Wrap width in base (pre-scale) pixels.
BUBBLE_TEXT_COLOR = (40, 30, 28, 255)
BUBBLE_FILL_COLOR = (255, 250, 235, 255)
BUBBLE_GAP = 8                       # Pixels between the bubble tail tip and the pet.

# Effects overlay (speech bubble + particles) ------------------------------
# A transparent, click-through window centred on the pet. Big enough to hold a
# bubble either above or below the pet plus floating particles.
FX_W = 420
FX_H = 440
PARTICLE_SCALE = 3
MAX_PARTICLES = 60
HEART_COLOR = (255, 95, 130, 255)
STAR_COLOR = (255, 214, 92, 255)
ANGER_COLOR = (232, 64, 52, 255)

# Mouse interaction --------------------------------------------------------
FOLLOW_CHANCE = 0.004                # Per-frame chance to start chasing the cursor.
FOLLOW_STOP_DISTANCE = 12            # Stop once this close (px) to the cursor.
FOLLOW_RUN_DISTANCE = 220            # Run instead of walk when farther than this.
IDLE_FX_MIN = 360                    # Min frames between spontaneous heart/stars.
IDLE_FX_MAX = 1080

# Anger ---------------------------------------------------------------------
ANGRY_THRESHOLD = 3                  # Clicks (before cooling down) that anger the pet.
ANGRY_DURATION = 240                 # Frames the pet stays grumpy (~4s).
ANGER_DECAY = 0.015                  # Anger cooled per frame.

ANGRY_PHRASES = [
    "Hey!",
    "Stop poking me!",
    "Quit it!",
    "Grrr!",
    "Leave me alone!",
    "Ouch!",
    "Cut it out!",
    "Rude!",
    "Not a button!",
]

PHRASES = [
    "Go work!",
    "Back to work!",
    "Focus, human!",
    "No slacking!",
    "You got this!",
    "Ship it!",
    "Just one more task.",
    "Deep breath. Begin.",
    "Eyes on the prize!",
    "Stop scrolling!",
    "Hydrate!",
    "Drink some water.",
    "Stretch your legs.",
    "Sit up straight!",
    "Blink. Rest your eyes.",
    "Take a tiny break.",
    "Snack time?",
    "You're doing great.",
    "Almost there!",
    "Keep going!",
    "One step at a time.",
    "Save your work!",
    "Did you commit?",
    "Push to main!",
    "Write the tests.",
    "Read the docs.",
    "Refactor later.",
    "Ship now, polish later.",
    "Coffee break!",
    "Tabs or spaces?",
    "It works on my machine!",
    "Have you tried turning it off?",
    "Bug? Or feature?",
    "Rubber duck me!",
    "Commit early, commit often.",
    "Less talk, more code.",
    "Inbox zero, maybe?",
    "Plan, then do.",
    "Small wins count.",
    "Procrastination later!",
    "I believe in you.",
    "Touch grass soon!",
    "Posture check!",
    "Are we there yet?",
    "Mmm, pixels.",
    "I'm watching you.",
    "Don't give up!",
    "Make it happen!",
    "Today is the day!",
    "Crush that to-do list!",
    "Boop! Now work.",
    "Stay hungry, stay foolish.",
]


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
    def __init__(self, display_rects, bounds):
        self.set_desktop(display_rects, bounds)
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

    def set_desktop(self, display_rects, bounds):
        self.displays = display_rects
        self.bounds = bounds
        self.min_x, self.min_y, self.max_x, self.max_y = bounds

    def _ground_platforms(self):
        """One ground platform per display, merging adjacent same-height edges.

        Each display's ground is its bottom edge in global coordinates.
        Contiguous displays at the same bottom Y are merged so the pet can
        walk seamlessly across them; displays of differing heights keep their
        own ground so the pet falls between them naturally.
        """
        intervals = [
            [d["x"], d["x"] + d["w"], d["y"] + d["h"]] for d in self.displays
        ]
        intervals.sort(key=lambda item: (item[2], item[0]))
        merged = []
        for left, right, y in intervals:
            if merged and merged[-1][2] == y and left <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], right)
            else:
                merged.append([left, right, y])

        grounds = []
        for index, (left, right, y) in enumerate(merged):
            grounds.append(
                {
                    "id": f"desktop:{index}",
                    "base_id": f"desktop:{index}",
                    "x": left,
                    "y": y,
                    "w": right - left,
                    "h": 1,
                    "name": GROUND_PLATFORM_NAME,
                    "edge": "ground",
                }
            )
        return grounds

    def platforms(self):
        platforms = self._ground_platforms()

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
        left = int(max(self.min_x, x))
        right = int(min(self.max_x, x + w))
        px = left
        pw = right - left
        py = int(y)
        ph = int(h)
        if pw < WINDOW_W:
            return None
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
        floor = self.max_y - 24
        if MIN_PLATFORM_Y + self.min_y <= top_y <= floor:
            platforms.extend(
                self._edge_platforms(window, "top", top_y, occluders)
            )
        if MIN_PLATFORM_Y + self.min_y <= bottom_y <= floor:
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
    def __init__(self, width, height, interactive=True):
        self.width = width
        self.height = height
        self.interactive = interactive
        self.objc = _objc_setup()
        self.cg = self._load_core_graphics()
        self.colorspace = self.cg.CGColorSpaceCreateDeviceRGB()
        self.nsapp = None
        self.status_item = None
        self.window = None
        self.layer = None
        self.last_buffer = None
        self.level = self.cg.CGWindowLevelForKey(CG_WINDOW_LEVEL_ASSISTIVE_TECH_HIGH)
        self.dragging = False
        self.drag_offset = NSPoint(0, 0)
        self.drag_position = None
        self.drag_released = False
        self.press_origin = None
        self.press_moved = False
        self.pending_clicks = 0
        self._seen_visible = False

        # Multi-monitor state, populated by refresh_displays().
        self.display_rects = []
        self.bounds = (0, 0, self.width, self.height)
        self.main_height = self.height
        self.refresh_displays()

        self._create_window()

    def _resource_path(self, filename):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(getattr(sys, "_MEIPASS"), filename)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

    def _load_core_graphics(self):
        cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreGraphics"))
        cg.CGMainDisplayID.restype = ctypes.c_uint32
        cg.CGDisplayBounds.restype = CGRect
        cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
        cg.CGGetActiveDisplayList.restype = ctypes.c_int
        cg.CGGetActiveDisplayList.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        ]
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
        _msg(
            objc,
            self.window,
            "setIgnoresMouseEvents:",
            not self.interactive,
            argtypes=[ctypes.c_bool],
        )
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
        if self.interactive:
            self._create_status_menu()

    def _create_status_menu(self):
        objc = self.objc
        NSStatusBar = objc.objc_getClass(b"NSStatusBar")
        NSMenu = objc.objc_getClass(b"NSMenu")
        NSMenuItem = objc.objc_getClass(b"NSMenuItem")
        NSImage = objc.objc_getClass(b"NSImage")

        status_bar = _msg(objc, NSStatusBar, "systemStatusBar")
        self.status_item = _msg(
            objc,
            status_bar,
            "statusItemWithLength:",
            NS_STATUS_ITEM_VARIABLE_LENGTH,
            argtypes=[ctypes.c_double],
        )

        button = _msg(objc, self.status_item, "button")
        icon_path = self._resource_path("sprite.png")
        icon_loaded = False

        symbol_image = _msg(
            objc,
            NSImage,
            "imageWithSystemSymbolName:accessibilityDescription:",
            _nsstring(objc, "pawprint.fill"),
            _nsstring(objc, "Desktop Pet"),
            argtypes=[ctypes.c_void_p, ctypes.c_void_p],
        )
        if symbol_image:
            _msg(objc, symbol_image, "setSize:", NSSize(MENU_ICON_SIZE, MENU_ICON_SIZE), argtypes=[NSSize])
            _msg(objc, symbol_image, "setTemplate:", False, argtypes=[ctypes.c_bool])
            _msg(objc, button, "setImage:", symbol_image, argtypes=[ctypes.c_void_p])
            icon_loaded = True

        if os.path.exists(icon_path):
            image = _msg(objc, NSImage, "alloc")
            image = _msg(
                objc,
                image,
                "initWithContentsOfFile:",
                _nsstring(objc, icon_path),
                argtypes=[ctypes.c_void_p],
            )
            if image:
                _msg(objc, image, "setSize:", NSSize(MENU_ICON_SIZE, MENU_ICON_SIZE), argtypes=[NSSize])
                _msg(objc, button, "setImage:", image, argtypes=[ctypes.c_void_p])
                icon_loaded = True

        title = _nsstring(objc, "" if icon_loaded else "Pet")
        tooltip = _nsstring(objc, "Desktop Pet")
        _msg(objc, button, "setTitle:", title, argtypes=[ctypes.c_void_p])
        _msg(objc, button, "setToolTip:", tooltip, argtypes=[ctypes.c_void_p])

        menu = _msg(objc, NSMenu, "alloc")
        menu = _msg(objc, menu, "init")
        _msg(objc, menu, "setAutoenablesItems:", False, argtypes=[ctypes.c_bool])
        quit_item = _msg(objc, NSMenuItem, "alloc")
        quit_item = _msg(
            objc,
            quit_item,
            "initWithTitle:action:keyEquivalent:",
            _nsstring(objc, "Quit Desktop Pet"),
            objc.sel_registerName(b"orderOut:"),
            _nsstring(objc, "q"),
            argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p],
        )
        _msg(objc, quit_item, "setTarget:", self.window, argtypes=[ctypes.c_void_p])
        _msg(objc, quit_item, "setEnabled:", True, argtypes=[ctypes.c_bool])
        _msg(objc, menu, "addItem:", quit_item, argtypes=[ctypes.c_void_p])
        _msg(objc, self.status_item, "setMenu:", menu, argtypes=[ctypes.c_void_p])

    def should_quit(self):
        window_visible = _msg(self.objc, self.window, "isVisible", restype=ctypes.c_bool)
        if window_visible:
            self._seen_visible = True
            return False
        return self._seen_visible

    def screen_bounds(self):
        bounds = self.cg.CGDisplayBounds(self.cg.CGMainDisplayID())
        return int(bounds.x), int(bounds.y), int(bounds.w), int(bounds.h)

    def display_bounds(self):
        """Return every active display's frame in the global CG space.

        Coordinates may be negative: the main display's top-left is the origin
        and other monitors are placed relative to it however the user (or a
        display manager) has arranged them.
        """
        max_displays = 32
        count = ctypes.c_uint32(0)
        ids = (ctypes.c_uint32 * max_displays)()
        rects = []
        if self.cg.CGGetActiveDisplayList(max_displays, ids, ctypes.byref(count)) == 0:
            for i in range(count.value):
                bounds = self.cg.CGDisplayBounds(ids[i])
                if bounds.w <= 0 or bounds.h <= 0:
                    continue
                rects.append(
                    {
                        "x": int(bounds.x),
                        "y": int(bounds.y),
                        "w": int(bounds.w),
                        "h": int(bounds.h),
                    }
                )
        if not rects:
            x, y, w, h = self.screen_bounds()
            rects.append({"x": x, "y": y, "w": w, "h": h})
        return rects

    def refresh_displays(self):
        """Re-scan displays so hot-plugging / rearranging monitors works live."""
        rects = self.display_bounds()
        min_x = min(d["x"] for d in rects)
        min_y = min(d["y"] for d in rects)
        max_x = max(d["x"] + d["w"] for d in rects)
        max_y = max(d["y"] + d["h"] for d in rects)
        self.display_rects = rects
        self.bounds = (min_x, min_y, max_x, max_y)
        self.main_height = int(self.cg.CGDisplayBounds(self.cg.CGMainDisplayID()).h)
        return self.display_rects, self.bounds

    def reassert_top(self):
        _msg(self.objc, self.window, "setLevel:", self.level, argtypes=[ctypes.c_long])
        _msg(self.objc, self.window, "orderFrontRegardless")

    def move(self, x, y):
        flipped_y = self.main_height - y - self.height
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
        NSEvent = self.objc.objc_getClass(b"NSEvent")
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
                if not self._handle_mouse_event(event, NSEvent):
                    _msg(self.objc, self.nsapp, "sendEvent:", event)
        _msg(self.objc, self.nsapp, "updateWindows")

    def _handle_mouse_event(self, event, NSEvent):
        event_type = _msg(self.objc, event, "type", restype=ctypes.c_ulong)
        if event_type == NSEVENT_LEFT_MOUSE_DOWN:
            self.dragging = True
            self.drag_released = False
            self.drag_offset = _msg(
                self.objc,
                event,
                "locationInWindow",
                restype=NSPoint,
            )
            self.drag_position = self._drag_top_left(NSEvent)
            self.press_origin = self.drag_position
            self.press_moved = False
            return True
        if event_type == NSEVENT_LEFT_MOUSE_DRAGGED and self.dragging:
            self.drag_position = self._drag_top_left(NSEvent)
            if self.press_origin:
                dx = self.drag_position[0] - self.press_origin[0]
                dy = self.drag_position[1] - self.press_origin[1]
                if dx * dx + dy * dy > CLICK_MOVE_THRESHOLD ** 2:
                    self.press_moved = True
            return True
        if event_type == NSEVENT_LEFT_MOUSE_UP and self.dragging:
            self.drag_position = self._drag_top_left(NSEvent)
            self.dragging = False
            if self.press_moved:
                self.drag_released = True
            else:
                self.pending_clicks += 1
            return True
        return False

    def mouse_position(self):
        """Current cursor location in global CG coordinates (top-left origin)."""
        NSEvent = self.objc.objc_getClass(b"NSEvent")
        mouse = _msg(self.objc, NSEvent, "mouseLocation", restype=NSPoint)
        return (mouse.x, self.main_height - mouse.y)

    def _drag_top_left(self, NSEvent):
        mouse = _msg(self.objc, NSEvent, "mouseLocation", restype=NSPoint)
        min_x, min_y, max_x, max_y = self.bounds
        x = mouse.x - self.drag_offset.x
        y = self.main_height - (mouse.y - self.drag_offset.y) - self.height
        x = max(min_x, min(max_x - self.width, x))
        y = max(min_y - self.height * 2, min(max_y - self.height, y))
        return x, y

    def consume_drag_state(self):
        state = {
            "dragging": self.dragging,
            "position": self.drag_position,
            "released": self.drag_released,
            "moved": self.press_moved,
            "clicks": self.pending_clicks,
        }
        self.drag_released = False
        self.pending_clicks = 0
        return state


class Pet:
    def __init__(self, bounds):
        self.set_bounds(bounds)
        self.x = float((self.min_x + self.max_x) // 2)
        self.y = float((self.min_y + self.max_y) // 2)
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
        self.talking = False
        self.speech_text = ""
        self.speech_timer = 0
        self.speech_cooldown = random.randint(120, 600)
        self.speech_dirty = False
        self.speech_surface = None
        self.speech_tail_up = False
        self.following = False
        self.follow_timer = 0
        self.particles = []
        self.idle_fx_timer = random.randint(IDLE_FX_MIN, IDLE_FX_MAX)
        self.anger = 0.0
        self.angry = False
        self.angry_timer = 0
        self.pick_state()

    def set_bounds(self, bounds):
        """Update the roamable area to the union of all displays.

        screen_w / screen_h stay as the *span* of the whole desktop so the
        jump-reachability heuristics keep working across monitors.
        """
        self.min_x, self.min_y, self.max_x, self.max_y = bounds
        self.screen_w = self.max_x - self.min_x
        self.screen_h = self.max_y - self.min_y

    def start_talk(self, text):
        self.talking = True
        self.speech_text = text
        self.speech_dirty = True
        self.speech_surface = None
        self.speech_timer = max(SPEECH_MIN_FRAMES, len(text) * SPEECH_PER_CHAR)
        self.state = State.IDLE
        self.vx = 0.0
        self.vy = 0.0

    def _maybe_talk(self):
        if self.speech_cooldown > 0:
            return
        if self.state not in (State.IDLE, State.WALK):
            return
        if random.random() > SPEAK_CHANCE:
            return
        self.start_talk(random.choice(PHRASES))

    def _update_talking(self):
        """Keep the pet planted while a bubble is up. Returns True if the rest
        of update() should be skipped this frame."""
        self.speech_timer -= 1
        if self.airborne:
            self._stop_talking(repick=False)
            return False
        if self.speech_timer <= 0:
            self._stop_talking(repick=True)
            return False
        self.state = State.IDLE
        self.vx = 0.0
        self.vy = 0.0
        if self.platform and self._feet_inside_platform(self.platform):
            self.y = self.platform["y"] - WINDOW_H
        return True

    def _stop_talking(self, repick):
        self.talking = False
        self.speech_text = ""
        self.speech_surface = None
        self.speech_dirty = False
        self.speech_cooldown = random.randint(SPEAK_COOLDOWN_MIN, SPEAK_COOLDOWN_MAX)
        if repick and not self.airborne:
            self.pick_state()

    # -- Particles ---------------------------------------------------------

    def spawn_particles(self, kind, count):
        head_x = self.x + WINDOW_W * 0.5
        for _ in range(count):
            if len(self.particles) >= MAX_PARTICLES:
                break
            life = random.randint(42, 66)
            self.particles.append(
                {
                    "kind": kind,
                    "x": head_x + random.uniform(-9, 9),
                    "y": self.y + random.uniform(-3, 7),
                    "vx": random.uniform(-0.7, 0.7),
                    "vy": random.uniform(-1.8, -0.9),
                    "life": life,
                    "maxlife": life,
                }
            )

    def _update_particles(self):
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.02
            p["life"] -= 1
        if self.particles:
            self.particles = [p for p in self.particles if p["life"] > 0]

    def _maybe_idle_fx(self):
        self.idle_fx_timer -= 1
        if self.idle_fx_timer > 0:
            return
        self.idle_fx_timer = random.randint(IDLE_FX_MIN, IDLE_FX_MAX)
        if not self.angry and not self.airborne:
            self.spawn_particles(random.choice(["heart", "star"]), 1)

    # -- Mouse interaction -------------------------------------------------

    def on_click(self, clicks, mouse=None):
        """React to taps: hearts when calm, anger after a few quick pokes."""
        for _ in range(clicks):
            if self.angry:
                self.spawn_particles("anger", random.randint(2, 3))
            else:
                self.spawn_particles("heart", random.randint(1, 2))
        self.anger += clicks
        if not self.angry and self.anger >= ANGRY_THRESHOLD:
            self._become_angry()

    def _become_angry(self):
        self.angry = True
        self.angry_timer = ANGRY_DURATION
        self.following = False
        self.spawn_particles("anger", 5)
        self.start_talk(random.choice(ANGRY_PHRASES))

    def _update_anger(self):
        self.anger = max(0.0, self.anger - ANGER_DECAY)
        if self.angry:
            self.angry_timer -= 1
            if self.angry_timer <= 0 and self.anger < 1.0:
                self.angry = False

    def _maybe_follow_mouse(self, mouse):
        if self.angry or self.following:
            return
        if self.state not in (State.IDLE, State.WALK):
            return
        if abs(mouse[0] - self._feet_x()) < FOLLOW_STOP_DISTANCE * 2:
            return
        if random.random() > FOLLOW_CHANCE:
            return
        self.following = True
        self.follow_timer = random.randint(120, 300)

    def _update_follow(self, mouse):
        if mouse is None or self.airborne or self.angry:
            self.following = False
            return
        self.follow_timer -= 1
        dx = mouse[0] - self._feet_x()
        if abs(dx) < FOLLOW_STOP_DISTANCE or self.follow_timer <= 0:
            reached = abs(dx) < FOLLOW_STOP_DISTANCE + 4
            self.following = False
            self.vx = 0.0
            self.state = State.IDLE
            self.state_timer = random.randint(40, 90)
            if reached:
                self.spawn_particles("heart", 1)
            return
        direction = 1 if dx > 0 else -1
        speed = 2.4 if abs(dx) > FOLLOW_RUN_DISTANCE else 1.0
        self.vx = direction * speed
        self.state = State.RUN if speed > 1.6 else State.WALK
        self.state_timer = 30

    def pick_state(self):
        r = random.random()
        if r < 0.50:
            self.state = State.WALK
            speed = random.uniform(0.35, 1.05)
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * speed
            self.vy = random.uniform(-0.12, 0.12)
            self.state_timer = random.randint(160, 420)
        elif r < 0.90:
            self.state = State.IDLE
            self.vx = 0.0
            self.vy = 0.0
            self.state_timer = random.randint(120, 360)
        elif r < 1.0 - RANDOM_JUMP_STATE_CHANCE:
            self.state = State.RUN
            speed = random.uniform(1.8, 3.0)
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * speed
            self.vy = random.uniform(-0.18, 0.18)
            self.state_timer = random.randint(30, 75)
        else:
            if self.jump_cooldown > 0:
                self.state = State.WALK
                self.vx = random.choice([-1, 1]) * random.uniform(0.35, 1.05)
                self.vy = random.uniform(-0.12, 0.12)
                self.state_timer = random.randint(120, 260)
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
            clearance = TARGET_JUMP_EXTRA_HEIGHT
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

    def update(self, platforms, mouse=None):
        self.frame += 1
        self.state_timer -= 1
        self.jump_cooldown = max(0, self.jump_cooldown - 1)
        self.speech_cooldown = max(0, self.speech_cooldown - 1)
        self._update_face()
        self._update_particles()
        self._update_anger()
        self._maybe_idle_fx()

        if self.talking and self._update_talking():
            return

        if not self.talking and not self.airborne and self.state != State.JUMP:
            self._maybe_talk()
            if self.talking:
                return

        if self.following:
            self._update_follow(mouse)
        elif mouse is not None and not self.airborne and self.state != State.JUMP:
            self._maybe_follow_mouse(mouse)

        if not self.following and not self.airborne and self.state != State.JUMP:
            if not self._maybe_drop_through_platform():
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

        if self.x < self.min_x:
            self.x = self.min_x
            self.vx = abs(self.vx)
            self.facing_right = True
        elif self.x + WINDOW_W > self.max_x:
            self.x = self.max_x - WINDOW_W
            self.vx = -abs(self.vx)
            self.facing_right = False

        if self.y + WINDOW_H > self.max_y:
            self.y = self.max_y - WINDOW_H
            self.airborne = False
            self.platform = self._ground_under_feet(platforms)
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

    def drag_to(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.jump_vy = 0.0
        self.airborne = False
        self.platform = None
        self.jump_target = None
        self.state = State.IDLE
        self.state_timer = 60
        self.following = False
        if self.talking:
            self._stop_talking(repick=False)

    def drop(self):
        self.airborne = True
        self.platform = None
        self.jump_target = None
        self.state = State.JUMP
        self.jump_vy = 0.0
        self.jump_cooldown = 30
        self.following = False

    def _maybe_drop_through_platform(self):
        if self.jump_cooldown > 0:
            return False
        if self.state not in (State.IDLE, State.WALK):
            return False
        if not self.platform or self.platform["name"] == GROUND_PLATFORM_NAME:
            return False
        if random.random() > PLATFORM_DROP_CHANCE:
            return False

        direction = 1 if self.facing_right else -1
        if abs(self.vx) < 0.2:
            self.vx = direction * random.uniform(0.25, 0.8)
        self.y += 3
        self.airborne = True
        self.platform = None
        self.jump_target = None
        self.state = State.JUMP
        self.jump_vy = 1.2
        self.jump_cooldown = 45
        return True

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

    def _ground_under_feet(self, platforms):
        foot = self._feet_x()
        grounds = [
            platform
            for platform in platforms
            if platform["name"] == GROUND_PLATFORM_NAME
            and platform["x"] <= foot <= platform["x"] + platform["w"]
        ]
        if grounds:
            return min(grounds, key=lambda item: item["y"])
        return platforms[0] if platforms else None

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


# Hand-rolled 5x7 pixel font (SDL_ttf is unavailable on this Python build, and
# a bitmap font keeps the retro look and the bundle dependency-free). Text is
# upper-cased before rendering. Unknown glyphs fall back to "?".
GLYPH_W = 5
GLYPH_H = 7
SPACE_W = 3
GLYPH_GAP = 1
LINE_GAP = 2

FONT_5x7 = {
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ####", "#    ", "#    ", "#  ##", "#   #", "#   #", " ####"],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "J": ["#####", "    #", "    #", "    #", "#   #", "#   #", " ### "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "# # #", "#  ##", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "!": ["  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "],
    "?": [" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "],
    ".": ["     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "],
    ",": ["     ", "     ", "     ", "     ", " ##  ", " ##  ", "#    "],
    "'": ["  #  ", "  #  ", "  #  ", "     ", "     ", "     ", "     "],
    "-": ["     ", "     ", "     ", "#####", "     ", "     ", "     "],
    ":": ["     ", " ##  ", " ##  ", "     ", " ##  ", " ##  ", "     "],
}


def _char_width(ch):
    if ch == " ":
        return SPACE_W
    return GLYPH_W


def _text_width(text):
    width = 0
    for ch in text:
        width += _char_width(ch) + GLYPH_GAP
    return max(0, width - GLYPH_GAP)


def _wrap_lines(text, max_w):
    lines = []
    current = ""
    for word in text.split():
        trial = word if not current else current + " " + word
        if _text_width(trial) <= max_w or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def render_pixel_text(text, color):
    text = text.upper()
    width = max(1, _text_width(text))
    surface = pygame.Surface((width, GLYPH_H), pygame.SRCALPHA)
    surface.fill(CLEAR)
    x = 0
    for ch in text:
        if ch == " ":
            x += SPACE_W + GLYPH_GAP
            continue
        glyph = FONT_5x7.get(ch, FONT_5x7["?"])
        for row, line in enumerate(glyph):
            for col, cell in enumerate(line):
                if cell == "#":
                    surface.set_at((x + col, row), color)
        x += GLYPH_W + GLYPH_GAP
    return surface


def draw_speech_bubble(text, tail_up=False):
    """Render a pixel speech bubble: cream box, dark border, and a tail that
    points down at the pet (default) or up at it (when the pet is near the top
    of the screen and the bubble sits below it)."""
    lines = _wrap_lines(text, BUBBLE_MAX_TEXT_W)
    rendered = [render_pixel_text(line, BUBBLE_TEXT_COLOR) for line in lines]
    line_h = GLYPH_H + LINE_GAP
    text_w = max(s.get_width() for s in rendered)
    text_h = line_h * len(rendered) - LINE_GAP

    pad = 3
    border = 1
    tail_h = 4
    tail_w = 8
    body_w = text_w + pad * 2 + border * 2
    body_h = text_h + pad * 2 + border * 2
    body_top = tail_h if tail_up else 0
    base = pygame.Surface((body_w, body_h + tail_h), pygame.SRCALPHA)
    base.fill(CLEAR)

    body = pygame.Rect(0, body_top, body_w, body_h)
    pygame.draw.rect(base, BUBBLE_TEXT_COLOR, body)
    pygame.draw.rect(
        base,
        BUBBLE_FILL_COLOR,
        pygame.Rect(border, body_top + border, body_w - border * 2, body_h - border * 2),
    )
    # Trim the four corner pixels for a softly rounded pixel edge.
    for corner in [
        (0, body_top),
        (body_w - 1, body_top),
        (0, body_top + body_h - 1),
        (body_w - 1, body_top + body_h - 1),
    ]:
        base.set_at(corner, CLEAR)

    for i, surface in enumerate(rendered):
        x = border + pad + (text_w - surface.get_width()) // 2
        base.blit(surface, (x, body_top + border + pad + i * line_h))

    cx = body_w // 2
    if tail_up:
        # Tail at the top, apex pointing up.
        pygame.draw.polygon(
            base,
            BUBBLE_TEXT_COLOR,
            [(cx - tail_w // 2, tail_h), (cx + tail_w // 2, tail_h), (cx, 0)],
        )
        pygame.draw.polygon(
            base,
            BUBBLE_FILL_COLOR,
            [(cx - tail_w // 2 + 1, tail_h + 1), (cx + tail_w // 2 - 1, tail_h + 1), (cx, 2)],
        )
    else:
        # Tail at the bottom, apex pointing down.
        pygame.draw.polygon(
            base,
            BUBBLE_TEXT_COLOR,
            [(cx - tail_w // 2, body_h - 1), (cx + tail_w // 2, body_h - 1), (cx, body_h - 1 + tail_h)],
        )
        pygame.draw.polygon(
            base,
            BUBBLE_FILL_COLOR,
            [(cx - tail_w // 2 + 1, body_h - 2), (cx + tail_w // 2 - 1, body_h - 2), (cx, body_h - 3 + tail_h)],
        )

    return pygame.transform.scale(
        base, (base.get_width() * BUBBLE_SCALE, base.get_height() * BUBBLE_SCALE)
    )


# Pixel particle sprites, built lazily after pygame is initialised.
HEART_PIXELS = [
    " ## ## ",
    "#######",
    "#######",
    " ##### ",
    "  ###  ",
    "   #   ",
]
STAR_PIXELS = [
    "   #   ",
    "   #   ",
    "## # ##",
    " ##### ",
    "  ###  ",
    " ## ## ",
    "##   ##",
]
PARTICLE_PIXELS = {
    "heart": (HEART_PIXELS, HEART_COLOR),
    "star": (STAR_PIXELS, STAR_COLOR),
    "anger": (STAR_PIXELS, ANGER_COLOR),
}
_PARTICLE_CACHE = {}


def particle_sprite(kind):
    sprite = _PARTICLE_CACHE.get(kind)
    if sprite is None:
        pattern, color = PARTICLE_PIXELS[kind]
        h = len(pattern)
        w = len(pattern[0])
        base = pygame.Surface((w, h), pygame.SRCALPHA)
        base.fill(CLEAR)
        for y, row in enumerate(pattern):
            for x, cell in enumerate(row):
                if cell == "#":
                    base.set_at((x, y), color)
        sprite = pygame.transform.scale(base, (w * PARTICLE_SCALE, h * PARTICLE_SCALE))
        _PARTICLE_CACHE[kind] = sprite
    return sprite


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

    if pet.angry:
        # Slanted brows (high on the outside, low toward the nose).
        px(small, left_eye_x - 1, eye_y - 2, EYE_COLOR)
        px(small, left_eye_x, eye_y - 1, EYE_COLOR)
        px(small, right_eye_x + 1, eye_y - 2, EYE_COLOR)
        px(small, right_eye_x, eye_y - 1, EYE_COLOR)

    mouth_y = body_y + 7
    if pet.angry:
        # Downturned frown.
        px(small, 8, mouth_y + 1, EYE_COLOR)
        px(small, 9, mouth_y, EYE_COLOR)
        px(small, 10, mouth_y, EYE_COLOR)
        px(small, 11, mouth_y, EYE_COLOR)
        px(small, 12, mouth_y + 1, EYE_COLOR)
    elif pet.state == State.RUN:
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
    fx = MacOverlay(FX_W, FX_H, interactive=False)
    display_rects, bounds = overlay.refresh_displays()
    window_tracker = WindowTracker(display_rects, bounds)
    platforms = window_tracker.platforms()
    pet = Pet(bounds)
    pet.place_on_best_platform(platforms)
    canvas = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    fx_canvas = pygame.Surface((FX_W, FX_H), pygame.SRCALPHA)
    clock = pygame.time.Clock()
    last_reassert = 0.0
    last_window_scan = 0.0
    fx_visible = False

    while running:
        now = time.monotonic()
        overlay.pump_events()
        if overlay.should_quit():
            running = False
            continue
        drag = overlay.consume_drag_state()
        mouse = overlay.mouse_position()

        if now - last_window_scan > 0.75:
            display_rects, bounds = overlay.refresh_displays()
            window_tracker.set_desktop(display_rects, bounds)
            pet.set_bounds(bounds)
            platforms = window_tracker.platforms()
            if not pet.airborne:
                pet.sync_platforms(platforms)
            last_window_scan = now

        if drag["moved"] and drag["position"]:
            pet.drag_to(*drag["position"])
        if drag["released"] and drag["moved"]:
            pet.drop()
        if drag["clicks"]:
            pet.on_click(drag["clicks"], mouse)

        if not drag["dragging"]:
            pet.update(platforms, mouse)

        canvas.fill(CLEAR)
        canvas.blit(draw_pet_frame(pet), (0, 0))

        overlay.move(round(pet.x), round(pet.y))
        overlay.show_surface(canvas)

        if pet.talking or pet.particles:
            origin_x = round(pet.x + WINDOW_W / 2 - FX_W / 2)
            origin_y = round(pet.y + WINDOW_H / 2 - FX_H / 2)
            fx_canvas.fill(CLEAR)

            for p in pet.particles:
                sprite = particle_sprite(p["kind"])
                sprite.set_alpha(int(255 * max(0.0, min(1.0, p["life"] / p["maxlife"]))))
                fx_canvas.blit(
                    sprite,
                    (
                        round(p["x"] - origin_x - sprite.get_width() / 2),
                        round(p["y"] - origin_y - sprite.get_height() / 2),
                    ),
                )

            if pet.talking:
                if pet.speech_dirty or pet.speech_surface is None:
                    surf = draw_speech_bubble(pet.speech_text)
                    if pet.y - surf.get_height() < pet.min_y + 4:
                        surf = draw_speech_bubble(pet.speech_text, tail_up=True)
                        pet.speech_tail_up = True
                    else:
                        pet.speech_tail_up = False
                    pet.speech_surface = surf
                    pet.speech_dirty = False
                surf = pet.speech_surface
                bx = (FX_W - surf.get_width()) // 2
                if pet.speech_tail_up:
                    by = round(pet.y + WINDOW_H - origin_y - BUBBLE_GAP)
                else:
                    by = round(pet.y - origin_y - surf.get_height() + BUBBLE_GAP)
                fx_canvas.blit(surf, (bx, by))

            fx.move(origin_x, origin_y)
            fx.show_surface(fx_canvas)
            fx_visible = True
        elif fx_visible:
            fx_canvas.fill(CLEAR)
            fx.show_surface(fx_canvas)
            fx_visible = False

        if now - last_reassert > 0.5:
            overlay.reassert_top()
            fx.reassert_top()
            last_reassert = now

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
