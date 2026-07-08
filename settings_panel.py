"""Das Pixel-Einstellungsfenster.

Ein komplett selbst gezeichnetes UI im Retro-Look des Pets: Tabs, Slider,
Schalter mit Kurzbeschreibung, eine Pet-Verwaltung und ein hübsch gezeichneter
Stammbaum. Gerendert als pygame-Surface und über ein normales Overlay-Fenster
angezeigt; die Maus-Interaktion kommt (wie beim Pet) aus dem Overlay-Event-Pump
der Hauptschleife.

Reine UI-/Layout-Logik ohne ObjC — dadurch headless testbar (Surface bauen,
Hit-Testing, prefs.json schreiben). Die Fenster-/Event-Anbindung macht main.
"""

import json
import os

import pygame

import breeding
import config
import lineage
import persistence
from config import WEAPONS
from render import render_pixel_text, GLYPH_H, SPACE_W, GLYPH_GAP, GLYPH_W


PANEL_W = 600
PANEL_H = 520

# Farbwelt: dunkles Navy-Panel, warmer Ginger-Akzent (wie das Pet), Minze fuer
# "an", Rot fuer Entfernen.
BG = (24, 27, 42, 255)
BAR = (33, 37, 57, 255)
CARD = (34, 39, 60, 255)
CARD_HI = (46, 52, 78, 255)
BORDER = (66, 74, 104, 255)
TEXT = (233, 237, 246, 255)
MUTED = (140, 148, 176, 255)
ACCENT = (236, 145, 92, 255)
ACCENT_DK = (176, 96, 58, 255)
TRACK = (52, 58, 86, 255)
GOOD = (118, 200, 158, 255)
GOOD_DK = (74, 150, 116, 255)
DANGER = (224, 96, 96, 255)
DANGER_DK = (168, 64, 64, 255)
KNOB = (245, 248, 255, 255)

# Palettenspiegel fuer die Pet-Verwaltung (Farbklecks je Pet).
PALETTE_SWATCH = [p["color"] for p in config.PALETTES]

_TAB_SETTING = [group for group, _fields in config.PREFS_SCHEMA]
TABS = _TAB_SETTING + ["Pets", "Stammbaum"]

_TRANSLIT = {
    "ä": "AE", "ö": "OE", "ü": "UE", "Ä": "AE", "Ö": "OE", "Ü": "UE", "ß": "SS",
}


def _tx(text):
    """Umlaute in etwas übersetzen, das die 5x7-Font kennt (nur fürs Display —
    die Quelltexte behalten echte Umlaute)."""
    for bad, good in _TRANSLIT.items():
        text = text.replace(bad, good)
    return text


def _text_width_scaled(text, ts):
    text = _tx(text).upper()
    width = 0
    for ch in text:
        adv = SPACE_W if ch == " " else GLYPH_W
        width += (adv + GLYPH_GAP) * ts
    return max(0, width - GLYPH_GAP * ts)


def _blit_text(surf, text, x, y, color, ts=2, align="left"):
    """Pixel-Text zeichnen (nearest-neighbour hochskaliert). align: left/right/center."""
    glyphs = render_pixel_text(_tx(text), color)
    w, h = glyphs.get_width() * ts, glyphs.get_height() * ts
    scaled = pygame.transform.scale(glyphs, (w, h))
    if align == "right":
        x -= w
    elif align == "center":
        x -= w // 2
    surf.blit(scaled, (int(x), int(y)))
    return w


def _fill(surf, rect, color):
    pygame.draw.rect(surf, color, rect)


def _panel_box(surf, rect, fill, border=None, bw=2):
    _fill(surf, rect, fill)
    if border:
        pygame.draw.rect(surf, border, rect, bw)


def _in(rect, pos):
    x, y, w, h = rect
    return x <= pos[0] < x + w and y <= pos[1] < y + h


