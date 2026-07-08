"""Entry point and main loop for the desktop pet.

Wires the pieces together: one interactive `MacOverlay` per pet (the first one
also owns the menu-bar menu), a second non-interactive overlay per pet for
effects (speech bubble, particles, weapon), a shared `WindowTracker` for
platforms, and a `Pet` per pet for behaviour.

Supports multiple pets: the menu-bar "Breed" item spawns a child and
"Remove a pet" culls the most recent one. Slow strokes over a pet make it
love you; clicking it too often makes it arm itself and chase the cursor.
"""

import math
import os
import random
import signal
import sys
import time

import pygame

import activity
import config
import persistence
import lineage
import playback
import sharing
import settings_panel
import updater

from ball import Ball
from food import Snack
from config import (
    BALL_WIN,
    SNACK_WIN,
    BREED_COOLDOWN,
    BUBBLE_GAP,
    CLEAR,
    COURT_TIMEOUT,
    COURT_MEET_FRAMES,
    COURT_MEET_HEART_CHANCE,
    FOCUS_MINUTES,
    FPS,
    FX_H,
    FX_W,
    MAX_PETS,
    GROUP_SUPPORT_RADIUS,
    GROUP_JOIN_CHANCE,
    GROUP_JOIN_ANGER,
    BABY_DEFENSE_RADIUS,
    WINDOW_H,
    WINDOW_W,
)
from overlay import MacOverlay
from pet import Pet
from render import (
    draw_ball,
    draw_snack,
    draw_flight_rig,
    draw_name_tag,
    draw_pet_frame,
    draw_speech_bubble,
    particle_sprite,
    pet_cache_key,
    weapon_pose,
)
from window_tracker import WindowTracker


def spawn_pet(bounds, platforms, x=None, y=None, overlay=None):
    """Create a pet plus its two overlay windows and drawing canvases.

    Pass an existing `overlay` to reuse the menu-owning primary window for the
    first pet; otherwise a fresh interactive window is created.
    """
    if overlay is None:
        overlay = MacOverlay(WINDOW_W, WINDOW_H, interactive=True)
    fx = MacOverlay(FX_W, FX_H, interactive=False)
    pet = Pet(bounds)
    if x is not None and y is not None:
        pet.x = float(x)
        pet.y = float(y)
    pet.place_on_best_platform(platforms)
    return {
        "pet": pet,
        "overlay": overlay,
        "fx": fx,
        "canvas": pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA),
        "fx_canvas": pygame.Surface((FX_W, FX_H), pygame.SRCALPHA),
        "fx_visible": False,
    }


def _confirm_remove_all(count):
    """Native confirmation before wiping out every pet. Returns True to proceed."""
    plural = "s" if count != 1 else ""
    choice = updater._alert(
        f"Remove all {count} pet{plural}?\n\nThey'll get a little send-off. You can "
        "always spawn new ones from the menu.",
        ["Cancel", "Remove all"],
        "Cancel",
    )
    return choice == "Remove all"


