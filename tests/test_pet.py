"""Tests der reinen State-Machine-Logik in pet.py.

Bewusst kein Rendering/ObjC/Overlay: ein Pet ist ohne Fenster instanziierbar
(nur config + stdlib). Getestet werden Anger/Rage-Uebergaenge, das Wachstum
eines Babys, die Vererbung beim Zeugen, die Death-Timeline und die
Mood-Prioritaet.
"""

import random

import pytest

import config
from pet import Pet, State


BOUNDS = (0, 0, 1440, 900)


@pytest.fixture
def pet():
    """Ein frischer Pet mit neutralem Temperament (anger/social = 1.0), damit
    die Schwellen deterministisch und ohne Personality-Skalierung greifen."""
    p = Pet(BOUNDS)
    p.personality = {t: 1.0 for t in config.PERSONALITY_TRAITS}
    p.personality["name"] = "Calm"
    return p


# -- Anger / Rage -----------------------------------------------------------

def test_clicks_below_threshold_stay_calm(pet):
    pet.on_click(2)
    assert pet.anger == pytest.approx(2.0)
    assert not pet.angry
    assert not pet.rage


def test_clicks_reach_angry_threshold(pet):
    pet.on_click(config.ANGRY_THRESHOLD)
    assert pet.angry
    assert not pet.rage
    assert pet.angry_timer == config.ANGRY_DURATION
    assert not pet.following
    assert not pet.loved


def test_clicks_reach_rage_threshold_arms_weapon(pet):
    pref = pet.weapon_pref
    pet.on_click(config.RAGE_THRESHOLD)
    assert pet.rage
    assert pet.angry  # Rage impliziert weiter Aerger
    assert pet.weapon == pref  # greift zur Lieblingswaffe
    assert pet.rage_timer == config.RAGE_DURATION


def test_become_rage_resets_combat_timeline(pet):
    # Combat-Zustand vorher "verschmutzen", danach muss _reset_combat aufraeumen.
    pet.combat_phase = "strike"
    pet.hits_landed = 3
    pet.flying = True
    pet._become_rage()
    assert pet.combat_phase is None
    assert pet.hits_landed == 0
    assert pet.attack_cooldown == 18
    assert not pet.flying


def test_anger_decays_each_frame(pet):
    pet.anger = 2.0
    pet._update_mood()
    assert pet.anger == pytest.approx(2.0 - config.ANGER_DECAY)


def test_angry_clears_when_timer_and_anger_run_out(pet):
    pet.angry = True
    pet.angry_timer = 1
    pet.anger = 0.5  # unter 1.0
    pet._update_mood()
    assert not pet.angry


def test_petting_soothes_anger(pet):
    pet.anger = 2.0
    pet._on_pet()
    assert pet.anger == pytest.approx(2.0 - config.PET_STROKE_CALM)
    assert pet.love == pytest.approx(config.PET_STROKE_LOVE)


# -- Growth -----------------------------------------------------------------

def test_baby_stays_tiny_during_delay(pet):
    pet.baby = True
    pet.growth = 0.0
    pet.baby_age = 0
    pet._update_growth()
    assert pet.baby_age == 1
    assert pet.growth == 0.0
    assert pet.baby


def test_baby_grows_after_delay(pet):
    pet.baby = True
    pet.growth = 0.0
    pet.baby_age = config.BABY_GROW_DELAY  # +1 im Aufruf -> knapp ueber der Schwelle
    pet._update_growth()
    assert 0.0 < pet.growth < 1.0
    assert pet.baby


def test_baby_becomes_adult_at_full_growth(pet):
    pet.baby = True
    pet.growth = 0.0
    pet.baby_age = config.BABY_GROW_DELAY + config.BABY_GROW_FRAMES + 10
    pet._update_growth()
    assert pet.growth == 1.0
    assert not pet.baby


def test_non_baby_growth_is_noop(pet):
    pet.baby = False
    pet.baby_age = 0
    pet.growth = 1.0
    pet._update_growth()
    assert pet.baby_age == 0
    assert pet.growth == 1.0


# -- Vererbung / Zeugung ----------------------------------------------------

