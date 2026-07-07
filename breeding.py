"""Vererbungs-Wahrscheinlichkeiten fuer Farbe und Waffe beim Zeugen.

Ein Kind erbt jede Eigenschaft mit PARENT_SHARE von Elternteil A bzw. B; mit
MUTATION-Restwahrscheinlichkeit mutiert sie zu einem zufaelligen Wert aus dem
ganzen Pool. Haben beide Eltern denselben Wert, addiert sich der Anteil.

Preview (Panel) und tatsaechliche Zeugung (make_baby) nutzen dieselben
Funktionen, damit die angezeigten Wahrscheinlichkeiten stimmen.
"""

import random

from config import PALETTES, WEAPONS

PARENT_SHARE = 0.45      # je Elternteil
MUTATION = 0.10          # Rest: zufaellige Mutation ueber den ganzen Pool


def _distribution(a_val, b_val, options):
    dist = {o: 0.0 for o in options}
    dist[a_val] += PARENT_SHARE
    dist[b_val] += PARENT_SHARE
    share = MUTATION / len(options)
    for o in options:
        dist[o] += share
    return dist


def color_distribution(a_index, b_index):
    """palette_index -> Wahrscheinlichkeit."""
    return _distribution(a_index, b_index, list(range(len(PALETTES))))


def weapon_distribution(a_weapon, b_weapon):
    """Waffe -> Wahrscheinlichkeit."""
    return _distribution(a_weapon, b_weapon, list(WEAPONS))


def _sample(dist):
    roll = random.random()
    acc = 0.0
    for key, prob in dist.items():
        acc += prob
        if roll <= acc:
            return key
    return next(reversed(dist))


def choose_color(a_index, b_index):
    return _sample(color_distribution(a_index, b_index))


def choose_weapon(a_weapon, b_weapon):
    return _sample(weapon_distribution(a_weapon, b_weapon))
