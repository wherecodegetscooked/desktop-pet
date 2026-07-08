"""Tests fuer die neutralen Sozial-Interaktionen: Nacht-Erkennung, spontane
Begruessung und Nacht-Kuscheln. Reine Logik, kein Display."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import config
import pet as pet_mod
from pet import Pet, State, is_night

BOUNDS = (0, 0, 1440, 900)


def make_pet(x=200, y=800):
    p = Pet(BOUNDS)
    p.x, p.y = float(x), float(y)
    p.state = State.IDLE
    p.airborne = False  # geerdet: __init__ kann RNG-abhaengig in der Luft starten
    return p


def center(p):
    return (p.x + config.WINDOW_W / 2, p.y + config.WINDOW_H / 2)


def test_is_night_wraps_midnight():
    assert is_night(23) is True
    assert is_night(0) is True
    assert is_night(5) is True
    assert is_night(6) is False
    assert is_night(12) is False
    assert is_night(22) is False


def test_greet_triggers_when_peer_is_near(monkeypatch):
    monkeypatch.setattr(pet_mod.random, "random", lambda: 0.0)
    p = make_pet()
    cx, cy = center(p)
    p.observe_peers([(cx + 20, cy)])
    assert p._maybe_greet() is True
    assert p.greet_pause == config.GREET_PAUSE
    assert p.greet_cooldown == config.GREET_COOLDOWN
    assert any(part["kind"] == "greet" for part in p.particles)


def test_greet_skipped_when_peer_too_far(monkeypatch):
    monkeypatch.setattr(pet_mod.random, "random", lambda: 0.0)
    p = make_pet()
    cx, cy = center(p)
    p.observe_peers([(cx + config.GREET_DISTANCE + 50, cy)])
    assert p._maybe_greet() is False


def test_greet_blocked_by_cooldown(monkeypatch):
    monkeypatch.setattr(pet_mod.random, "random", lambda: 0.0)
    p = make_pet()
    cx, cy = center(p)
    p.observe_peers([(cx + 20, cy)])
    p.greet_cooldown = 5
    assert p._maybe_greet() is False


def test_angry_pet_does_not_greet(monkeypatch):
    monkeypatch.setattr(pet_mod.random, "random", lambda: 0.0)
    p = make_pet()
    p.angry = True
    cx, cy = center(p)
    p.observe_peers([(cx + 20, cy)])
    assert p._maybe_greet() is False


def test_night_huddle_only_at_night(monkeypatch):
    monkeypatch.setattr(pet_mod.random, "random", lambda: 0.0)
    p = make_pet()
    p.idle_seconds = config.BORED_SECONDS + 1
    cx, cy = center(p)
    p.observe_peers([(cx + 120, cy)])

    monkeypatch.setattr(pet_mod, "_current_hour", lambda: 12)
    assert p._maybe_night_huddle() is False

    monkeypatch.setattr(pet_mod, "_current_hour", lambda: 2)
    assert p._maybe_night_huddle() is True
    assert p.huddling is True


def test_night_huddle_needs_quiet_machine(monkeypatch):
    monkeypatch.setattr(pet_mod.random, "random", lambda: 0.0)
    monkeypatch.setattr(pet_mod, "_current_hour", lambda: 2)
    p = make_pet()
    p.idle_seconds = 0.0  # gerade aktiv genutzt
    cx, cy = center(p)
    p.observe_peers([(cx + 120, cy)])
    assert p._maybe_night_huddle() is False


def test_huddle_walks_and_falls_asleep(monkeypatch):
    monkeypatch.setattr(pet_mod, "_current_hour", lambda: 2)
    p = make_pet(x=200, y=BOUNDS[3] - config.WINDOW_H)
    p.huddling = True
    p.huddle_target_x = 260.0
    p.observe_peers([(260.0, p.y + config.WINDOW_H / 2)])
    for _ in range(200):
        p._update_huddle()
        if p.asleep:
            break
    assert p.asleep is True
    assert p.huddle_sleep is True
    assert p.huddling is False


def test_huddle_sleep_wakes_on_input():
    p = make_pet()
    p.asleep = True
    p.huddle_sleep = True
    # Frische Eingabe (idle_seconds klein) weckt den Kuschelschlaf auf.
    p.observe_activity(0.0, 0)
    assert p.asleep is False
    assert p.huddle_sleep is False


def test_huddle_sleep_persists_while_idle():
    p = make_pet()
    p.asleep = True
    p.huddle_sleep = True
    # Weiter ruhig (unter AFK-Schwelle) — der Kuschelschlaf haelt.
    p.observe_activity(10.0, 0)
    assert p.asleep is True
    assert p.huddle_sleep is True