def test_inherit_personality_blends_within_mutation_band():
    child = Pet(BOUNDS)
    a = {t: 1.0 for t in config.PERSONALITY_TRAITS}
    b = {t: 2.0 for t in config.PERSONALITY_TRAITS}
    a["name"], b["name"] = "Lazy", "Hyper"
    child.inherit_personality(a, b)
    for trait in config.PERSONALITY_TRAITS:
        avg = (a[trait] + b[trait]) / 2  # 1.5
        # Mutation liegt in [0.85, 1.15]; kleine Toleranz fuer die Rundung.
        assert avg * 0.85 - 0.01 <= child.personality[trait] <= avg * 1.15 + 0.01
    assert child.personality["name"] in ("Lazy", "Hyper")


def test_make_baby_blends_parents():
    random.seed(1234)
    pa = Pet(BOUNDS)
    pb = Pet(BOUNDS)
    pa.palette_index, pa.palette = 0, config.PALETTES[0]
    pb.palette_index, pb.palette = 3, config.PALETTES[3]
    pa.weapon_pref = "knife"
    pb.weapon_pref = "hammer"
    pa.name, pb.name = "Pixel", "Mochi"

    baby = Pet(BOUNDS)
    baby.make_baby(pa, pb)

    assert baby.baby
    assert baby.growth == 0.0
    assert baby.baby_age == 0
    # Farbe stammt von genau einem Elternteil (Palette + Index passen zusammen).
    assert baby.palette_index in (pa.palette_index, pb.palette_index)
    assert baby.palette in (pa.palette, pb.palette)
    idx = baby.palette_index
    assert baby.palette is config.PALETTES[idx]
    # Waffen-Vorliebe von einem Elternteil.
    assert baby.weapon_pref in (pa.weapon_pref, pb.weapon_pref)
    # Name: entweder frisch aus dem Pool oder ein Eltern-Name mit "Jr"-Suffix.
    assert (
        baby.name in config.PET_NAMES
        or baby.name.endswith(config.BABY_NAME_SUFFIX)
    )


def test_make_baby_name_suffix_uses_parent_name():
    # Deterministisch einen "Jr"-Namen erzwingen: random.random() < 0.5.
    random.seed(0)
    pa = Pet(BOUNDS)
    pb = Pet(BOUNDS)
    pa.name, pb.name = "Pixel", "Mochi"
    names_seen = set()
    for seed in range(50):
        random.seed(seed)
        baby = Pet(BOUNDS)
        baby.make_baby(pa, pb)
        names_seen.add(baby.name)
    jr_names = {n for n in names_seen if n.endswith(config.BABY_NAME_SUFFIX)}
    # Mindestens ein Jr-Name muss vorkommen und auf einem Eltern-Namen basieren.
    assert jr_names
    for n in jr_names:
        base = n[: -len(config.BABY_NAME_SUFFIX)]
        assert base in ("Pixel", "Mochi")


# -- Death-Timeline ---------------------------------------------------------

def test_start_death_sets_timeline(pet):
    pet.rage = True
    pet.weapon = "sword"
    pet.start_death("poof")
    assert pet.dying
    assert not pet.dead
    assert pet.death_kind == "poof"
    assert pet.death_timer == config.DEATH_FRAMES
    assert pet.death_max == config.DEATH_FRAMES
    # Death raeumt Kampf/Bindungen auf.
    assert not pet.rage
    assert pet.weapon is None


def test_death_counts_down_to_dead(pet):
    pet.start_death("poof")
    for _ in range(config.DEATH_FRAMES - 1):
        pet._update_death()
        assert not pet.dead
    pet._update_death()  # letzter Frame
    assert pet.dead


def test_start_death_is_noop_when_already_dying(pet):
    pet.start_death("poof")
    pet.death_timer = 5
    pet.start_death("explosion")
    assert pet.death_kind == "poof"  # unveraendert
    assert pet.death_timer == 5


# -- Mood-Prioritaet --------------------------------------------------------

@pytest.mark.parametrize(
    "flags, expected",
    [
        ({"rage": True, "asleep": True}, "rage"),
        ({"angry": True, "loved": True}, "angry"),
        ({"scared": True, "excited": True}, "scared"),
        ({"victory": True, "bored": True}, "victory"),
        ({"asleep": True, "excited": True}, "asleep"),
        ({"loved": True, "curious": True}, "love"),
        ({"excited": True, "curious": True, "bored": True}, "excited"),
        ({"curious": True, "bored": True}, "curious"),
        ({"bored": True}, "bored"),
        ({}, "neutral"),
    ],
)
def test_mood_priority(pet, flags, expected):
    for name in ("rage", "angry", "scared", "victory", "asleep", "loved",
                 "excited", "curious", "bored"):
        setattr(pet, name, flags.get(name, False))
    assert pet.mood == expected