def _decimals_for_step(step):
    s = f"{step:.6f}".rstrip("0")
    return len(s.split(".")[1]) if "." in s else 0


def _format_value(field, val):
    if field["type"] == "bool":
        return "AN" if val else "AUS"
    if field["type"] == "int":
        txt = str(int(round(val)))
    else:
        txt = f"{val:.{_decimals_for_step(field['step'])}f}"
    unit = field.get("unit")
    return f"{txt} {unit}" if unit else txt


class SettingsPanel:
    """Zustand + Zeichnen + Interaktion des Einstellungsfensters."""

    W = PANEL_W
    H = PANEL_H

    def __init__(self):
        # Aktuelle Werte aus config (inkl. bereits geladener prefs.json).
        self.values = {
            key: getattr(config, key) for key in config.PREFS_FIELDS
        }
        self.tab = TABS[0]
        self.active_slider = None      # key des gerade gezogenen Sliders
        self.breed_selection = []      # bis zu 2 Pet-ids fuers gezielte Zuchten
        self.pet_scroll = 0            # Index des ersten sichtbaren Pets (Scroll)
        self._scroll_accum = 0.0       # aufgelaufener Scroll-Delta bis zur naechsten Zeile
        self._actions = []             # (typ, *args) fuer main
        self._widgets = []
        self._tracks = {}
        self.saved_flash = 0           # Frames "Gespeichert!"-Hinweis
        self.dirty = True
        # Kontext von main (pro Frame gesetzt).
        self.pets = []                 # [{"id","name","palette_index","generation","baby"}]
        self.lineage = {}              # uid -> (name, generation, [eltern-uids])
        self.focus_uid = None
        self.stats = {}                # {"victories","balls","playtime"}

    # -- Kontext / Aktionen ------------------------------------------------

    def set_context(self, pets, lineage, focus_uid, stats=None):
        stats = stats or {}
        if (pets, lineage, focus_uid, stats) != (
            self.pets, self.lineage, self.focus_uid, self.stats
        ):
            self.dirty = True
        self.pets = pets
        self.lineage = lineage
        self.focus_uid = focus_uid
        self.stats = stats

    def pop_actions(self):
        actions = self._actions[:]
        self._actions.clear()
        return actions

    def take_dirty(self):
        was = self.dirty
        self.dirty = False
        return was

    # -- Speichern ---------------------------------------------------------

    def save(self):
        """Alle Werte als prefs.json schreiben. config liest sie beim naechsten
        Start; darum der Neustart-Hinweis im Footer."""
        data = {}
        for key, field in config.PREFS_FIELDS.items():
            val = self.values[key]
            data[key] = int(round(val)) if field["type"] == "int" else (
                bool(val) if field["type"] == "bool" else round(float(val), 6)
            )
        try:
            os.makedirs(persistence.state_dir(), exist_ok=True)
            path = persistence.prefs_path()
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError:
            pass
        self.saved_flash = 150
        self.dirty = True

    # -- Interaktion -------------------------------------------------------

    def wants_point(self, local):
        return _in((0, 0, self.W, self.H), local) or self.active_slider is not None

    def _set_slider(self, key, local_x):
        field = config.PREFS_FIELDS[key]
        tx, _ty, tw, _th = self._tracks[key]
        frac = max(0.0, min(1.0, (local_x - tx) / max(1, tw)))
        lo, hi, step = field["min"], field["max"], field["step"]
        raw = lo + frac * (hi - lo)
        snapped = lo + round((raw - lo) / step) * step
        snapped = max(lo, min(hi, snapped))
        new = int(round(snapped)) if field["type"] == "int" else round(snapped, 6)
        if new != self.values[key]:
            self.values[key] = new
            self.dirty = True

    def on_click(self, local):
        """Ein Tap (Druck + Loslassen ohne Ziehen): diskrete Controls ausloesen
        bzw. einen Slider an der Klickstelle setzen (ohne ihn zu 'greifen')."""
        for w in self._widgets:
            if not _in(w["rect"], local):
                continue
            kind = w["kind"]
            if kind == "slider":
                self._set_slider(w["field"]["key"], local[0])
            elif kind == "toggle":
                key = w["field"]["key"]
                self.values[key] = not self.values[key]
                self.dirty = True
            elif kind == "tab":
                if self.tab != w["tab"]:
                    self.tab = w["tab"]
                    self.dirty = True
            elif kind == "select":
                pid = w["pet_id"]
                if pid in self.breed_selection:
                    self.breed_selection.remove(pid)
                elif len(self.breed_selection) < 2:
                    self.breed_selection.append(pid)
                else:
                    # Aeltere Auswahl weiterschieben, hoechstens zwei aktiv.
                    self.breed_selection = [self.breed_selection[1], pid]
                self.dirty = True
            elif kind == "button":
                self._do_button(w["action"])
            return

    def on_grab(self, local):
        """Maustaste ging ueber einem Slider runter: Slider 'greifen', damit das
        Ziehen ihn weiterstellt, auch wenn der Cursor kurz den Track verlaesst."""
        for w in self._widgets:
            if w["kind"] == "slider" and _in(w["rect"], local):
                self.active_slider = w["field"]["key"]
                self._set_slider(self.active_slider, local[0])
                self.dirty = True
                return

    def on_drag(self, local):
        if self.active_slider is not None:
            self._set_slider(self.active_slider, local[0])

    def on_release(self):
        if self.active_slider is not None:
            self.active_slider = None

    SCROLL_PX_PER_ROW = 22             # aufgelaufene Scroll-Pixel je Zeile

    def _max_pet_scroll(self):
        return max(0, len(self.pets) - self.PET_ROWS)

    def on_scroll(self, local, delta):
        """Mausrad/Trackpad ueber der Pet-Liste: die Liste zeilenweise scrollen.
        `delta` ist die vertikale Scroll-Groesse (AppKit scrollingDeltaY)."""
        if self.tab != "Pets" or self._max_pet_scroll() == 0:
            return False
        # Nach unten scrollen (delta < 0) zeigt spaetere Pets -> Offset groesser.
        self._scroll_accum += -delta
        rows = int(self._scroll_accum / self.SCROLL_PX_PER_ROW)
        if rows:
            self._scroll_accum -= rows * self.SCROLL_PX_PER_ROW
            new = max(0, min(self._max_pet_scroll(), self.pet_scroll + rows))
            if new != self.pet_scroll:
                self.pet_scroll = new
                self.dirty = True
        return True

    def _do_button(self, action):
        if action == ("save",):
            self.save()  # prefs.json schreiben + Bestaetigung
        elif action[0] == "breed":
            self.breed_selection = []  # Auswahl nach dem Zuchten zuruecksetzen
        # Immer an main melden — fuer Save, damit es live angewandt wird, sonst
        # fuer close/recolour/rename/remove/remove_all/new_pet/breed.
        self._actions.append(action)

    # -- Widget-Layout (fuer Zeichnen UND Hit-Testing) ---------------------

    def _build_widgets(self):
        widgets = []
        # Tabs.
        tab_x = 12
        for name in TABS:
            tw = _text_width_scaled(name, 2) + 24
            widgets.append({"kind": "tab", "tab": name,
                            "rect": (tab_x, 52, tw, 26)})
            tab_x += tw + 6
        # Footer-Buttons.
        widgets.append({"kind": "button", "action": ("save",),
                        "rect": (self.W - 150, self.H - 44, 134, 30),
                        "label": "Speichern", "style": "accent"})
        widgets.append({"kind": "button", "action": ("close",),
                        "rect": (16, self.H - 44, 110, 30),
                        "label": "Schliessen", "style": "muted"})

        if self.tab in _TAB_SETTING:
            widgets.extend(self._build_setting_widgets())
        elif self.tab == "Pets":
            widgets.extend(self._build_pet_widgets())
        # Stammbaum hat keine interaktiven Widgets.
        self._widgets = widgets
        return widgets

    def _fields_for_tab(self):
        for group, fields in config.PREFS_SCHEMA:
            if group == self.tab:
                return fields
        return []

    def _build_setting_widgets(self):
        widgets = []
        fields = self._fields_for_tab()
        y = 96
        rh = 62
        for field in fields:
            rect = (16, y, self.W - 32, rh - 8)
            if field["type"] == "bool":
                widgets.append({"kind": "toggle", "field": field, "rect": rect,
                                "toggle_rect": (self.W - 100, y + 16, 70, 26)})
            else:
                track = (34, y + rh - 24, self.W - 68, 8)
                self._tracks[field["key"]] = track
                widgets.append({"kind": "slider", "field": field, "rect": rect,
                                "track": track})
            y += rh
        return widgets

    PET_ROWS = 5
    PET_ROW_Y = 128
    PET_ROW_H = 36

    def _build_pet_widgets(self):
        widgets = []
        # Auswahl auf noch existierende Pets beschraenken.
        alive = {p["id"] for p in self.pets}
        self.breed_selection = [i for i in self.breed_selection if i in alive]

        # Toolbar oben: neuer Pet / alle entfernen.
        widgets.append({"kind": "button", "action": ("new_pet",),
                        "rect": (16, 96, 132, 26),
                        "label": "Neuer Pet", "style": "accent"})
        widgets.append({"kind": "button", "action": ("remove_all",),
                        "rect": (156, 96, 150, 26),
                        "label": "Alle entfernen", "style": "danger"})

        # Scroll-Offset auf den gueltigen Bereich klemmen (Pets koennen weniger
        # geworden sein) und nur das sichtbare Fenster als Zeilen auslegen.
        self.pet_scroll = max(0, min(self.pet_scroll, self._max_pet_scroll()))
        y = self.PET_ROW_Y
        for pet in self.pets[self.pet_scroll:self.pet_scroll + self.PET_ROWS]:
            # Aktions-Buttons rechts (zuerst -> werden vor der Auswahl getroffen).
            bx = self.W - 16
            for label, action, style in (
                ("Weg", ("remove", pet["id"]), "danger"),
                ("Name", ("rename", pet["id"]), "muted"),
                ("Farbe", ("recolour", pet["id"]), "muted"),
            ):
                bw = _text_width_scaled(label, 2) + 18
                bx -= bw
                widgets.append({"kind": "button", "action": action,
                                "rect": (bx, y + 5, bw, 24),
                                "label": label, "style": style})
                bx -= 6
            # Rest der Zeile = Auswahl fuers Zuchten.
            widgets.append({"kind": "select", "pet_id": pet["id"],
                            "rect": (16, y, bx - 16, self.PET_ROW_H - 4)})
            y += self.PET_ROW_H

        # Zuchten-Button nur, wenn genau zwei ausgewaehlt UND nicht verwandt sind
        # (kein Inzest). Bei zu enger Verwandtschaft bleibt der Button weg.
        if len(self.breed_selection) == 2 and not self._selection_related():
            widgets.append({
                "kind": "button",
                "action": ("breed", self.breed_selection[0], self.breed_selection[1]),
                "rect": (self.W - 150, self.H - 92, 134, 30),
                "label": "Zuchten", "style": "accent",
            })
        return widgets

    def _family_graph(self):
        """self.lineage (uid -> (name, gen, [eltern])) in das von lineage.py
        erwartete Format (uid -> {"parents": [...]}) bringen."""
        return {uid: {"parents": rec[2]} for uid, rec in self.lineage.items()}

    def _selection_related(self):
        """Ob die zwei aktuell ausgewaehlten Pets zu eng verwandt sind."""
        if len(self.breed_selection) != 2:
            return False
        a = self._pet_by_id(self.breed_selection[0])
        b = self._pet_by_id(self.breed_selection[1])
        if a is None or b is None:
            return False
        return lineage.are_related(a["uid"], b["uid"], self._family_graph())

    # -- Zeichnen ----------------------------------------------------------

    def render(self):
        if self.saved_flash > 0:
            self.saved_flash -= 1
            if self.saved_flash == 0:
                self.dirty = True
        self._build_widgets()

        surf = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        _panel_box(surf, (0, 0, self.W, self.H), BG, BORDER, 2)
        # Titelleiste.
        _fill(surf, (2, 2, self.W - 4, 40), BAR)
        _blit_text(surf, "Desktop Pet", 18, 12, TEXT, ts=3)
        _blit_text(surf, "Einstellungen", self.W - 18, 16, ACCENT, ts=2,
                   align="right")

        self._draw_tabs(surf)
        self._draw_stats(surf)

        if self.tab in _TAB_SETTING:
            self._draw_settings(surf)
        elif self.tab == "Pets":
            self._draw_pets(surf)
        elif self.tab == "Stammbaum":
            self._draw_tree(surf)

        self._draw_footer(surf)
        return surf

    def _draw_stats(self, surf):
        """Schmale Lifetime-Statistik-Zeile unter den Tabs (auf allen Tabs)."""
        if not self.stats:
            return
        line = (
            f"Kaempfe {self.stats.get('victories', 0)}    "
            f"Baelle {self.stats.get('balls', 0)}    "
            f"Spielzeit {self.stats.get('playtime', '-')}"
        )
        _blit_text(surf, line, self.W // 2, 82, MUTED, ts=1, align="center")

    def _draw_tabs(self, surf):
        for w in self._widgets:
            if w["kind"] != "tab":
                continue
            active = w["tab"] == self.tab
            _panel_box(surf, w["rect"], ACCENT if active else CARD,
                       None if active else BORDER, 1)
            col = BG if active else MUTED
            _blit_text(surf, w["tab"], w["rect"][0] + 12, w["rect"][1] + 6, col,
                       ts=2)

    def _draw_settings(self, surf):
        for w in self._widgets:
            if w["kind"] == "slider":
                self._draw_slider(surf, w)
            elif w["kind"] == "toggle":
                self._draw_toggle(surf, w)

    def _draw_slider(self, surf, w):
        field, rect = w["field"], w["rect"]
        _panel_box(surf, rect, CARD, BORDER, 1)
        _blit_text(surf, field["label"], rect[0] + 14, rect[1] + 8, TEXT, ts=2)
        _blit_text(surf, _format_value(field, self.values[field["key"]]),
                   rect[0] + rect[2] - 14, rect[1] + 8, ACCENT, ts=2,
                   align="right")
        _blit_text(surf, field["help"], rect[0] + 14, rect[1] + 24, MUTED, ts=1)
        # Track + Fuellung + Knopf.
        tx, ty, tw, th = w["track"]
        _fill(surf, (tx, ty, tw, th), TRACK)
        lo, hi = field["min"], field["max"]
        frac = 0.0 if hi == lo else (self.values[field["key"]] - lo) / (hi - lo)
        frac = max(0.0, min(1.0, frac))
        _fill(surf, (tx, ty, int(tw * frac), th), ACCENT)
        kx = tx + int(tw * frac)
        _panel_box(surf, (kx - 5, ty - 5, 10, th + 10), KNOB, ACCENT_DK, 1)

    def _draw_toggle(self, surf, w):
        field, rect = w["field"], w["rect"]
        _panel_box(surf, rect, CARD, BORDER, 1)
        _blit_text(surf, field["label"], rect[0] + 14, rect[1] + 8, TEXT, ts=2)
        _blit_text(surf, field["help"], rect[0] + 14, rect[1] + 24, MUTED, ts=1)
        on = bool(self.values[field["key"]])
        tr = w["toggle_rect"]
        _panel_box(surf, tr, GOOD if on else TRACK, GOOD_DK if on else BORDER, 1)
        # Schieber links/rechts.
        knob_x = tr[0] + tr[2] - 22 if on else tr[0] + 2
        _fill(surf, (knob_x, tr[1] + 2, 20, tr[3] - 4), KNOB)
        _blit_text(surf, "AN" if on else "AUS",
                   tr[0] + tr[2] // 2, tr[1] + 7,
                   BG if on else MUTED, ts=1, align="center")

    def _pet_by_id(self, pid):
        return next((p for p in self.pets if p["id"] == pid), None)

    def _draw_pets(self, surf):
        if not self.pets:
            _blit_text(surf, "Keine Pets da.", self.W // 2, 200, MUTED, ts=2,
                       align="center")
        self.pet_scroll = max(0, min(self.pet_scroll, self._max_pet_scroll()))
        start = self.pet_scroll
        visible = self.pets[start:start + self.PET_ROWS]
        y = self.PET_ROW_Y
        for pet in visible:
            selected = pet["id"] in self.breed_selection
            rect = (16, y, self.W - 32, self.PET_ROW_H - 4)
            _panel_box(surf, rect, CARD_HI if selected else CARD,
                       ACCENT if selected else BORDER, 2 if selected else 1)
            sw = PALETTE_SWATCH[pet["palette_index"] % len(PALETTE_SWATCH)]
            _panel_box(surf, (rect[0] + 10, y + 8, 16, 16), sw, BORDER, 1)
            name = pet["name"]
            if len(name) > 12:
                name = name[:11] + "."
            if pet.get("baby"):
                name += " (Baby)"
            _blit_text(surf, name, rect[0] + 34, y + 4, TEXT, ts=2)
            gen = pet["generation"]
            gtxt = "wild" if gen == 0 else f"Gen {gen}"
            weap = (pet.get("weapon") or "?").upper()
            _blit_text(surf, f"{gtxt}  {weap}", rect[0] + 34, y + 20, MUTED, ts=1)
            if selected:
                idx = self.breed_selection.index(pet["id"]) + 1
                _blit_text(surf, f"{idx}", rect[0] + rect[2] - 200, y + 9,
                           ACCENT, ts=2, align="center")
            y += self.PET_ROW_H

        # Scrollbar + Zaehler, sobald mehr Pets da sind als Zeilen passen.
        total = len(self.pets)
        if total > self.PET_ROWS:
            last = min(start + self.PET_ROWS, total)
            _blit_text(surf, f"{start + 1}-{last} von {total}  (scrollen)",
                       self.W // 2, y - 4, MUTED, ts=1, align="center")
            self._draw_pet_scrollbar(surf, total)

        self._draw_breed_preview(surf)
        # Alle Buttons dieses Tabs zeichnen (Footer-Buttons macht _draw_footer).
        # (Scrollbar oben gezeichnet, damit sie nicht von Karten verdeckt wird.)
        for w in self._widgets:
            if w["kind"] == "button" and w["action"] not in (("save",), ("close",)):
                self._draw_button(surf, w)

    def _draw_pet_scrollbar(self, surf, total):
        """Schlanke Scrollbar im rechten Rand-Gutter der Pet-Liste; der Thumb
        zeigt Position und sichtbaren Anteil."""
        x = self.W - 12
        top = self.PET_ROW_Y
        height = self.PET_ROWS * self.PET_ROW_H - 8
        _fill(surf, (x, top, 4, height), CARD)
        thumb_h = max(20, int(height * self.PET_ROWS / total))
        max_scroll = self._max_pet_scroll()
        t = self.pet_scroll / max_scroll if max_scroll else 0
        thumb_y = top + int((height - thumb_h) * t)
        _panel_box(surf, (x, thumb_y, 4, thumb_h), ACCENT, ACCENT, 1)

    def _draw_breed_preview(self, surf):
        """Zeigt fuer zwei ausgewaehlte Eltern die Wahrscheinlichkeiten, welche
        Farbe und Waffe das Kind bekommt."""
        box = (16, 314, self.W - 32, self.H - 314 - 58)
        _panel_box(surf, box, CARD, BORDER, 1)
        bx, by, bw, bh = box
        sel = self.breed_selection
        if len(sel) < 2:
            _blit_text(surf, "Zwei Pets anklicken, um Eltern zu waehlen",
                       self.W // 2, by + bh // 2 - 6, MUTED, ts=2, align="center")
            return
        a, b = self._pet_by_id(sel[0]), self._pet_by_id(sel[1])
        if a is None or b is None:
            return
        if self._selection_related():
            _blit_text(surf, "Zu eng verwandt", self.W // 2, by + bh // 2 - 14,
                       DANGER, ts=2, align="center")
            _blit_text(surf, "kein Inzest — andere Eltern waehlen",
                       self.W // 2, by + bh // 2 + 6, MUTED, ts=1, align="center")
            return
        _blit_text(surf, f"Zucht-Vorschau: {a['name']} + {b['name']}",
                   bx + 14, by + 8, TEXT, ts=2)

        col_dist = breeding.color_distribution(a["palette_index"], b["palette_index"])
        wpn_dist = breeding.weapon_distribution(
            a.get("weapon") or WEAPONS[0], b.get("weapon") or WEAPONS[0]
        )
        top_colors = sorted(col_dist.items(), key=lambda kv: -kv[1])[:4]
        top_weapons = sorted(wpn_dist.items(), key=lambda kv: -kv[1])[:4]

        col_x = bx + 16
        wpn_x = bx + bw // 2 + 10
        row_y = by + 32
        _blit_text(surf, "Farbe", col_x, row_y, ACCENT, ts=1)
        _blit_text(surf, "Waffe", wpn_x, row_y, ACCENT, ts=1)
        row_y += 16
        for i in range(max(len(top_colors), len(top_weapons))):
            ry = row_y + i * 18
            if i < len(top_colors):
                idx, p = top_colors[i]
                _panel_box(surf, (col_x, ry, 14, 14),
                           PALETTE_SWATCH[idx % len(PALETTE_SWATCH)], BORDER, 1)
                _blit_text(surf, f"{round(p * 100)}%", col_x + 22, ry, TEXT, ts=1)
            if i < len(top_weapons):
                wname, p = top_weapons[i]
                _blit_text(surf, wname.upper(), wpn_x, ry, TEXT, ts=1)
                _blit_text(surf, f"{round(p * 100)}%", wpn_x + 110, ry, MUTED,
                           ts=1, align="right")

    def _tree_levels(self):
        """Ahnen-Ebenen als uid-Listen: Ebene 0 = Fokus-Pet, dann Eltern,
        Grosseltern … Pro Ebene und ueber Ebenen hinweg dedupliziert (ein Ahn
        erscheint nur einmal), damit gemeinsame Vorfahren und kaputte Zyklen den
        Baum nicht aufblaehen."""
        focus = self.focus_uid
        if focus is None or focus not in self.lineage:
            return []
        levels = [[focus]]
        placed = {focus}
        for _ in range(5):
            nxt = []
            for uid in levels[-1]:
                _name, _gen, parents = self.lineage.get(uid, ("?", 0, []))
                for p in parents:
                    if p in self.lineage and p not in placed and p not in nxt:
                        nxt.append(p)
                        placed.add(p)
            if not nxt:
                break
            levels.append(nxt)
        return levels

    def _draw_tree(self, surf):
        """Stammbaum als verbundene Kaestchen: Eltern/Ahnen OBEN, das gewaehlte
        Pet UNTEN, mit Verbindungslinien. Ueber stabile uids gefuehrt (Namen
        koennen sich wiederholen), speist sich aus dem vollstaendigen
        Familienregister — auch verstorbene Ahnen erscheinen."""
        focus_name = None
        if self.focus_uid in self.lineage:
            focus_name = self.lineage[self.focus_uid][0]
        if not focus_name:
            _blit_text(surf, "Kein Pet ausgewaehlt.", self.W // 2, 200, MUTED,
                       ts=2, align="center")
            return
        _blit_text(surf, f"Stammbaum: {focus_name}", self.W // 2, 100, TEXT,
                   ts=2, align="center")

        levels = self._tree_levels()
        n_levels = len(levels)
        top, bottom = 126, self.H - 64
        row_h = (bottom - top) // max(1, n_levels)
        positions = {}  # uid -> (cx, cy)
        for li, uids in enumerate(levels):
            # Invertiert: Ebene 0 (Kind) unten, hoehere Ebenen (Ahnen) oben.
            cy = bottom - li * row_h - row_h // 2
            n = len(uids)
            for i, uid in enumerate(uids):
                positions[uid] = (int(self.W * (i + 1) / (n + 1)), cy)

        # Verbindungslinien Kind (unten) -> Eltern (darueber), ueber die uid
        # direkt aufgeloest — auch bei gemeinsamen Vorfahren korrekt.
        for li in range(n_levels - 1):
            for uid in levels[li]:
                _name, _gen, parents = self.lineage.get(uid, ("?", 0, []))
                cx, cy = positions[uid]
                for p in parents:
                    if p in positions:
                        px, py = positions[p]
                        pygame.draw.line(surf, BORDER, (cx, cy - 14), (px, py + 14), 2)

        for li, uids in enumerate(levels):
            n = len(uids)
            node_w = min(140, max(64, (self.W - 40) // max(1, n) - 8))
            for uid in uids:
                cx, cy = positions[uid]
                name, gen, _parents = self.lineage.get(uid, ("?", 0, []))
                self._draw_tree_node(surf, cx, cy, name, gen, uid == self.focus_uid,
                                     node_w)

    def _draw_tree_node(self, surf, cx, cy, name, gen, focus, node_w):
        max_chars = max(3, (node_w - 12) // (GLYPH_W + GLYPH_GAP) // 2)
        label = name if len(name) <= max_chars else name[:max_chars - 1] + "."
        h = 32
        rect = (cx - node_w // 2, cy - h // 2, node_w, h)
        _panel_box(surf, rect, CARD_HI if focus else CARD,
                   ACCENT if focus else BORDER, 2 if focus else 1)
        _blit_text(surf, label, cx, cy - 10, TEXT, ts=2, align="center")
        badge = "wild" if gen == 0 else (f"Gen {gen}" if gen is not None else "?")
        _blit_text(surf, badge, cx, cy + 4, ACCENT if focus else MUTED, ts=1,
                   align="center")

    def _draw_footer(self, surf):
        _fill(surf, (2, self.H - 52, self.W - 4, 50), BAR)
        if self.saved_flash > 0:
            _blit_text(surf, "Gespeichert!", self.W // 2, self.H - 40, GOOD,
                       ts=2, align="center")
        else:
            _blit_text(surf, "Aenderungen gelten nach Neustart",
                       self.W // 2, self.H - 38, MUTED, ts=1, align="center")
        for w in self._widgets:
            if w["kind"] == "button" and w["action"] in (("save",), ("close",)):
                self._draw_button(surf, w)

    def _draw_button(self, surf, w):
        style = w.get("style", "muted")
        fill, border, txt = {
            "accent": (ACCENT, ACCENT_DK, BG),
            "muted": (CARD, BORDER, TEXT),
            "danger": (DANGER, DANGER_DK, (255, 255, 255, 255)),
        }[style]
        _panel_box(surf, w["rect"], fill, border, 1)
        _blit_text(surf, w["label"], w["rect"][0] + w["rect"][2] // 2,
                   w["rect"][1] + (w["rect"][3] - 14) // 2, txt, ts=2,
                   align="center")
