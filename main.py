"""Entry point and main loop for the desktop pet.

Wires the pieces together: one interactive `MacOverlay` per pet (the first one
also owns the menu-bar menu), a second non-interactive overlay per pet for
effects (speech bubble, particles, weapon), a shared `WindowTracker` for
platforms, and a `Pet` per pet for behaviour.

Supports multiple pets: the menu-bar "Breed" item spawns a child and
"Remove a pet" culls the most recent one. Slow strokes over a pet make it
love you; clicking it too often makes it arm itself and chase the cursor.
"""

import json
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
import playback
import updater

from ball import Ball
from config import (
    BALL_WIN,
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
    draw_flight_rig,
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


def _lineage_lookup(pets):
    """Name -> (Generation, Eltern-Namen). Speist sich aus den persistierten
    Pets (letzter Lauf) und den aktuell lebenden (frischer, ueberschreiben),
    damit die Abstammungslinie auch ueber Neustarts hinweg sichtbar bleibt."""
    lookup = {}
    for data in persistence.load_pets():
        name = data.get("name")
        if isinstance(name, str):
            parents = [p for p in data.get("parents", []) if isinstance(p, str)]
            gen = data.get("generation")
            lookup[name] = (gen if isinstance(gen, int) else 0, parents)
    for entry in pets:
        pet = entry["pet"]
        lookup[pet.name] = (pet.generation, list(pet.parents))
    return lookup


def _lineage_lines(name, lookup, depth=0, seen=None):
    """Die Abstammung als einfache, eingerueckte Textzeilen (kein grafischer
    Baum). Zyklen-/Tiefensicher."""
    if seen is None:
        seen = set()
    gen, parents = lookup.get(name, (None, []))
    label = name if gen is None else f"{name} (Gen {gen})"
    lines = [("   " * depth) + ("└ " if depth else "") + label]
    if name in seen or depth >= 8:
        return lines
    seen.add(name)
    for parent in parents:
        lines.extend(_lineage_lines(parent, lookup, depth + 1, seen))
    return lines


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

    if pet.talking or pet.particles or pet.weapon or pet.flying or pet.joy_flying:
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

    # Zustand vom letzten Lauf wiederherstellen: gespeicherte Pets neu erzeugen
    # (durch MAX_PETS begrenzt). Der erste Pet uebernimmt das Menue-Fenster.
    # Fehlt die Datei oder ist sie leer/kaputt, wie bisher genau ein Default-Pet.
    saved_state = persistence.load()
    saved_pets = saved_state.get("pets") or []
    pets = []
    for data in saved_pets[:MAX_PETS]:
        if not isinstance(data, dict):
            continue
        overlay = primary if not pets else None
        entry = spawn_pet(
            bounds, platforms, x=data.get("x"), y=data.get("y"), overlay=overlay
        )
        persistence.apply_dict(entry["pet"], data)
        entry["pet"].place_on_best_platform(platforms)
        pets.append(entry)
    if not pets:
        pets = [spawn_pet(bounds, platforms, overlay=primary)]

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
    # Self-update: spawn update.sh, show a bubble briefly, then quit so it can
    # pull the latest and relaunch. Counts down frames before quitting.
    pending_update = 0
    # Breeding: a courtship in progress (or None) plus a cooldown so it can't be
    # spammed.
    courting = None
    breed_cooldown = 0

    def open_settings():
        """prefs.json im Standard-Editor oeffnen (beim ersten Mal mit den
        aktuellen Default-Werten anlegen) und danach darauf hinweisen, dass
        Aenderungen erst nach einem Neustart greifen. config.py bleibt die
        Default-Quelle; prefs.json ueberschreibt selektiv."""
        path = persistence.prefs_path()
        if not os.path.exists(path):
            defaults = {name: getattr(config, name) for name in config.PREFS_SPEC}
            try:
                os.makedirs(persistence.state_dir(), exist_ok=True)
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(defaults, handle, ensure_ascii=False, indent=2)
            except OSError:
                pass
        primary.open_file(path)
        updater._alert(
            "Einstellungen in prefs.json bearbeiten.\n\nAenderungen werden beim "
            "naechsten Start uebernommen.",
            ["OK"],
            "OK",
        )

    def make_pet(x=None, y=None):
        """Spawn a fresh pet (appended to `pets`), reusing the menu window if it
        is free so the app recovers cleanly from zero pets."""
        nonlocal menu_overlay_free
        if menu_overlay_free:
            menu_overlay.set_mouse_ignore(False)
            entry = spawn_pet(bounds, platforms, x=x, y=y, overlay=menu_overlay)
            menu_overlay.reassert_top()
            menu_overlay_free = False
        else:
            entry = spawn_pet(bounds, platforms, x=x, y=y)
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

    def start_breeding():
        """Kick off a courtship (or, with no pets, just conjure a new one)."""
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
            make_pet()  # nothing to breed from — start over with a fresh pet
            breed_cooldown = BREED_COOLDOWN
            return
        if len(living) == 1:
            a = b = living[0]
        else:
            a, b = random.sample(living, 2)
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
            # Der "vorderste" Pet fuer pet-bezogene Infos: zuletzt angeklickt,
            # falls noch am Leben, sonst der oberste (zuletzt gespawnte) lebende.
            if last_click_entry in pets and not last_click_entry["pet"].dying:
                focus = last_click_entry["pet"]
            else:
                living = living_pets()
                focus = living[-1]["pet"] if living else lead
            if action == "breed":
                start_breeding()
            elif action == "new_pet":
                if len(living_pets()) < MAX_PETS:
                    baby = make_pet()
                    baby["pet"].spawn_particles("star", 4)
                elif lead:
                    lead.start_talk("Too crowded!")
            elif action == "remove":
                # Topmost living pet gets a dramatic send-off (then it's culled
                # once the animation finishes).
                victim = next(
                    (e for e in reversed(pets) if not e["pet"].dying), None
                )
                if victim:
                    victim["pet"].start_death()
                    if victim is drag_target:
                        drag_target = None
            elif action == "remove_all":
                living = living_pets()
                if living and _confirm_remove_all(len(living)):
                    for entry in living:
                        entry["pet"].start_death()
                    drag_target = None
                    if courting is not None:
                        courting = None
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
            elif action == "about" and focus:
                playtime = lifetime["playtime_seconds"] + (
                    time.monotonic() - session_start
                )
                char = focus.personality.get("name", "?")
                if focus.generation == 0:
                    lineage = "wild geboren"
                else:
                    parents = ", ".join(focus.parents) if focus.parents else "unbekannt"
                    lineage = f"Generation {focus.generation}, Eltern: {parents}"
                updater._alert(
                    f"{focus.name}\n"
                    f"Charakter: {char}\n"
                    f"Abstammung: {lineage}\n\n"
                    "Lifetime-Statistik (alle Pets):\n"
                    f"Gewonnene Kaempfe: {lifetime['victories']}\n"
                    f"Gefangene Baelle: {lifetime['balls']}\n"
                    f"Gesamt-Spielzeit: {_format_playtime(playtime)}",
                    ["OK"],
                    "OK",
                )
            elif action == "family" and focus:
                lookup = _lineage_lookup(pets)
                if focus.generation == 0 and not focus.parents:
                    body = f"{focus.name} ist wild geboren — keine Eltern bekannt."
                else:
                    body = "\n".join(_lineage_lines(focus.name, lookup))
                updater._alert(
                    f"Stammbaum von {focus.name}\n\n{body}",
                    ["OK"],
                    "OK",
                )
            elif action == "settings":
                open_settings()
            elif action == "recolour" and lead:
                lead.cycle_palette()
            elif action == "rename" and lead:
                lead.rename()
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

        # Drag: only a gesture that actually moved counts as a drag, so a plain
        # click never sticks a pet as the drag target (which would freeze it).
        if drag["dragging"] and drag["moved"]:
            if drag_target is None and drag["position"]:
                drag_target = pet_under_point(pets, mouse)
            if drag_target and drag["position"]:
                drag_target["pet"].drag_to(*drag["position"])
        elif not drag["dragging"]:
            if drag_target and drag["released"] and drag["moved"]:
                drag_target["pet"].release()
            drag_target = None

        if drag["clicks"]:
            target = pet_under_point(pets, mouse) or (pets[0] if pets else None)
            if target and not target["pet"].dying:
                target["pet"].on_click(drag["clicks"], mouse)
                last_click_entry = target

        world = platforms

        # Advance the fetch ball before the pets so they react to its new spot.
        if ball is not None:
            ball.update(world)

        for entry in pets:
            pet = entry["pet"]
            if entry is drag_target:
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

        for entry in pets:
            render_pet(entry, display_rects)

        if ball is not None:
            ball_overlay.move(round(ball.x - BALL_WIN / 2), round(ball.y - BALL_WIN / 2))
            ball_overlay.show_surface(draw_ball())

        if now - last_reassert > 0.5:
            for entry in pets:
                entry["overlay"].reassert_top()
                entry["fx"].reassert_top()
            if ball is not None:
                ball_overlay.reassert_top()
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
        "pets": [persistence.pet_to_dict(e["pet"]) for e in living_pets()],
        "stats": lifetime,
    })

    playback_monitor.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
