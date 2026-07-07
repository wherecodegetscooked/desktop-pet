"""Tests fuer die App-Klassifikation (activity.classify / needs_title).

Reine Lookup-Logik ohne AppKit: Bundle-ID bzw. App-Name -> Mood. Deckt die
Bundle-Listen, die Namens-Fallbacks in _matches() und die Audio-/Fokus-Gates ab.
"""

import activity


def test_focus_wins_over_everything():
    # Eine laufende Fokus-Sitzung schlaegt jede App-Erkennung.
    assert activity.classify("com.valvesoftware.steam", "Steam", "", True, True) == "work"
    assert activity.classify(None, "Netflix", "", True, True) == "work"


def test_work_bundle_and_name_hint():
    assert activity.classify("com.microsoft.VSCode", "Code", "", False, False) == "work"
    # Unbekannte Bundle-ID, aber der Name-Hint "pycharm" greift.
    assert activity.classify("com.unknown.ide", "PyCharm 2024", "", False, False) == "work"


def test_video_only_with_audio():
    # Video zaehlt nur, wenn wirklich Ton laeuft (pausiertes Video -> kein Popcorn).
    assert activity.classify("org.videolan.vlc", "VLC", "", False, True) == "video"
    assert activity.classify("org.videolan.vlc", "VLC", "", False, False) is None


def test_call_only_with_audio():
    assert activity.classify("us.zoom.xos", "zoom.us", "", False, True) == "call"
    assert activity.classify("us.zoom.xos", "zoom.us", "", False, False) is None


def test_gaming_ignores_audio():
    assert activity.classify("com.valvesoftware.steam", "Steam", "", False, False) == "gaming"
    assert activity.classify(None, "Minecraft", "", False, False) == "gaming"


def test_browser_video_tab_needs_audio_and_title():
    # YouTube-Tab im Browser: nur mit Ton als Video erkannt.
    assert activity.classify(
        "com.apple.Safari", "Safari", "Cats - YouTube", False, True
    ) == "video"
    assert activity.classify(
        "com.apple.Safari", "Safari", "Cats - YouTube", False, False
    ) is None
    # Gewoehnliches Surfen ohne Video-Keyword bleibt None.
    assert activity.classify(
        "com.apple.Safari", "Safari", "Wikipedia", False, True
    ) is None


def test_browser_call_tab_beats_video():
    assert activity.classify(
        "com.google.Chrome", "Chrome", "Google Meet", False, True
    ) == "call"


def test_plain_app_is_none():
    assert activity.classify("com.apple.finder", "Finder", "", False, False) is None
    assert activity.classify(None, "", "", False, False) is None


def test_needs_title_only_for_browsers():
    assert activity.needs_title("com.apple.Safari", "Safari") is True
    assert activity.needs_title("com.unknown", "Arc") is True
    assert activity.needs_title("com.microsoft.VSCode", "Code") is False


def test_matches_handles_missing_bundle_and_name():
    assert activity._matches(None, None, activity.WORK_BUNDLES, activity.WORK_NAME_HINTS) is False
    assert activity._matches("", "vim", set(), ("vim",)) is True
