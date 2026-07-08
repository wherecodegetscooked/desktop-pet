"""Tests fuer die reine Stammbaum-Logik (Verwandtschaft, eindeutige Namen)."""

import random

import lineage


def fam(pets):
    """Kleines Familienregister bauen: {uid: parents-Liste}."""
    return {uid: {"name": f"P{uid}", "generation": 0, "parents": parents}
            for uid, parents in pets.items()}


def test_ancestors_walks_all_generations():
    # 5 = Kind von 3 und 4; 3 = Kind von 1 und 2.
    family = {
        1: {"parents": []},
        2: {"parents": []},
        3: {"parents": [1, 2]},
        4: {"parents": []},
        5: {"parents": [3, 4]},
    }
    assert lineage.ancestors(5, family) == {1, 2, 3, 4}
    assert lineage.ancestors(3, family) == {1, 2}
    assert lineage.ancestors(1, family) == set()


def test_ancestors_survives_cycle():
    # Kaputter Zustand mit Zyklus darf nicht in Endlosschleife laufen.
    family = {1: {"parents": [2]}, 2: {"parents": [1]}}
    assert lineage.ancestors(1, family) == {1, 2}


def test_same_pet_is_related():
    family = fam({1: []})
    assert lineage.are_related(1, 1, family) is True


def test_parent_child_related():
    family = {1: {"parents": []}, 2: {"parents": [1]}}
    assert lineage.are_related(1, 2, family) is True
    assert lineage.are_related(2, 1, family) is True


def test_siblings_related():
    # 2 und 3 teilen sich Elternteil 1 -> Geschwister.
    family = {1: {"parents": []}, 2: {"parents": [1]}, 3: {"parents": [1]}}
    assert lineage.are_related(2, 3, family) is True


def test_grandparent_related():
    family = {1: {"parents": []}, 2: {"parents": [1]}, 3: {"parents": [2]}}
    assert lineage.are_related(1, 3, family) is True


def test_unrelated_pets():
    family = {1: {"parents": []}, 2: {"parents": []}}
    assert lineage.are_related(1, 2, family) is False


def test_cousins_are_not_related():
    # 1 und 2 sind Wurzeln; 3=Kind(1), 4=Kind(2); 5=Kind(3), 6=Kind(4).
    # 5 und 6 sind Cousins — kein gemeinsamer Elternteil, keiner Vorfahre.
    family = {
        1: {"parents": []}, 2: {"parents": []},
        3: {"parents": [1]}, 4: {"parents": [2]},
        5: {"parents": [3]}, 6: {"parents": [4]},
    }
    assert lineage.are_related(5, 6, family) is False


def test_unique_name_prefers_free_pool():
    rng = random.Random(1)
    pool = ["Pixel", "Mochi", "Bean"]
    name = lineage.unique_name({"Pixel", "Mochi"}, pool, rng)
    assert name == "Bean"


def test_unique_name_appends_counter_when_pool_exhausted():
    rng = random.Random(1)
    pool = ["Pixel"]
    name = lineage.unique_name({"Pixel"}, pool, rng)
    assert name == "Pixel 2"
    name2 = lineage.unique_name({"Pixel", "Pixel 2"}, pool, rng)
    assert name2 == "Pixel 3"
