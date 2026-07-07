"""Tests fuer die Plattform-Geometrie des WindowTrackers.

platforms() selbst fragt Core Graphics ab und braucht AppKit; die reine Geometrie
(Fenster-Rects -> begehbare Kanten, Verdeckung, Boden pro Display) liegt aber in
den Helfern _ground_platforms/_platforms_from_window/_edge_platforms/
_subtract_interval. Wir instanziieren den Tracker ohne __init__ (kein AppKit) und
testen nur diese Logik.
"""

from config import GROUND_PLATFORM_NAME, WINDOW_H, WINDOW_W
from window_tracker import WindowTracker

BOUNDS = (0, 0, 1440, 900)
DISPLAYS = [{"x": 0, "y": 0, "w": 1440, "h": 900}]


def make_tracker(displays=DISPLAYS, bounds=BOUNDS):
    # __new__ umgeht __init__ (das AppKit/CoreGraphics laedt); wir setzen nur die
    # Desktop-Geometrie, die die reinen Helfer brauchen.
    tracker = WindowTracker.__new__(WindowTracker)
    tracker.set_desktop(displays, bounds)
    return tracker


def window(wid, x, y, w, h, name="Window"):
    return {"id": wid, "x": x, "y": y, "w": w, "h": h, "name": name}


def test_ground_platform_per_display():
    tracker = make_tracker()
    grounds = tracker._ground_platforms()
    assert len(grounds) == 1
    g = grounds[0]
    assert g["name"] == GROUND_PLATFORM_NAME
    assert g["y"] == 900
    assert g["x"] == 0
    assert g["w"] == 1440


def test_two_displays_same_height_merge():
    tracker = make_tracker(
        displays=[
            {"x": 0, "y": 0, "w": 1440, "h": 900},
            {"x": 1440, "y": 0, "w": 1440, "h": 900},
        ],
        bounds=(0, 0, 2880, 900),
    )
    grounds = tracker._ground_platforms()
    assert len(grounds) == 1
    assert grounds[0]["w"] == 2880


def test_two_displays_different_height_stay_separate():
    tracker = make_tracker(
        displays=[
            {"x": 0, "y": 0, "w": 1440, "h": 900},
            {"x": 1440, "y": 0, "w": 1440, "h": 1080},
        ],
        bounds=(0, 0, 2880, 1080),
    )
    grounds = tracker._ground_platforms()
    assert len(grounds) == 2


def test_window_yields_top_and_bottom_edges():
    tracker = make_tracker()
    win = window(1, 200, 300, 400, 250)
    platforms = tracker._platforms_from_window(win, [])
    edges = {p["edge"] for p in platforms}
    assert edges == {"top", "bottom"}
    top = next(p for p in platforms if p["edge"] == "top")
    assert top["y"] == 300
    assert top["x"] == 200
    assert top["w"] == 400


def test_occluder_subtracts_hidden_edge():
    tracker = make_tracker()
    back = window(1, 100, 400, 600, 200)
    # Ein Fenster genau davor auf gleicher Kanten-Hoehe schneidet ein Stueck heraus.
    front = window(2, 300, 350, 200, 300)
    platforms = tracker._edge_platforms(back, "top", 400, [front])
    # Es bleiben Segmente links und/oder rechts, aber keines ueberdeckt 300..500.
    for p in platforms:
        assert not (p["x"] < 500 and p["x"] + p["w"] > 300)


def test_fully_occluded_edge_disappears():
    tracker = make_tracker()
    back = window(1, 300, 400, 200, 200)
    front = window(2, 100, 350, 700, 300)  # deckt die ganze Kante ab
    platforms = tracker._edge_platforms(back, "top", 400, [front])
    assert platforms == []


def test_offscreen_window_clamped_to_bounds():
    tracker = make_tracker()
    # Fenster ragt links aus dem Bildschirm; die Kante wird auf min_x geklemmt.
    win = window(1, -100, 300, 500, 200)
    win["x"] = max(BOUNDS[0], -100)  # so wie _window_from_info klemmt
    platforms = tracker._platforms_from_window(win, [])
    for p in platforms:
        assert p["x"] >= BOUNDS[0]


def test_subtract_interval_splits_and_trims():
    tracker = make_tracker()
    # Schnitt in der Mitte splittet in zwei Segmente.
    assert tracker._subtract_interval([(0, 100)], 40, 60) == [(0, 40), (60, 100)]
    # Schnitt am Rand trimmt nur.
    assert tracker._subtract_interval([(0, 100)], 0, 30) == [(30, 100)]
    # Kein Ueberlapp laesst das Segment unveraendert.
    assert tracker._subtract_interval([(0, 100)], 200, 300) == [(0, 100)]
    # Vollstaendige Ueberdeckung loescht das Segment.
    assert tracker._subtract_interval([(0, 100)], -10, 200) == []


def test_narrow_segment_below_min_width_dropped():
    tracker = make_tracker()
    # Ein Fenster schmaler als die Mindestbreite ergibt keine Plattform.
    narrow = window(1, 200, 300, WINDOW_W, 200)
    platforms = tracker._edge_platforms(narrow, "top", 300, [])
    assert platforms == []
