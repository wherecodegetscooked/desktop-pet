"""The transparent, always-on-top, click-through macOS overlay window.

`MacOverlay` wraps a borderless `NSPanel` whose layer the pet (or the effects)
are drawn into. It handles window placement across multiple displays, pushing
pygame surfaces to the layer, pumping the AppKit event loop, and tracking
drag/click gestures. A status-bar item with a Quit menu is added for the
interactive (pet) window.
"""

import ctypes
import ctypes.util
import os
import sys

import pygame

from config import (
    CG_WINDOW_LEVEL_ASSISTIVE_TECH_HIGH,
    CLICK_MOVE_THRESHOLD,
    MENU_ICON_SIZE,
    NS_APPLICATION_ACTIVATION_POLICY_ACCESSORY,
    NS_BACKING_STORE_BUFFERED,
    NS_STATUS_ITEM_VARIABLE_LENGTH,
    NS_WINDOW_COLLECTION_CAN_JOIN_ALL_SPACES,
    NS_WINDOW_COLLECTION_FULLSCREEN_AUXILIARY,
    NS_WINDOW_COLLECTION_IGNORES_CYCLE,
    NS_WINDOW_STYLE_BORDERLESS,
    NS_WINDOW_STYLE_NONACTIVATING_PANEL,
    NSEVENT_LEFT_MOUSE_DOWN,
    NSEVENT_LEFT_MOUSE_DRAGGED,
    NSEVENT_LEFT_MOUSE_UP,
)
from objc_bridge import (
    CGRect,
    NSPoint,
    NSRect,
    NSSize,
    _msg,
    _nsstring,
    _objc_setup,
)


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

    def _begin_no_implicit_anim(self):
        """Open a CATransaction with implicit animations disabled so layer
        moves/content swaps apply instantly. Without this, Core Animation
        cross-fades and slides the old contents from the old position, which
        produced a brief 'ghost' bubble in the previous spot."""
        ca = self.objc.objc_getClass(b"CATransaction")
        _msg(self.objc, ca, "begin")
        _msg(self.objc, ca, "setDisableActions:", True, argtypes=[ctypes.c_bool])
        return ca

    def move(self, x, y):
        flipped_y = self.main_height - y - self.height
        ca = self._begin_no_implicit_anim()
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
        _msg(self.objc, ca, "commit")

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
            ca = self._begin_no_implicit_anim()
            _msg(self.objc, self.layer, "setContents:", image)
            _msg(self.objc, ca, "commit")
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
