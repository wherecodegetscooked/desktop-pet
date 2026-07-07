"""Tests fuer das Vererbungs-Wahrscheinlichkeitsmodell."""

import random

import pytest

import breeding
import config


def test_distribution_sums_to_one_and_parents_dominate():
    d = breeding.color_distribution(0, 3)
    assert sum(d.values()) == pytest.approx(1.0)
    assert d[0] == pytest.approx(breeding.PARENT_SHARE + breeding.MUTATION / len(config.PALETTES))
    assert d[3] == pytest.approx(breeding.PARENT_SHARE + breeding.MUTATION / len(config.PALETTES))
    # Eine Nicht-Eltern-Farbe traegt nur den Mutationsanteil.
    assert d[1] == pytest.approx(breeding.MUTATION / len(config.PALETTES))


def test_same_parent_value_stacks():
    d = breeding.weapon_distribution("bow", "bow")
    share = breeding.MUTATION / len(config.WEAPONS)
    assert d["bow"] == pytest.approx(2 * breeding.PARENT_SHARE + share)
    assert sum(d.values()) == pytest.approx(1.0)


def test_samples_land_on_parents_most_of_the_time():
    random.seed(42)
    a, b = 0, 3
    hits = [breeding.choose_color(a, b) for _ in range(2000)]
    on_parent = sum(1 for h in hits if h in (a, b)) / len(hits)
    # ~90% sollten auf einem Elternteil landen (2*45%).
    assert on_parent > 0.82


def test_make_baby_uses_the_model(monkeypatch):
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from pet import Pet

    random.seed(1)
    pa, pb = Pet((0, 0, 1440, 900)), Pet((0, 0, 1440, 900))
    pa.palette_index, pb.palette_index = 0, 3
    pa.weapon_pref, pb.weapon_pref = "knife", "hammer"
    seen_colors = set()
    for seed in range(60):
        random.seed(seed)
        baby = Pet((0, 0, 1440, 900))
        baby.make_baby(pa, pb)
        assert 0 <= baby.palette_index < len(config.PALETTES)
        assert baby.weapon_pref in config.WEAPONS
        assert baby.palette is config.PALETTES[baby.palette_index]
        seen_colors.add(baby.palette_index)
    # Ueber viele Zeugungen dominieren die Elternfarben 0 und 3.
    assert {0, 3} & seen_colors
