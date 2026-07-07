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