def _format_playtime(seconds):
    """Sekunden als knappe Spielzeit, z.B. '3h 12m' oder '4m 07s'."""
    seconds = int(max(0, seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def pet_under_point(pets, point):
    """Topmost (most recently spawned) pet whose hitbox contains point."""
    if point is None:
        return None
    px, py = point
    for entry in reversed(pets):
        pet = entry["pet"]
        if pet.dying:
            continue
        if (
            pet.x - 6 <= px <= pet.x + WINDOW_W + 6
            and pet.y - 6 <= py <= pet.y + WINDOW_H + 6
        ):
            return entry
    return None


def _display_for_fx(display_rects, pet, origin_x, origin_y):
    """Pick the display the effects window must stay inside.

    Prefer the display containing the pet's centre; if the pet sits in the
    empty gap between differently-sized monitors, fall back to the display the
    intended effects rect overlaps most, then to the global bounding box.
    Returned as (x, y, w, h) in the global CG (top-left origin) space.
    """
    cx = pet.x + WINDOW_W / 2
    cy = pet.y + WINDOW_H / 2
    for d in display_rects:
        if d["x"] <= cx < d["x"] + d["w"] and d["y"] <= cy < d["y"] + d["h"]:
            return d["x"], d["y"], d["w"], d["h"]
    best, best_area = None, 0
    for d in display_rects:
        ox = max(0, min(origin_x + FX_W, d["x"] + d["w"]) - max(origin_x, d["x"]))
        oy = max(0, min(origin_y + FX_H, d["y"] + d["h"]) - max(origin_y, d["y"]))
        area = ox * oy
        if area > best_area:
            best, best_area = d, area
    if best is not None:
        return best["x"], best["y"], best["w"], best["h"]
    return pet.min_x, pet.min_y, pet.max_x - pet.min_x, pet.max_y - pet.min_y


def render_pet(entry, display_rects):
    """Draw a pet into its overlay, and its bubble/particles/weapon into fx."""
    pet = entry["pet"]
    overlay = entry["overlay"]
    fx = entry["fx"]
    canvas = entry["canvas"]
    fx_canvas = entry["fx_canvas"]

    # Nur neu zeichnen/pushen, wenn sich am Aussehen wirklich etwas geändert hat.
    # Ein ruhender/schlafender Pet behält seinen Key: kein Redraw, kein CGImage-
    # Push. Bewegt er sich nur (gleicher Key, andere Position), reicht ein move().
    key = pet_cache_key(pet)
    appearance_changed = key != entry.get("pet_key")
    pos = (round(pet.x), round(pet.y))
    if appearance_changed:
        canvas.fill(CLEAR)
        canvas.blit(draw_pet_frame(pet), (0, 0))
    if pos != entry.get("pet_pos"):
        overlay.move(*pos)
        entry["pet_pos"] = pos
    if appearance_changed:
        overlay.show_surface(canvas)
        entry["pet_key"] = key

    hovering = entry.get("hover") and not pet.talking and not pet.dying
    if (pet.talking or pet.particles or pet.weapon or pet.flying
            or pet.joy_flying or hovering):
        origin_x = round(pet.x + WINDOW_W / 2 - FX_W / 2)
        origin_y = round(pet.y + WINDOW_H / 2 - FX_H / 2)
        # Keep the effects window fully inside the SINGLE display the pet is on,
        # not just the global bounding box. That box spans the empty gaps
        # between differently-sized monitors, so clamping to it let this large
        # (420x440) window straddle a display edge or poke into an inter-display
        # gap. A high-level "join all spaces" panel that straddles a boundary
        # gets composited/constrained onto a second spot by the window server,
        # which showed up as a flickering ghost of the bubble/particles in a
        # corner of the external monitor.
        dx, dy, dw, dh = _display_for_fx(display_rects, pet, origin_x, origin_y)
        if dw >= FX_W:
            origin_x = max(dx, min(dx + dw - FX_W, origin_x))
        if dh >= FX_H:
            origin_y = max(dy, min(dy + dh - FX_H, origin_y))
        # The pet is centred in the window only when unclamped; derive its
        # actual offset so the bubble/weapon stay pinned to him after clamping.
        pet_left = round(pet.x) - origin_x
        pet_top = round(pet.y) - origin_y

        fx_canvas.fill(CLEAR)

        for p in pet.particles:
            sprite = particle_sprite(p["kind"])
            if p.get("flip"):
                sprite = pygame.transform.flip(sprite, True, False)
            sprite.set_alpha(int(255 * max(0.0, min(1.0, p["life"] / p["maxlife"]))))
            fx_canvas.blit(
                sprite,
                (
                    round(p["x"] - origin_x - sprite.get_width() / 2),
                    round(p["y"] - origin_y - sprite.get_height() / 2),
                ),
            )

        # Jetpack sits behind the pet, so draw it before the weapon (in front).
        if pet.flying or pet.joy_flying:
            rig, rdx, rdy = draw_flight_rig(pet)
            fx_canvas.blit(rig, (round(pet_left + rdx), round(pet_top + rdy)))

        if pet.weapon:
            weapon, wdx, wdy = weapon_pose(pet)
            fx_canvas.blit(weapon, (round(pet_left + wdx), round(pet_top + wdy)))

        if pet.talking:
            if pet.speech_dirty or pet.speech_surface is None:
                surf = draw_speech_bubble(pet.speech_text)
                if pet.y - surf.get_height() < pet.min_y + 4:
                    surf = draw_speech_bubble(pet.speech_text, tail_up=True)
                    pet.speech_tail_up = True
                else:
                    pet.speech_tail_up = False
                pet.speech_surface = surf
                pet.speech_dirty = False
            surf = pet.speech_surface
            bx = pet_left + (WINDOW_W - surf.get_width()) // 2
            if pet.speech_tail_up:
                by = pet_top + WINDOW_H - BUBBLE_GAP
            else:
                by = pet_top - surf.get_height() + BUBBLE_GAP
            fx_canvas.blit(surf, (bx, by))

        # Hover: kleines Namensschild ueber dem Kopf (nur solange die Maus drueber
        # ist und keine Sprechblase laeuft).
        if hovering:
            tag = draw_name_tag(pet.name)
            tx = pet_left + (WINDOW_W - tag.get_width()) // 2
            ty = pet_top - tag.get_height() - 2
            fx_canvas.blit(tag, (tx, ty))

        fx.move(origin_x, origin_y)
        fx.show_surface(fx_canvas)
        entry["fx_visible"] = True
    elif entry["fx_visible"]:
        fx_canvas.fill(CLEAR)
        fx.show_surface(fx_canvas)
        entry["fx_visible"] = False


def main():
    if sys.platform != "darwin":
        raise SystemExit("This overlay implementation is for macOS.")

    running = True

    def stop(_signum=None, _frame=None):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    pygame.init()
    primary = MacOverlay(WINDOW_W, WINDOW_H, interactive=True, with_menu=True)
    # Window titles (used to spot a YouTube/Meet tab in a browser) need Screen
    # Recording permission. We only check whether it's already granted — we never
    # prompt for it, so first launch and post-update relaunches stay quiet.
    primary.ensure_screen_recording()
    display_rects, bounds = primary.refresh_displays()
    window_tracker = WindowTracker(display_rects, bounds)
    platforms = window_tracker.platforms()

    saved_state = persistence.load()
    saved_pets = saved_state.get("pets") or []

    # Identitaet & Stammbaum laufen ueber stabile uids, nicht ueber Namen (Namen
    # duerfen sich wiederholen und dienen nur der Anzeige). Der uid-basierte Stand
    # traegt "next_uid"; aeltere Staende fuehrten die Abstammung ueber Namen — die
    # verwerfen wir und lassen den Baum ab jetzt sauber ueber uids neu wachsen.
    legacy_state = "next_uid" not in saved_state
    next_uid = [0 if legacy_state else int(saved_state.get("next_uid") or 0)]

    def assign_uid(pet):
        next_uid[0] += 1
        pet.uid = next_uid[0]

    # Stammbaum-Register: uid -> {"name","generation","parents":[uid,...]}. Sammelt
    # ALLE je gelebten Pets (auch verstorbene Ahnen), damit der Baum vollstaendig
    # bleibt und ueber Neustarts hinweg waechst.
    family = {}
    if not legacy_state and isinstance(saved_state.get("family"), dict):
        for key, rec in saved_state["family"].items():
            try:
                uid = int(key)
            except (TypeError, ValueError):
                continue
            if not isinstance(rec, dict):
                continue
            gen = rec.get("generation")
            name = rec.get("name")
            family[uid] = {
                "name": name if isinstance(name, str) and name else f"Pet {uid}",
                "generation": gen if isinstance(gen, int) and gen >= 0 else 0,
                "parents": [int(p) for p in rec.get("parents", [])
                            if isinstance(p, int) and not isinstance(p, bool)],
            }

    def used_names(exclude_uid=None):
        names = {rec["name"] for uid, rec in family.items() if uid != exclude_uid}
        names |= {e["pet"].name for e in pets if e["pet"].uid != exclude_uid}
        return names

    def unique_name(exclude_uid=None):
        return lineage.unique_name(used_names(exclude_uid), config.PET_NAMES, random)

    def record_family(pet):
        family[pet.uid] = {
            "name": pet.name,
            "generation": pet.generation,
            "parents": list(pet.parents),
        }

    # Gespeicherte Pets neu erzeugen (durch MAX_PETS begrenzt). Der erste Pet
    # uebernimmt das Menue-Fenster. Fehlt die Datei, genau ein Default-Pet.
    pets = []
    for data in saved_pets[:MAX_PETS]:
        if not isinstance(data, dict):
            continue
        overlay = primary if not pets else None
        entry = spawn_pet(
            bounds, platforms, x=data.get("x"), y=data.get("y"), overlay=overlay
        )
        persistence.apply_dict(entry["pet"], data)
        pet = entry["pet"]
        if legacy_state:
            # Alte namensbasierte Abstammung verwerfen -> saubere Wurzel.
            pet.parents = []
            pet.generation = 0
        if pet.uid <= 0:
            assign_uid(pet)
        else:
            next_uid[0] = max(next_uid[0], pet.uid)
        pet.place_on_best_platform(platforms)
        pets.append(entry)
    if not pets:
        default = spawn_pet(bounds, platforms, overlay=primary)
        assign_uid(default["pet"])
        pets = [default]

    # Eindeutige, saubere Anzeigenamen sicherstellen: Duplikate (alte Staende
    # konnten welche haben) und die frueheren "Jr"-Namen bekommen einen frischen.
    seen = set()
    for entry in pets:
        pet = entry["pet"]
        if pet.name in seen or " Jr" in pet.name:
            pet.name = unique_name(exclude_uid=pet.uid)
        seen.add(pet.name)

    for entry in pets:
        record_family(entry["pet"])

    # Lifetime-Zaehler (gewonnene Kaempfe, gefangene Baelle, Gesamt-Spielzeit)
    # aus derselben Datei wie die Pets. Die Playtime dieser Sitzung kommt beim
    # Beenden dazu.
    lifetime = persistence.load_stats()
    session_start = time.monotonic()

    # The menu-owning window is special: it hosts the status-bar menu, so it must
    # stay alive even when every pet is removed. We never close it — when its pet
    # is culled we just blank it and make it click-through, then reuse it for the
    # next pet. `menu_overlay_free` is True while no pet's body lives in it.
    menu_overlay = primary
    menu_overlay_free = False

    # Polls media playback off-thread (music play state + whether sound is
    # actually playing) so the 60 fps loop never blocks on osascript.
    playback_monitor = playback.PlaybackMonitor()

    # Erkennt best-effort ein laufendes Bildschirm-Teilen (Zoom/Teams/Meet) ueber
    # die Fensterliste. Nur ein optionaler Automatik-Zusatz; verlaesslich ist der
    # manuelle Toggle "Bildschirm-Teilen-Modus" (share_manual).
    share_monitor = sharing.ScreenShareMonitor()
    # Vom Nutzer im Menue gesetzter Modus (verlaessliche Grundloesung).
    share_manual = False
    # True, solange die Pet-Overlays wegen Teilens ausgeblendet sind.
    pets_hidden = False

    clock = pygame.time.Clock()
    last_reassert = 0.0
    last_window_scan = 0.0
    last_activity_scan = 0.0
    drag_target = None
    # Zuletzt angeklickter Pet — Ziel fuer "Über diesen Pet" und "Stammbaum".
    last_click_entry = None
    last_key_count = None
    focus_active = False
    focus_frames_left = 0
    focus_total_frames = FOCUS_MINUTES * 60 * FPS
    # Fetch ball: a single bouncy ball the pets chase. It stays until the user
    # removes it from the menu bar ("Remove ball").
    ball = None
    ball_overlay = None
    # Snack: ein einzelnes Stueck Futter auf dem Desktop. Der naechste ruhige Pet
    # laeuft hin und frisst es; danach verschwindet es. Fluechtig, nicht persistiert.
    snack = None
    snack_overlay = None
    # Self-update: spawn update.sh, show a bubble briefly, then quit so it can
    # pull the latest and relaunch. Counts down frames before quitting.
    pending_update = 0
    # Breeding: a courtship in progress (or None) plus a cooldown so it can't be
    # spammed.
    courting = None
    breed_cooldown = 0

    # -- Pixel-Einstellungsfenster ----------------------------------------
    # Ein normales, verschiebbares Fenster mit Titelleiste; der Pixel-Inhalt wird
    # als Layer-Bild gezeichnet. Klicks kommen ueber einen Maus-Hook in
    # Fensterkoordinaten rein (nicht als Pet-Drag).
    settings_overlay = None
    settings = None
    settings_open = False
    settings_mouse = {"moved": False}
    next_pet_id = [0]

    def assign_pet_ids():
        for entry in pets:
            if "id" not in entry:
                next_pet_id[0] += 1
                entry["id"] = next_pet_id[0]

    def pet_entry_by_id(pid):
        return next((e for e in pets if e.get("id") == pid), None)

    def on_settings_mouse(phase, wx, wy, delta=0.0):
        """Maus-Event auf dem Einstellungsfenster (Fensterkoordinaten, unten-links).
        Wandelt in Panel-lokale Koordinaten (oben-links) und verteilt an das Panel.
        Rueckgabe True = Event verschluckt; False = an AppKit (z.B. Titelleiste
        zum Verschieben)."""
        if settings is None:
            return False
        lx, ly = wx, settings_panel.PANEL_H - wy
        in_content = (
            0 <= lx < settings_panel.PANEL_W and 0 <= ly < settings_panel.PANEL_H
        )
        if phase == "scroll":
            if not in_content:
                return False
            return bool(settings.on_scroll((lx, ly), delta))
        if phase == "down":
            if not in_content:
                return False  # Titelleiste/Rand -> AppKit verschiebt das Fenster
            settings_mouse["moved"] = False
            settings.on_grab((lx, ly))
            return True
        if phase == "drag":
            if settings.active_slider is not None:
                settings_mouse["moved"] = True
                settings.on_drag((lx, ly))
                return True
            return False
        if phase == "up":
            settings.on_release()
            if in_content and not settings_mouse["moved"]:
                settings.on_click((lx, ly))
                return True
            return False
        return False

    def open_settings():
        """Das Einstellungsfenster oeffnen (beim ersten Mal erzeugen), mittig
        platzieren und in den Vordergrund holen."""
        nonlocal settings_overlay, settings, settings_open
        if settings_overlay is None:
            settings = settings_panel.SettingsPanel()
            settings_overlay = MacOverlay(
                settings_panel.PANEL_W, settings_panel.PANEL_H,
                interactive=True, titled=True,
            )
            primary.set_mouse_hook(settings_overlay.window, on_settings_mouse)
        cx = (bounds[0] + bounds[2]) // 2 - settings_panel.PANEL_W // 2
        cy = (bounds[1] + bounds[3]) // 2 - settings_panel.PANEL_H // 2
        settings_overlay.move(cx, cy)
        settings.dirty = True
        settings_open = True
        settings_overlay.activate()

    def close_settings():
        nonlocal settings_open
        settings_open = False
        if settings_overlay is not None:
            settings_overlay.close()

    def apply_settings_action(action):
        """Eine vom Panel gemeldete Aktion ausfuehren."""
        nonlocal drag_target, focus_total_frames
        typ = action[0]
        if typ == "close":
            close_settings()
        elif typ == "save":
            # Sofort live anwenden, kein Neustart noetig.
            config.reload_prefs()
            focus_total_frames = config.FOCUS_MINUTES * 60 * FPS
        elif typ == "new_pet":
            if len(living_pets()) < MAX_PETS:
                entry = make_pet(randomize=True)
                entry["pet"].spawn_particles("star", 4)
                record_family(entry["pet"])
        elif typ == "breed":
            a = pet_entry_by_id(action[1])
            b = pet_entry_by_id(action[2])
            if a and b and not a["pet"].dying and not b["pet"].dying:
                start_breeding(a, b)
        elif typ == "remove_all":
            living = living_pets()
            if living and _confirm_remove_all(len(living)):
                for entry in living:
                    entry["pet"].start_death()
                drag_target = None
        elif typ in ("recolour", "rename", "remove"):
            entry = pet_entry_by_id(action[1])
            if entry is None or entry["pet"].dying:
                return
            pet = entry["pet"]
            if typ == "recolour":
                pet.cycle_palette()
                record_family(pet)
            elif typ == "remove":
                pet.start_death()
                if entry is drag_target:
                    drag_target = None
            elif typ == "rename":
                name = updater._prompt("Neuer Name fuer diesen Pet:", pet.name)
                if name:
                    pet.rename(name)
                    record_family(pet)

    def make_pet(x=None, y=None, randomize=False):
        """Spawn a fresh pet (appended to `pets`), reusing the menu window if it
        is free so the app recovers cleanly from zero pets. Mit randomize=True
        bekommt der neue Pet eine zufaellige Farbe (die Waffe ist ohnehin schon
        zufaellig) — nur explizit neu erzeugte Pets, nie der erste Default-Pet."""
        nonlocal menu_overlay_free
        if menu_overlay_free:
            menu_overlay.set_mouse_ignore(False)
            entry = spawn_pet(bounds, platforms, x=x, y=y, overlay=menu_overlay)
            menu_overlay.reassert_top()
            menu_overlay_free = False
        else:
            entry = spawn_pet(bounds, platforms, x=x, y=y)
        pet = entry["pet"]
        # Jeder neu erzeugte Pet bekommt eine frische uid und einen eindeutigen
        # Namen (kein "Jr", keine Duplikate). Ein Baby behaelt diesen Namen; nur
        # Farbe/Waffe/Abstammung ueberschreibt make_baby danach.
        assign_uid(pet)
        pet.name = unique_name(exclude_uid=pet.uid)
        if randomize:
            pet.palette_index = random.randrange(len(config.PALETTES))
            pet.palette = config.PALETTES[pet.palette_index]
            pet.weapon_pref = random.choice(config.WEAPONS)
        if focus_active:
            entry["pet"].start_focus()
        pets.append(entry)
        return entry

    def release_entry(entry):
        """Tear down a culled pet's overlays. The menu window is kept alive
        (blanked + click-through) so the menu still works with zero pets."""
        nonlocal menu_overlay_free
        entry["fx"].close()
        if entry["overlay"] is menu_overlay:
            blank = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
            blank.fill(CLEAR)
            menu_overlay.show_surface(blank)
            menu_overlay.set_mouse_ignore(True)
            menu_overlay_free = True
        else:
            entry["overlay"].close()

    def living_pets():
        return [e for e in pets if not e["pet"].dying]

    def start_breeding(a=None, b=None):
        """Kick off a courtship (or, with no pets, just conjure a new one).
        Ohne Argumente werden zwei zufaellige lebende Pets gewaehlt; a/b koennen
        vom Pets-Tab explizit vorgegeben werden."""
        nonlocal courting, breed_cooldown
        if courting is not None:
            return
        living = living_pets()
        if len(living) >= MAX_PETS:
            if living:
                living[0]["pet"].start_talk("Too crowded!")
            return
        if breed_cooldown > 0:
            if living:
                living[0]["pet"].start_talk("Not yet!")
            return
        if not living:
            make_pet(randomize=True)  # nothing to breed from — start fresh
            breed_cooldown = BREED_COOLDOWN
            return
        if a is None or b is None:
            # Zufaellig zwei UNVERWANDTE Eltern (bei nur einem Pet zeugt es mit
            # sich selbst). Kein Inzest: verwandte Paare werden uebersprungen.
            if len(living) == 1:
                a = b = living[0]
            else:
                pairs = [
                    (x, y)
                    for i, x in enumerate(living)
                    for y in living[i + 1:]
                    if not lineage.are_related(x["pet"].uid, y["pet"].uid, family)
                ]
                if not pairs:
                    living[0]["pet"].start_talk("Too related!")
                    return
                a, b = random.choice(pairs)
        elif a is not b and lineage.are_related(a["pet"].uid, b["pet"].uid, family):
            # Vom Panel gezielt gewaehlte, aber verwandte Eltern -> ablehnen.
            a["pet"].start_talk("Too related!")
            return
        mid = (a["pet"].x + b["pet"].x) / 2 + WINDOW_W / 2
        a["pet"].court_to(mid)
        if b is not a:
            b["pet"].court_to(mid)
        courting = {"a": a, "b": b, "timer": 0}
        breed_cooldown = BREED_COOLDOWN

    while running:
        now = time.monotonic()
        primary.pump_events()
        if primary.should_quit():
            running = False
            continue

        drag = primary.consume_drag_state()
        mouse = primary.mouse_position()

        # System-wide input activity, shared by every pet this frame.
        idle_seconds = primary.seconds_since_input()
        key_count = primary.keydown_count()
        keys_this_frame = 0 if last_key_count is None else max(0, key_count - last_key_count)
        last_key_count = key_count

        for action in primary.consume_menu_actions():
            lead = pets[0]["pet"] if pets else None
            if action == "breed":
                start_breeding()
            elif action == "new_pet":
                if len(living_pets()) < MAX_PETS:
                    baby = make_pet(randomize=True)
                    baby["pet"].spawn_particles("star", 4)
                    record_family(baby["pet"])
                elif lead:
                    lead.start_talk("Too crowded!")
            elif action == "focus_start" and not focus_active:
                focus_active = True
                focus_frames_left = focus_total_frames
                for entry in pets:
                    entry["pet"].start_focus()
                if lead:
                    lead.start_talk("Focus time!")
            elif action == "focus_stop" and focus_active:
                focus_active = False
                for entry in pets:
                    entry["pet"].end_focus()
            elif action == "ball":
                if ball_overlay is None:
                    ball_overlay = MacOverlay(BALL_WIN, BALL_WIN, interactive=False)
                if lead is not None:
                    bx, by = lead.x + WINDOW_W / 2, lead.y - 50
                    lead.spawn_particles("star", 2)
                else:
                    bx = (bounds[0] + bounds[2]) / 2
                    by = (bounds[1] + bounds[3]) / 2
                ball = Ball(bx, by, bounds)
                ball.kick(random.uniform(-4.0, 4.0), -3.0)
                ball_overlay.reassert_top()  # re-show if it was hidden on removal
            elif action == "ball_remove" and ball is not None:
                ball_overlay.close()
                ball = None
            elif action == "snack":
                if snack_overlay is None:
                    snack_overlay = MacOverlay(SNACK_WIN, SNACK_WIN, interactive=False)
                if lead is not None:
                    # Ein Stueck neben den Leit-Pet legen, sodass er es findet.
                    sx = lead.x + WINDOW_W / 2 + random.uniform(-140, 140)
                    sy = lead.y + WINDOW_H - 6
                else:
                    sx = (bounds[0] + bounds[2]) / 2
                    sy = bounds[3] - 6
                sx = min(max(bounds[0] + 8, sx), bounds[2] - 8)
                snack = Snack(sx, sy)
                snack_overlay.reassert_top()
            elif action == "share_toggle":
                # Manueller Bildschirm-Teilen-Modus umschalten. Das Haekchen folgt
                # weiter unten dem manuellen Zustand; das eigentliche Aus-/Einblenden
                # macht die share_hidden-Transition.
                share_manual = not share_manual
                primary.set_share_hidden_check(share_manual)
            elif action == "settings":
                open_settings()
            elif action == "update" and not pending_update:
                # updater shows its own dialogs (up to date / found / failed);
                # we only act when it kicks off the download + relaunch.
                proj = os.path.dirname(os.path.abspath(__file__))
                if updater.check_for_updates(proj) == "updating":
                    if lead:
                        lead.start_talk("Updating!")
                    pending_update = 36  # show the bubble, then quit to relaunch

        if now - last_window_scan > 0.75:
            display_rects, bounds = primary.refresh_displays()
            window_tracker.set_desktop(display_rects, bounds)
            platforms = window_tracker.platforms()
            for entry in pets:
                entry["pet"].set_bounds(bounds)
                if not entry["pet"].airborne:
                    entry["pet"].sync_platforms(platforms)
            if ball is not None:
                ball.set_bounds(bounds)
            last_window_scan = now

        # App-aware reactions: notice what the human is doing and tell every pet
        # so it can show the matching prop (laptop / popcorn / headphones).
        if now - last_activity_scan > 0.5:
            bundle, app_name = primary.frontmost_app()
            title = (
                primary.active_window_title(app_name)
                if activity.needs_title(bundle, app_name)
                else ""
            )
            context = activity.classify(
                bundle, app_name, title, focus_active, playback_monitor.audio_active
            )
            music = playback_monitor.music_playing
            for entry in pets:
                entry["pet"].set_activity(context, music)
            last_activity_scan = now

        # Einstellungsfenster: vom Panel gemeldete Aktionen ausfuehren und ein
        # natives Schliessen (roter Fensterknopf) erkennen. Die Maus-Klicks selbst
        # kommen ueber den Hook (on_settings_mouse) rein, nicht hier.
        if settings_open and settings is not None:
            for act in settings.pop_actions():
                apply_settings_action(act)
            if settings_overlay is not None and not settings_overlay.visible():
                settings_open = False

        # Drag: only a gesture that actually moved counts as a drag, so a plain
        # click never sticks a pet as the drag target (which would freeze it).
        if drag["dragging"] and drag["moved"]:
            if drag_target is None and drag["position"]:
                drag_target = pet_under_point(pets, mouse)
            if drag_target and drag["position"]:
                # Cmd gedrueckt -> Leine (weiches Nachlaufen), sonst harter Drag/Wurf.
                if drag["leash"]:
                    drag_target["pet"].leash_to(*drag["position"])
                else:
                    drag_target["pet"].drag_to(*drag["position"])
        elif not drag["dragging"]:
            if drag_target and drag["released"] and drag["moved"]:
                # Leine: einfach stehen bleiben. Harter Drag: Flick wird zum Wurf.
                if drag_target["pet"].leashing:
                    drag_target["pet"].stop_leash()
                else:
                    drag_target["pet"].release()
            drag_target = None

        if drag["clicks"]:
            target = pet_under_point(pets, mouse) or (pets[0] if pets else None)
            if target and not target["pet"].dying:
                target["pet"].on_click(drag["clicks"], mouse)
                last_click_entry = target

        # Hover: der oberste Pet unter dem Cursor bekommt ein Namensschild (nur
        # wenn gerade nicht gezogen wird).
        hover_entry = None if drag["dragging"] else pet_under_point(pets, mouse)
        for entry in pets:
            entry["hover"] = entry is hover_entry

        world = platforms

        # Advance the fetch ball before the pets so they react to its new spot.
        if ball is not None:
            ball.update(world)

        # Snack: den naechstgelegenen ruhigen, nicht kaempfenden/fliegenden Pet
        # ansetzen, falls noch keiner unterwegs ist. Er laeuft selbst hin und isst.
        if snack is not None and not snack.eaten and not snack.claimed():
            candidates = [
                entry["pet"] for entry in pets
                if entry is not drag_target and entry["pet"].wants_snack(snack)
            ]
            if candidates:
                nearest = min(
                    candidates,
                    key=lambda p: abs(snack.x - (p.x + WINDOW_W / 2)),
                )
                nearest.send_to_snack(snack)
                snack.claimed_by = nearest

        for entry in pets:
            pet = entry["pet"]
            # Ein hart gezogener Pet wird per drag_to() direkt positioniert und
            # ueberspringt update(). Ein geleinter Pet dagegen laeuft dem Cursor
            # in update() (_update_leash) hinterher und muss darum durchlaufen.
            if entry is drag_target and not pet.leashing:
                continue
            # Other pets' centres, so this one can wander over and socialize.
            pet.observe_peers([
                (other["pet"].x + WINDOW_W / 2, other["pet"].y + WINDOW_H / 2)
                for other in pets
                if other is not entry
            ])
            pet.observe_activity(idle_seconds, keys_this_frame)
            if not drag["dragging"]:
                pet.observe_cursor(mouse)
            pet.update(world, mouse, ball)
            # An enraged pet that caught the cursor either flings it once
            # (cursor_grab) or pins it in place each frame (cursor_lock).
            if pet.cursor_grab is not None:
                primary.warp_cursor(*pet.cursor_grab)
                pet.cursor_grab = None
            if pet.cursor_lock is not None:
                primary.warp_cursor(*pet.cursor_lock)
            # Die vom Pet hochgezaehlten Ereignisse als Delta in die globalen
            # Lifetime-Stats ziehen (der Pet selbst kennt die Persistenz nicht).
            lifetime["victories"] += pet.stat_victories - entry.get("stat_v", 0)
            lifetime["balls"] += pet.stat_balls - entry.get("stat_b", 0)
            entry["stat_v"] = pet.stat_victories
            entry["stat_b"] = pet.stat_balls

        # Group behaviour: pets back each other up. A fighting adult rallies other
        # adults CLOSE to it into the fight, and any adult near a scared baby drops
        # everything to defend it (aiming at whatever spooked the baby). Only
        # nearby adults react, and only on a chance roll, so it never turns into an
        # instant screen-wide brawl. Babies never join.
        def _center(p):
            return (p.x + WINDOW_W / 2, p.y + WINDOW_H / 2)

        adults = [e["pet"] for e in pets if not e["pet"].baby and not e["pet"].dying]
        # Nur selbst wuetend gewordene Pets (per Klick) rekrutieren Nachbarn.
        # Rekrutierte Kaempfer kaempfen mit, ziehen aber niemanden nach — sonst
        # halten sich wuetende Pets endlos gegenseitig in Rage, und ein gerade
        # beruhigter wird vom Nachbarn sofort wieder angesteckt.
        fighters = [p for p in adults if p.rage and not p.recruited]
        threatened = [
            e["pet"] for e in pets
            if e["pet"].baby and e["pet"].needs_defense > 0
        ]
        if fighters or threatened:
            for pet in adults:
                if pet.rage or pet.scared:
                    continue
                px, py = _center(pet)
                # Defend a nearby threatened baby first — top priority.
                for baby in threatened:
                    bx, by = _center(baby)
                    if math.hypot(px - bx, py - by) <= BABY_DEFENSE_RADIUS:
                        pet.provoke_to_fight(GROUP_JOIN_ANGER, baby.threat_pos or mouse)
                        break
                else:
                    # Otherwise, maybe join a brawl already underway nearby.
                    for ally in fighters:
                        if ally is pet:
                            continue
                        ax, ay = _center(ally)
                        if (math.hypot(px - ax, py - ay) <= GROUP_SUPPORT_RADIUS
                                and random.random() < GROUP_JOIN_CHANCE):
                            pet.provoke_to_fight(GROUP_JOIN_ANGER, ally._aim or mouse)
                            break

        # Cull pets whose removal animation has finished, keeping the menu window
        # alive so the app stays usable even at zero pets.
        if any(entry["pet"].dead for entry in pets):
            for entry in pets:
                if entry["pet"].dead:
                    if entry is drag_target:
                        drag_target = None
                    release_entry(entry)
            pets = [entry for entry in pets if not entry["pet"].dead]

        # Courtship: drive the two parents together; when they meet they play a
        # short cuddle — facing each other under a shower of hearts — and only
        # THEN does a baby pop out at the midpoint, inheriting a blend of their
        # traits. A timeout still forces the meeting so it can't stall forever.
        if courting is not None:
            a_entry, b_entry = courting["a"], courting["b"]
            a_pet, b_pet = a_entry["pet"], b_entry["pet"]
            courting["timer"] += 1
            gone = (
                a_entry not in pets
                or b_entry not in pets
                or a_pet.dying or b_pet.dying
                or a_pet.rage or b_pet.rage
                or a_pet.scared or b_pet.scared
            )
            ready = a_pet.court_arrived and (b_pet is a_pet or b_pet.court_arrived)
            if gone:
                a_pet.stop_courting()
                b_pet.stop_courting()
                courting = None
            elif courting.get("meet", 0) > 0:
                # The breeding moment: hold still, face each other, shower hearts.
                courting["meet"] -= 1
                a_pet.facing_right = b_pet.x >= a_pet.x
                b_pet.facing_right = a_pet.x >= b_pet.x
                if random.random() < COURT_MEET_HEART_CHANCE:
                    a_pet.spawn_particles("heart", 1)
                if random.random() < COURT_MEET_HEART_CHANCE:
                    b_pet.spawn_particles("heart", 1)
                if courting["meet"] <= 0:
                    # Cuddle done — the baby arrives near its parents.
                    if len(living_pets()) < MAX_PETS:
                        midx = (a_pet.x + b_pet.x) / 2
                        midy = min(a_pet.y, b_pet.y)
                        baby = make_pet(x=midx, y=midy)
                        baby["pet"].make_baby(a_pet, b_pet)
                        record_family(baby["pet"])
                        a_pet.spawn_particles("heart", 5)
                        b_pet.spawn_particles("heart", 5)
                    a_pet.stop_courting()
                    b_pet.stop_courting()
                    courting = None
            elif ready or courting["timer"] >= COURT_TIMEOUT:
                # Arrived (or gave up chasing): freeze the pair and begin the
                # meeting with a big heart burst.
                courting["meet"] = COURT_MEET_FRAMES
                a_pet.court_arrived = True
                b_pet.court_arrived = True
                a_pet.vx = b_pet.vx = 0.0
                a_pet.spawn_particles("heart", 4)
                b_pet.spawn_particles("heart", 4)

        if breed_cooldown > 0:
            breed_cooldown -= 1

        # Pomodoro countdown: when the focus timer elapses, everyone celebrates.
        if focus_active:
            focus_frames_left -= 1
            if focus_frames_left <= 0:
                focus_active = False
                for entry in pets:
                    entry["pet"].end_focus(party=True)
                if pets:
                    pets[0]["pet"].start_talk("Break time!")

        # Bildschirm-Teilen: manueller Toggle ODER automatische Erkennung. Bei
        # aktivem Zustand alle Pet-Overlays einmalig blanken + click-through
        # setzen (gleiches Muster wie beim Entfernen eines Pets); die Simulation
        # laeuft unsichtbar weiter, es geht kein State/keine Position verloren.
        share_hidden = share_manual or share_monitor.sharing
        if share_hidden and not pets_hidden:
            blank = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
            blank.fill(CLEAR)
            fx_blank = pygame.Surface((FX_W, FX_H), pygame.SRCALPHA)
            fx_blank.fill(CLEAR)
            for entry in pets:
                entry["overlay"].show_surface(blank)
                entry["overlay"].set_mouse_ignore(True)
                entry["fx"].show_surface(fx_blank)
                entry["fx_visible"] = False
                entry["pet_key"] = None   # Wiederherstellung -> Neuzeichnen
                entry["pet_pos"] = None
            if ball_overlay is not None:
                ball_overlay.close()
            if snack_overlay is not None:
                snack_overlay.close()
            pets_hidden = True
        elif not share_hidden and pets_hidden:
            for entry in pets:
                entry["pet_key"] = None
                entry["pet_pos"] = None
                entry["fx_visible"] = False
                # Das Menue-Fenster bleibt geparkt, wenn es gerade keinen Pet hostet.
                if not (entry["overlay"] is menu_overlay and menu_overlay_free):
                    entry["overlay"].set_mouse_ignore(False)
            if ball is not None and ball_overlay is not None:
                ball_overlay.reassert_top()
            if snack is not None and snack_overlay is not None:
                snack_overlay.reassert_top()
            pets_hidden = False

        if not pets_hidden:
            for entry in pets:
                render_pet(entry, display_rects)

            if ball is not None:
                ball_overlay.move(
                    round(ball.x - BALL_WIN / 2), round(ball.y - BALL_WIN / 2)
                )
                ball_overlay.show_surface(draw_ball())

            # Snack zeichnen bzw. nach dem Essen entfernen. Der Byte-Dirty-Check in
            # show_surface haelt den Push billig (identisches Sprite jeden Frame).
            if snack is not None:
                if snack.eaten:
                    snack_overlay.close()
                    snack_overlay = None
                    snack = None
                else:
                    snack_overlay.move(
                        round(snack.x - SNACK_WIN / 2), round(snack.y - SNACK_WIN / 2)
                    )
                    snack_overlay.show_surface(draw_snack())

        # Einstellungsfenster mit aktuellem Kontext neu zeichnen (nur pushen, wenn
        # sich etwas geaendert hat). Liegt ganz oben.
        if settings_open and settings is not None:
            assign_pet_ids()
            pets_info = [
                {
                    "id": e["id"],
                    "uid": e["pet"].uid,
                    "name": e["pet"].name,
                    "palette_index": e["pet"].palette_index,
                    "generation": e["pet"].generation,
                    "baby": e["pet"].baby,
                    "weapon": e["pet"].weapon_pref,
                }
                for e in living_pets()
            ]
            if last_click_entry in pets and not last_click_entry["pet"].dying:
                focus_uid = last_click_entry["pet"].uid
            else:
                living = living_pets()
                focus_uid = living[-1]["pet"].uid if living else None
            playtime = lifetime["playtime_seconds"] + (time.monotonic() - session_start)
            # Register in das vom Panel erwartete Format bringen:
            # uid -> (name, generation, [eltern-uids]).
            lineage_info = {
                uid: (rec.get("name", "?"), rec.get("generation", 0), rec.get("parents", []))
                for uid, rec in family.items()
            }
            settings.set_context(
                pets_info,
                lineage_info,
                focus_uid,
                stats={
                    "victories": lifetime["victories"],
                    "balls": lifetime["balls"],
                    "playtime": _format_playtime(playtime),
                },
            )
            surf = settings.render()
            if settings.take_dirty():
                settings_overlay.show_surface(surf)

        if not pets_hidden and now - last_reassert > 0.5:
            for entry in pets:
                entry["overlay"].reassert_top()
                entry["fx"].reassert_top()
            if ball is not None:
                ball_overlay.reassert_top()
            if snack is not None and snack_overlay is not None:
                snack_overlay.reassert_top()
            last_reassert = now

        # After an update was requested, let the "Updating!" bubble show for a
        # few frames, then quit; update.sh waits for us to exit and relaunches.
        if pending_update:
            pending_update -= 1
            if pending_update == 0:
                running = False

        clock.tick(FPS)

    # Zustand aller lebenden Pets plus die Lifetime-Stats sichern (eine Datei).
    lifetime["playtime_seconds"] += time.monotonic() - session_start
    persistence.save({
        "version": persistence.STATE_VERSION,
        "next_uid": next_uid[0],
        "pets": [persistence.pet_to_dict(e["pet"]) for e in living_pets()],
        "stats": lifetime,
        # family ist uid-keyed; json macht die int-Schluessel zu Strings, beim
        # Laden werden sie wieder zu int geparst (siehe oben).
        "family": {str(uid): rec for uid, rec in family.items()},
    })

    playback_monitor.stop()
    share_monitor.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
