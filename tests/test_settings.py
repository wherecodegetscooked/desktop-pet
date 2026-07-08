"""Tests fuer das Prefs-Schema und das Einstellungsfenster (Logik-Teil).

Kein Fenster/ObjC: das Panel ist als reine Surface-/Layout-Logik testbar.
"""

import json
import os

import pytest

import config


def test_every_pref_key_is_a_config_attribute():
    for key in config.PREFS_FIELDS:
        assert hasattr(config, key), key


def test_defaults_lie_within_declared_range():
    for key, field in config.PREFS_FIELDS.items():
        val = getattr(config, key)
        if field["type"] == "bool":
            assert isinstance(val, bool)
        else:
            assert field["min"] <= val <= field["max"], key


def test_pref_ok_rejects_bool_in_number_and_out_of_range():
    intf = config.PREFS_FIELDS["MAX_PETS"]
    assert config._pref_ok(intf, 4)
    assert not config._pref_ok(intf, True)      # bool nie in int-Feld
    assert not config._pref_ok(intf, 999)       # ausserhalb Range
    assert not config._pref_ok(intf, 2.5)       # kein Ganzzahlwert
    boolf = config.PREFS_FIELDS["RAGE_ENABLED"]
    assert config._pref_ok(boolf, False)
    assert not config._pref_ok(boolf, 1)        # int nie in bool-Feld


def test_panel_save_writes_valid_prefs(tmp_path, monkeypatch):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    import persistence
    import settings_panel

    monkeypatch.setattr(persistence, "state_dir", lambda: str(tmp_path))
    monkeypatch.setattr(persistence, "prefs_path",
                        lambda: str(tmp_path / "prefs.json"))

    panel = settings_panel.SettingsPanel()
    panel.save()

    data = json.loads((tmp_path / "prefs.json").read_text(encoding="utf-8"))
    # Jeder geschriebene Wert muss die config-Validierung bestehen.
    for key, field in config.PREFS_FIELDS.items():
        assert key in data
        assert config._pref_ok(field, data[key]), (key, data[key])


def _pets_panel(n):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.init()
    import settings_panel

    panel = settings_panel.SettingsPanel()
    panel.tab = "Pets"
    panel.pets = [{"id": i, "uid": i, "name": f"P{i}", "palette_index": 0,
                   "generation": 0, "baby": False, "weapon": "knife"}
                  for i in range(n)]
    return panel


def test_pet_scroll_advances_and_clamps():
    panel = _pets_panel(8)                 # 8 Pets, 5 Zeilen -> max Offset 3
    assert panel._max_pet_scroll() == 3
    step = panel.SCROLL_PX_PER_ROW
    # Nach unten scrollen (negatives scrollingDeltaY) -> spaetere Pets.
    panel.on_scroll((100, 200), -step)
    assert panel.pet_scroll == 1
    panel.on_scroll((100, 200), -step * 5)  # weit ueber das Ende hinaus
    assert panel.pet_scroll == 3            # geklemmt
    # Zurueck nach oben.
    panel.on_scroll((100, 200), step * 10)
    assert panel.pet_scroll == 0


def test_pet_scroll_noop_when_all_fit():
    panel = _pets_panel(3)                  # passt komplett -> kein Scrollen
    assert panel._max_pet_scroll() == 0
    assert panel.on_scroll((100, 200), -panel.SCROLL_PX_PER_ROW * 3) is False
    assert panel.pet_scroll == 0


def test_pet_scroll_only_on_pets_tab():
    panel = _pets_panel(8)
    panel.tab = "Allgemein"
    assert panel.on_scroll((100, 200), -panel.SCROLL_PX_PER_ROW) is False
    assert panel.pet_scroll == 0


def test_visible_pet_widgets_follow_scroll():
    panel = _pets_panel(8)
    panel.pet_scroll = 2
    panel._build_widgets()
    sel_ids = [w["pet_id"] for w in panel._widgets if w["kind"] == "select"]
    # Genau die 5 sichtbaren Zeilen ab Offset 2 sind interaktiv.
    assert sel_ids == [2, 3, 4, 5, 6]
