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
    CG_ANY_INPUT_EVENT_TYPE,
    CG_EVENT_KEY_DOWN,
    CG_EVENT_SOURCE_STATE_HID,
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
    WINDOW_LIST_EXCLUDE_DESKTOP,
    WINDOW_LIST_ON_SCREEN_ONLY,
)
from updater import current_version
from objc_bridge import (
    CGRect,
    NSPoint,
    NSRect,
    NSSize,
    _msg,
    _nsnumber_int,
    _nsstring,
    _nsstring_text,
    _objc_setup,
)


class MacOverlay:
    def __init__(self, width, height, interactive=True, with_menu=False):
        self.width = width
        self.height = height
        self.interactive = interactive
        self.with_menu = with_menu
        # Filled by the status-bar menu callbacks; drained by consume_menu_actions.
        self.menu_actions = []
        self.menu_controller = None
        self._menu_imps = []
        self.objc = _objc_setup()
        self.cg = self._load_core_graphics()
        self.cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        self.cf.CFRelease.argtypes = [ctypes.c_void_p]
        # NSString keys for reading the frontmost window's title (app-awareness).
        self._win_keys = {
            name: _nsstring(self.objc, name)
            for name in ("kCGWindowLayer", "kCGWindowName", "kCGWindowOwnerName")
        }
        # Whether Screen Recording is already granted (needed to read window
        # titles). We never prompt for it — see ensure_screen_recording.
        self._screen_recording_ok = False
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
        # Cursor warp, for the enraged pet flinging the mouse pointer away.
        cg.CGWarpMouseCursorPosition.restype = ctypes.c_int
        cg.CGWarpMouseCursorPosition.argtypes = [NSPoint]
        # Window list, for reading the frontmost window's title (app-awareness).
        cg.CGWindowListCopyWindowInfo.restype = ctypes.c_void_p
        cg.CGWindowListCopyWindowInfo.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        # Screen Recording gate: window titles are only readable with it granted
        # (10.15+). We only ever preflight (never request), so we bind just the
        # preflight symbol; it may be absent on older macOS, hence the guard.
        if hasattr(cg, "CGPreflightScreenCaptureAccess"):
            cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        # Input-activity queries for AFK sleep and typing energy.
        cg.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
        cg.CGEventSourceSecondsSinceLastEventType.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
        cg.CGEventSourceCounterForEventType.restype = ctypes.c_uint32
        cg.CGEventSourceCounterForEventType.argtypes = [
            ctypes.c_uint32,
            ctypes.c_uint32,
        ]
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
        if self.with_menu:
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

        self._create_menu_controller()

        menu = _msg(objc, NSMenu, "alloc")
        menu = _msg(objc, menu, "init")
        _msg(objc, menu, "setAutoenablesItems:", False, argtypes=[ctypes.c_bool])

        self._add_menu_item(
            menu, "Start Focus (25 min)", "f", self.menu_controller, b"startFocus:"
        )
        self._add_menu_item(
            menu, "Stop Focus", "s", self.menu_controller, b"stopFocus:"
        )
        _msg(objc, menu, "addItem:", _msg(objc, NSMenuItem, "separatorItem"))
        self._add_menu_item(
            menu, "Toss a ball", "t", self.menu_controller, b"tossBall:"
        )
        self._add_menu_item(
            menu, "Remove ball", "", self.menu_controller, b"removeBall:"
        )
        self._add_menu_item(menu, "Recolour", "c", self.menu_controller, b"recolour:")
        self._add_menu_item(menu, "Rename", "n", self.menu_controller, b"renamePet:")
        _msg(objc, menu, "addItem:", _msg(objc, NSMenuItem, "separatorItem"))
        self._add_menu_item(
            menu, "Breed", "b", self.menu_controller, b"breed:"
        )
        self._add_menu_item(
            menu, "New pet", "p", self.menu_controller, b"newPet:"
        )
        self._add_menu_item(
            menu, "Remove a pet", "r", self.menu_controller, b"removeDup:"
        )
        self._add_menu_item(
            menu, "Remove all pets…", "", self.menu_controller, b"removeAll:"
        )
        _msg(objc, menu, "addItem:", _msg(objc, NSMenuItem, "separatorItem"))
        self._add_menu_item(
            menu, "Check for updates…", "u", self.menu_controller, b"updateApp:"
        )
        _msg(objc, menu, "addItem:", _msg(objc, NSMenuItem, "separatorItem"))
        # Quit hides this primary window; the run loop notices and shuts down.
        self._add_menu_item(menu, "Quit Desktop Pet", "q", self.window, b"orderOut:")

        # A disabled label at the very bottom showing this build's version.
        _msg(objc, menu, "addItem:", _msg(objc, NSMenuItem, "separatorItem"))
        version_item = _msg(objc, NSMenuItem, "alloc")
        version_item = _msg(
            objc,
            version_item,
            "initWithTitle:action:keyEquivalent:",
            _nsstring(objc, f"v{current_version()}"),
            None,
            _nsstring(objc, ""),
            argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p],
        )
        _msg(objc, version_item, "setEnabled:", False, argtypes=[ctypes.c_bool])
        _msg(objc, menu, "addItem:", version_item, argtypes=[ctypes.c_void_p])

        _msg(objc, self.status_item, "setMenu:", menu, argtypes=[ctypes.c_void_p])

    def _add_menu_item(self, menu, title, key, target, action_sel):
        objc = self.objc
        NSMenuItem = objc.objc_getClass(b"NSMenuItem")
        item = _msg(objc, NSMenuItem, "alloc")
        item = _msg(
            objc,
            item,
            "initWithTitle:action:keyEquivalent:",
            _nsstring(objc, title),
            objc.sel_registerName(action_sel),
            _nsstring(objc, key),
            argtypes=[ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p],
        )
        _msg(objc, item, "setTarget:", target, argtypes=[ctypes.c_void_p])
        _msg(objc, item, "setEnabled:", True, argtypes=[ctypes.c_bool])
        _msg(objc, menu, "addItem:", item, argtypes=[ctypes.c_void_p])
        return item

    def _create_menu_controller(self):
        """Build a tiny Objective-C class at runtime whose action methods push
        onto self.menu_actions, so menu-bar clicks reach Python."""
        objc = self.objc
        objc.objc_allocateClassPair.restype = ctypes.c_void_p
        objc.objc_allocateClassPair.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        objc.objc_registerClassPair.argtypes = [ctypes.c_void_p]
        objc.class_addMethod.restype = ctypes.c_bool
        objc.class_addMethod.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_char_p,
        ]

        NSObject = objc.objc_getClass(b"NSObject")
        name = f"DesktopPetMenu_{id(self)}".encode()
        cls = objc.objc_allocateClassPair(NSObject, name, 0)

        imp_type = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )
        actions = self.menu_actions

        def make_imp(action):
            def handler(_self, _cmd, _sender):
                actions.append(action)

            return imp_type(handler)

        for sel_name, action in (
            (b"breed:", "breed"),
            (b"newPet:", "new_pet"),
            (b"removeDup:", "remove"),
            (b"removeAll:", "remove_all"),
            (b"startFocus:", "focus_start"),
            (b"stopFocus:", "focus_stop"),
            (b"tossBall:", "ball"),
            (b"removeBall:", "ball_remove"),
            (b"recolour:", "recolour"),
            (b"renamePet:", "rename"),
            (b"updateApp:", "update"),
        ):
            imp = make_imp(action)
            self._menu_imps.append(imp)  # keep callbacks alive
            objc.class_addMethod(
                cls,
                objc.sel_registerName(sel_name),
                ctypes.cast(imp, ctypes.c_void_p),
                b"v@:@",
            )

        objc.objc_registerClassPair(cls)
        self.menu_controller = _msg(objc, cls, "new")

    def consume_menu_actions(self):
        actions = self.menu_actions[:]
        self.menu_actions.clear()
        return actions

    def close(self):
        """Hide this overlay's window (used when a bred pet is removed)."""
        _msg(self.objc, self.window, "orderOut:", None)

    def set_mouse_ignore(self, ignore):
        """Toggle click-through. Used to park the menu-owning window when it has
        no pet to host, so it doesn't swallow clicks in empty space, then make it
        interactive again when reused for a new pet."""
        _msg(
            self.objc,
            self.window,
            "setIgnoresMouseEvents:",
            bool(ignore),
            argtypes=[ctypes.c_bool],
        )

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
        # Genau eine Kopie: tobytes liefert das fertige BGRA/premultiplied-Layout.
        # Das bytes-Objekt geht direkt als Datenpointer an CGDataProviderCreateWithData
        # (c_void_p akzeptiert bytes); die frühere zweite from_buffer_copy-Kopie
        # entfaellt. self.last_buffer haelt den Puffer am Leben, bis der naechste
        # Frame ihn ersetzt (die Layer-Contents referenzieren ihn bis dahin).
        pixels = pygame.image.tobytes(surface, "BGRA")
        provider = self.cg.CGDataProviderCreateWithData(None, pixels, len(pixels), None)
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
        self.last_buffer = pixels

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

    def seconds_since_input(self):
        """Seconds since the last keyboard or mouse event, system-wide. Used to
        decide when the pet should doze off. Needs no accessibility permission."""
        return float(
            self.cg.CGEventSourceSecondsSinceLastEventType(
                CG_EVENT_SOURCE_STATE_HID, CG_ANY_INPUT_EVENT_TYPE
            )
        )

    def keydown_count(self):
        """Cumulative count of keydown events for this login session. Polled each
        frame; the per-frame delta is how fast the human is typing."""
        return int(
            self.cg.CGEventSourceCounterForEventType(
                CG_EVENT_SOURCE_STATE_HID, CG_EVENT_KEY_DOWN
            )
        )

    def mouse_position(self):
        """Current cursor location in global CG coordinates (top-left origin)."""
        NSEvent = self.objc.objc_getClass(b"NSEvent")
        mouse = _msg(self.objc, NSEvent, "mouseLocation", restype=NSPoint)
        return (mouse.x, self.main_height - mouse.y)

    def warp_cursor(self, x, y):
        """Teleport the mouse pointer to a global-display point (top-left
        origin, the same space the pet lives in). Used by the enraged pet to
        fling the cursor away. Needs no accessibility permission."""
        self.cg.CGWarpMouseCursorPosition(NSPoint(float(x), float(y)))

    def frontmost_app(self):
        """(bundle_id, localized_name) of the frontmost application, or two
        empty strings. Needs no special permission."""
        objc = self.objc
        NSWorkspace = objc.objc_getClass(b"NSWorkspace")
        ws = _msg(objc, NSWorkspace, "sharedWorkspace")
        app = _msg(objc, ws, "frontmostApplication")
        if not app:
            return "", ""
        bundle = _nsstring_text(objc, _msg(objc, app, "bundleIdentifier"))
        name = _nsstring_text(objc, _msg(objc, app, "localizedName"))
        return bundle, name

    def ensure_screen_recording(self):
        """Check (never prompt) whether Screen Recording is granted, which is
        what lets us read window titles to spot a YouTube/Meet tab in a browser.

        We deliberately do NOT call CGRequestScreenCaptureAccess: that modal is
        intrusive and macOS re-triggers it after every update (the resigned
        binary loses its TCC grant). Browser-tab detection is a minor nicety, so
        it stays fully opt-in — the user can grant Screen Recording in System
        Settings if they want it, and it takes effect on the next launch. Native
        video/call apps and audio detection work without any of this.

        Returns True if already granted (or pre-10.15, where titles are free).
        """
        preflight = getattr(self.cg, "CGPreflightScreenCaptureAccess", None)
        if preflight is None:
            self._screen_recording_ok = True  # pre-10.15: titles readable freely
            return True
        self._screen_recording_ok = bool(preflight())
        return self._screen_recording_ok

    def active_window_title(self, owner_name=""):
        """Title of the frontmost normal (layer-0) on-screen window, or "".

        When `owner_name` is given (the frontmost app's name), prefer that app's
        window — so we read the focused browser's tab title rather than whatever
        window happens to sort on top — and fall back to the topmost window's
        title if none matches. Reading titles needs Screen Recording permission
        on macOS 10.15+; without it we skip the peek entirely so we never touch a
        screen-capture API (which could re-arm the system prompt).
        """
        if not self._screen_recording_ok:
            return ""
        options = WINDOW_LIST_ON_SCREEN_ONLY | WINDOW_LIST_EXCLUDE_DESKTOP
        array = self.cg.CGWindowListCopyWindowInfo(options, 0)
        if not array:
            return ""
        try:
            count = _msg(self.objc, array, "count", restype=ctypes.c_ulong)
            fallback = ""
            for i in range(count):
                info = _msg(
                    self.objc, array, "objectAtIndex:", i, argtypes=[ctypes.c_ulong]
                )
                layer = _nsnumber_int(
                    self.objc,
                    _msg(self.objc, info, "objectForKey:", self._win_keys["kCGWindowLayer"]),
                )
                if layer != 0:
                    continue  # skip menubar, our own high-level panels, etc.
                title = _nsstring_text(
                    self.objc,
                    _msg(self.objc, info, "objectForKey:", self._win_keys["kCGWindowName"]),
                )
                if not owner_name:
                    return title
                owner = _nsstring_text(
                    self.objc,
                    _msg(self.objc, info, "objectForKey:", self._win_keys["kCGWindowOwnerName"]),
                )
                if owner == owner_name and title:
                    return title
                if not fallback:
                    fallback = title
            return fallback
        finally:
            self.cf.CFRelease(array)

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
