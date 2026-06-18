"""Entry point and main loop for the desktop pet.

Wires the pieces together: one interactive `MacOverlay` per pet (the first one
also owns the menu-bar menu), a second non-interactive overlay per pet for
effects (speech bubble, particles, weapon), a shared `WindowTracker` for
platforms, and a `Pet` per pet for behaviour.

Supports multiple pets: the menu-bar "Breed" item spawns a child and
"Remove a pet" culls the most recent one. Slow strokes over a pet make it
love you; clicking it too often makes it arm itself and chase the cursor.
"""

import os
import random
import signal
import sys
import time

import pygame

import activity
import playback
import updater

from ball import Ball
from config import (
    BALL_WIN,
    BUBBLE_GAP,
    CLEAR,
    FOCUS_MINUTES,
    FPS,
    FX_H,
    FX_W,
    MAX_PETS,
    WINDOW_H,
    WINDOW_W,
)
from overlay import MacOverlay
from pet import Pet
from render import (
    draw_ball,
    draw_pet_frame,
    draw_speech_bubble,
    draw_weapon,
    particle_sprite,
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


def pet_under_point(pets, point):
    """Topmost (most recently spawned) pet whose hitbox contains point."""
    if point is None:
        return None
    px, py = point
    for entry in reversed(pets):
        pet = entry["pet"]
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

    canvas.fill(CLEAR)
    canvas.blit(draw_pet_frame(pet), (0, 0))
    overlay.move(round(pet.x), round(pet.y))
    overlay.show_surface(canvas)

    if pet.talking or pet.particles or pet.weapon:
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
            sprite.set_alpha(int(255 * max(0.0, min(1.0, p["life"] / p["maxlife"]))))
            fx_canvas.blit(
                sprite,
                (
                    round(p["x"] - origin_x - sprite.get_width() / 2),
                    round(p["y"] - origin_y - sprite.get_height() / 2),
                ),
            )

        if pet.weapon:
            weapon = draw_weapon(pet.weapon)
            if not pet.facing_right:
                weapon = pygame.transform.flip(weapon, True, False)
            hand_y = pet_top + int(WINDOW_H * 0.45)
            if pet.facing_right:
                wx = pet_left + WINDOW_W - 8
            else:
                wx = pet_left + 8 - weapon.get_width()
            fx_canvas.blit(weapon, (wx, hand_y))

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
    # Window titles (used to spot a YouTube tab in any browser) need Screen
    # Recording permission; prompt once if it hasn't been decided yet.
    primary.ensure_screen_recording()
    display_rects, bounds = primary.refresh_displays()
    window_tracker = WindowTracker(display_rects, bounds)
    platforms = window_tracker.platforms()

    # The first pet reuses the menu-owning primary overlay created above.
    pets = [spawn_pet(bounds, platforms, overlay=primary)]

    # Polls media playback off-thread (music play state + whether sound is
    # actually playing) so the 60 fps loop never blocks on osascript.
    playback_monitor = playback.PlaybackMonitor()

    clock = pygame.time.Clock()
    last_reassert = 0.0
    last_window_scan = 0.0
    last_activity_scan = 0.0
    drag_target = None
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
            if action == "breed" and len(pets) < MAX_PETS:
                parent = random.choice(pets)["pet"]
                mate = random.choice(pets)["pet"]
                offset = random.choice([-1, 1]) * (WINDOW_W + 12)
                child = spawn_pet(
                    bounds,
                    platforms,
                    x=parent.x + offset,
                    y=parent.y,
                )
                # The child's temperament is a blend of two pets'.
                child["pet"].inherit_personality(parent.personality, mate.personality)
                parent.spawn_particles("heart", 4)
                if focus_active:
                    child["pet"].start_focus()
                pets.append(child)
            elif action == "remove" and len(pets) > 1:
                removed = pets.pop()
                removed["overlay"].close()
                removed["fx"].close()
                if removed is drag_target:
                    drag_target = None
            elif action == "focus_start" and not focus_active:
                focus_active = True
                focus_frames_left = focus_total_frames
                for entry in pets:
                    entry["pet"].start_focus()
                pets[0]["pet"].start_talk("Focus time!")
            elif action == "focus_stop" and focus_active:
                focus_active = False
                for entry in pets:
                    entry["pet"].end_focus()
            elif action == "ball":
                lead = pets[0]["pet"]
                if ball_overlay is None:
                    ball_overlay = MacOverlay(BALL_WIN, BALL_WIN, interactive=False)
                ball = Ball(lead.x + WINDOW_W / 2, lead.y - 50, bounds)
                ball.kick(random.uniform(-4.0, 4.0), -3.0)
                ball_overlay.reassert_top()  # re-show if it was hidden on removal
                lead.spawn_particles("star", 2)
            elif action == "ball_remove" and ball is not None:
                ball_overlay.close()
                ball = None
            elif action == "recolour":
                pets[0]["pet"].cycle_palette()
            elif action == "rename":
                pets[0]["pet"].rename()
            elif action == "update" and not pending_update:
                # updater shows its own dialogs (up to date / found / failed);
                # we only act when it kicks off the download + relaunch.
                proj = os.path.dirname(os.path.abspath(__file__))
                if updater.check_for_updates(proj) == "updating":
                    pets[0]["pet"].start_talk("Updating!")
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
                drag_target = pet_under_point(pets, mouse) or pets[0]
            if drag_target and drag["position"]:
                drag_target["pet"].drag_to(*drag["position"])
        elif not drag["dragging"]:
            if drag_target and drag["released"] and drag["moved"]:
                drag_target["pet"].release()
            drag_target = None

        if drag["clicks"]:
            target = pet_under_point(pets, mouse) or pets[0]
            target["pet"].on_click(drag["clicks"], mouse)

        # Advance the fetch ball before the pets so they react to its new spot.
        if ball is not None:
            ball.update(platforms)

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
            pet.update(platforms, mouse, ball)
            # An enraged pet that caught the cursor either flings it once
            # (cursor_grab) or pins it in place each frame (cursor_lock).
            if pet.cursor_grab is not None:
                primary.warp_cursor(*pet.cursor_grab)
                pet.cursor_grab = None
            if pet.cursor_lock is not None:
                primary.warp_cursor(*pet.cursor_lock)

        # Pomodoro countdown: when the focus timer elapses, everyone celebrates.
        if focus_active:
            focus_frames_left -= 1
            if focus_frames_left <= 0:
                focus_active = False
                for entry in pets:
                    entry["pet"].end_focus(party=True)
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

    playback_monitor.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
