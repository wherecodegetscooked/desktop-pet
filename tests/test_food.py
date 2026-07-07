"""Tests fuer den Snack (food.Snack) und das Ess-Verhalten des Pets.

Reine Logik, kein Display: der Pet laeuft zum Snack, isst und bekommt danach
Love- und Happy-Boost. SDL im Dummy-Modus, damit Pet importierbar ist."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import config
from food import Snack


BOUNDS = (0, 0, 1440, 900)


def make_pet(x, y):
    from pet import Pet

    p = Pet(BOUNDS)
    p.x, p.y = float(x), float(y)
    return p


def run_until_eaten(pet, snack, max_frames=600):
    for i in range(max_frames):
        pet.update([])
        if snack.eaten:
            return i
    return None


def test_snack_starts_uneaten_and_unclaimed():
    s = Snack(100, 800)
    assert s.eaten is False
    assert s.claimed() is False


def test_wants_snack_only_when_calm_and_near_level():
    pet = make_pet(200, 800)
    near = Snack(300, 800 + config.WINDOW_H / 2)
    assert pet.wants_snack(near) is True
    # Weit unter dem Pet -> ausser vertikaler Reichweite.
    far_below = Snack(300, 800 + config.SNACK_REACH_HEIGHT + 200)
    assert pet.wants_snack(far_below) is False


def test_angry_pet_ignores_snack():
    pet = make_pet(200, 800)
    pet.angry = True
    assert pet.wants_snack(Snack(300, 800 + config.WINDOW_H / 2)) is False


def test_claimed_pet_not_offered_again():
    pet = make_pet(200, 800)
    s = Snack(300, 800 + config.WINDOW_H / 2)
    pet.send_to_snack(s)
    s.claimed_by = pet
    assert s.claimed() is True
    # Solange der Pet den Snack als Ziel hat, will er keinen zweiten annehmen.
    assert pet.wants_snack(s) is False


def test_pet_walks_over_and_eats():
    pet = make_pet(200, 830)
    pet.y = BOUNDS[3] - config.WINDOW_H  # auf dem Boden
    s = Snack(320, pet.y + config.WINDOW_H / 2)
    pet.send_to_snack(s)
    frames = run_until_eaten(pet, s)
    assert frames is not None
    assert s.eaten is True
    assert pet.snack_target is None


def test_eating_boosts_love_and_happy():
    pet = make_pet(260, BOUNDS[3] - config.WINDOW_H)
    s = Snack(280, pet.y + config.WINDOW_H / 2)
    love_before = pet.love
    pet.send_to_snack(s)
    run_until_eaten(pet, s)
    assert pet.love >= love_before + config.SNACK_LOVE_BOOST - 0.01
    assert pet.happy_timer == config.HAPPY_DURATION


def test_happy_timer_counts_down():
    pet = make_pet(260, BOUNDS[3] - config.WINDOW_H)
    s = Snack(280, pet.y + config.WINDOW_H / 2)
    pet.send_to_snack(s)
    run_until_eaten(pet, s)
    start = pet.happy_timer
    pet.update([])
    assert pet.happy_timer == start - 1
