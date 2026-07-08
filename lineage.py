"""Reine Stammbaum-Logik: Verwandtschaft und eindeutige Namen.

Das Familienregister ist ``{uid: {"name", "generation", "parents": [uid, ...]}}``.
Jeder Pet hat eine stabile, ueber Neustarts erhaltene ``uid`` — der Name ist rein
kosmetisch und darf sich nie als Identitaet ausgeben (frueher kollidierten
gleiche Namen im Register und zerstoerten den Stammbaum). Alles hier ist frei von
Display/State, damit main.py Inzest verhindern und eindeutige Namen vergeben kann
und Tests die Graph-Auswertung pruefen koennen.
"""


def ancestors(uid, family):
    """Menge aller Vorfahren-uids (Eltern, Grosseltern, …) von ``uid``.

    Zyklensicher (ein kaputter Zustand kann keinen Endlos-Loop ausloesen) und
    ohne ``uid`` selbst im Ergebnis."""
    seen = set()
    stack = list(family.get(uid, {}).get("parents", []))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(family.get(current, {}).get("parents", []))
    return seen


def are_related(a, b, family):
    """Ob ``a`` und ``b`` zu eng verwandt sind, um sie zu verpaaren.

    Verwandt heisst: derselbe Pet, direkte Abstammung (einer ist Vorfahre des
    anderen) oder ein gemeinsamer Elternteil (Geschwister/Halbgeschwister)."""
    if a == b:
        return True
    if b in ancestors(a, family) or a in ancestors(b, family):
        return True
    pa = set(family.get(a, {}).get("parents", []))
    pb = set(family.get(b, {}).get("parents", []))
    return bool(pa & pb)


def unique_name(used, pool, rng):
    """Einen Namen zurueckgeben, der noch nicht in ``used`` vorkommt.

    Bevorzugt einen freien Namen aus ``pool``; ist der Pool erschoepft, wird ein
    Basisname mit fortlaufender Nummer angehaengt ("Mochi 2", "Mochi 3", …).
    ``rng`` ist die Zufallsquelle (z.B. das ``random``-Modul)."""
    used = set(used)
    free = [name for name in pool if name not in used]
    if free:
        return rng.choice(free)
    base = rng.choice(pool)
    i = 2
    while f"{base} {i}" in used:
        i += 1
    return f"{base} {i}"
