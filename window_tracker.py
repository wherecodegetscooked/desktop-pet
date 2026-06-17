"""Detect on-screen windows and turn their edges into walkable platforms.

`WindowTracker` queries Core Graphics for the current on-screen windows and
exposes their top/bottom edges (plus one ground platform per display) as
rectangles the pet can stand and jump on. Edges occluded by windows in front
are subtracted out so the pet never stands on a hidden ledge.
"""

import ctypes
import ctypes.util

from config import (
    GROUND_PLATFORM_NAME,
    MIN_PLATFORM_Y,
    WINDOW_H,
    WINDOW_LIST_EXCLUDE_DESKTOP,
    WINDOW_LIST_ON_SCREEN_ONLY,
    WINDOW_W,
)
from objc_bridge import (
    _msg,
    _nsnumber_double,
    _nsnumber_int,
    _nsstring,
    _nsstring_text,
    _objc_setup,
)


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
