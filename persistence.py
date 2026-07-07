"""Zustands-Persistenz ueber Neustarts hinweg.

Speichert die lebenden Pets (Name, Palette, Temperament, Position, Abstammung,
Waffen-Vorliebe, Baby-Wachstum) sowie Lifetime-Stats als JSON unter
``~/Library/Application Support/Desktop Pet/state.json``. Beim Start werden die
Pets wiederhergestellt; fehlt die Datei oder ist sie kaputt, faellt alles
defensiv auf das bisherige Verhalten zurueck (eine Exception dringt nie nach
aussen).

Bewusst eine einzige Datei/Struktur, damit Stats (siehe main/stats) und Pets
zusammen liegen und nicht gegenseitig ueberschrieben werden.
"""

import json
import os

from config import PALETTES, PERSONALITY_TRAITS

STATE_VERSION = 1


def state_dir():
    return os.path.expanduser("~/Library/Application Support/Desktop Pet")


def state_path():
    return os.path.join(state_dir(), "state.json")


def pet_to_dict(pet):
    """Die aussehens-/identitaetsbestimmenden Felder eines Pets als JSON-Dict.

    Nur was einen Neustart ueberdauern soll — kein fluechtiger Kampf-/Physik-
    Zustand."""
    data = {
        "name": pet.name,
        "palette_index": pet.palette_index,
        "personality": dict(pet.personality),
        "x": round(float(pet.x), 1),
        "y": round(float(pet.y), 1),
        "weapon_pref": pet.weapon_pref,
        "generation": getattr(pet, "generation", 0),
        "parents": list(getattr(pet, "parents", [])),
    }
    # Baby-Stand nur mitschreiben, wenn er noch klein ist — ein erwachsener Pet
    # startet wieder als Erwachsener.
    if getattr(pet, "baby", False):
        data["baby"] = True
        data["growth"] = round(float(pet.growth), 3)
        data["baby_age"] = int(pet.baby_age)
    return data


def apply_dict(pet, data):
    """Einen gespeicherten Zustand auf einen frischen Pet anwenden. Defensiv:
    fehlende/kaputte Felder lassen den jeweiligen Default stehen."""
    name = data.get("name")
    if isinstance(name, str) and name:
        pet.name = name

    idx = data.get("palette_index")
    if isinstance(idx, int) and 0 <= idx < len(PALETTES):
        pet.palette_index = idx
        pet.palette = PALETTES[idx]

    personality = data.get("personality")
    if isinstance(personality, dict):
        merged = dict(pet.personality)
        for trait in PERSONALITY_TRAITS:
            val = personality.get(trait)
            if isinstance(val, (int, float)):
                merged[trait] = float(val)
        pname = personality.get("name")
        if isinstance(pname, str) and pname:
            merged["name"] = pname
        pet.personality = merged

    weapon = data.get("weapon_pref")
    if isinstance(weapon, str) and weapon:
        pet.weapon_pref = weapon

    gen = data.get("generation")
    if isinstance(gen, int) and gen >= 0:
        pet.generation = gen
    parents = data.get("parents")
    if isinstance(parents, list):
        pet.parents = [p for p in parents if isinstance(p, str)]

    if data.get("baby"):
        pet.baby = True
        growth = data.get("growth")
        pet.growth = float(growth) if isinstance(growth, (int, float)) else 0.0
        pet.growth = min(1.0, max(0.0, pet.growth))
        age = data.get("baby_age")
        pet.baby_age = int(age) if isinstance(age, int) and age >= 0 else 0


def load():
    """Den gespeicherten Zustand als Dict laden. Bei fehlender/korrupter Datei
    ein leeres Dict — nie eine Exception."""
    try:
        with open(state_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def load_pets():
    """Bequemer Zugriff auf die gespeicherte Pet-Liste (immer eine Liste)."""
    pets = load().get("pets")
    return pets if isinstance(pets, list) else []


def save(state):
    """Das komplette Zustands-Dict atomar schreiben (best effort). Fehler werden
    geschluckt — ein misslungenes Speichern darf den Quit nie stoppen."""
    try:
        os.makedirs(state_dir(), exist_ok=True)
        path = state_path()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass
