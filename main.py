"""Entry point and main loop for the desktop pet.

Wires the pieces together: one interactive `MacOverlay` per pet (the first one
also owns the menu-bar menu), a second non-interactive overlay per pet for
effects (speech bubble, particles, weapon), a shared `WindowTracker` for
platforms, and a `Pet` per pet for behaviour.

Supports multiple pets: the menu-bar "Breed" item spawns a short-lived child,
"Remove a pet" culls the most recent one. Slow strokes over a pet make it
love you; clicking it too often makes it arm itself and chase the cursor.
"""

import random
import signal
import sys
import time

import pygame

from config import (
    BUBBLE_GAP,
    CHILD_LIFESPAN_MAX,
    CHILD_LIFESPAN_MIN,
    CLEAR,
    FPS,
    FX_H,
    FX_W,
    MAX_PETS,
    WINDOW_H,
    WINDOW_W,
)
from overlay import MacOverlay
from pet import Pet
from render import draw_pet_frame, draw_speech_bubble, draw_weapon, particle_sprite
from window_tracker import WindowTracker


def spawn_pet(bounds, platforms, x=None, y=None, child=False, overlay=None):
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
    if child:
        pet.life = random.randint(CHILD_LIFESPAN_MIN, CHILD_LIFESPAN_MAX)
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


def render_pet(entry):
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
        # Keep the effects window fully on the desktop; otherwise macOS shoves
        # it back on-screen (notably near the bottom edge), which fights our
        # per-frame move and makes the bubble flicker.
        origin_x = max(pet.min_x, min(pet.max_x - FX_W, origin_x))
        origin_y = max(pet.min_y, min(pet.max_y - FX_H, origin_y))
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
    display_rects, bounds = primary.refresh_displays()
    window_tracker = WindowTracker(display_rects, bounds)
    platforms = window_tracker.platforms()

    # The first pet reuses the menu-owning primary overlay created above.
    pets = [spawn_pet(bounds, platforms, overlay=primary)]

    clock = pygame.time.Clock()
    last_reassert = 0.0
    last_window_scan = 0.0
    drag_target = None

    while running:
        now = time.monotonic()
        primary.pump_events()
        if primary.should_quit():
            running = False
            continue

        drag = primary.consume_drag_state()
        mouse = primary.mouse_position()

        for action in primary.consume_menu_actions():
            if action == "breed" and len(pets) < MAX_PETS:
                parent = random.choice(pets)["pet"]
                offset = random.choice([-1, 1]) * (WINDOW_W + 12)
                child = spawn_pet(
                    bounds,
                    platforms,
                    x=parent.x + offset,
                    y=parent.y,
                    child=True,
                )
                parent.spawn_particles("heart", 4)
                pets.append(child)
            elif action == "remove" and len(pets) > 1:
                removed = pets.pop()
                removed["overlay"].close()
                removed["fx"].close()
                if removed is drag_target:
                    drag_target = None

        if now - last_window_scan > 0.75:
            display_rects, bounds = primary.refresh_displays()
            window_tracker.set_desktop(display_rects, bounds)
            platforms = window_tracker.platforms()
            for entry in pets:
                entry["pet"].set_bounds(bounds)
                if not entry["pet"].airborne:
                    entry["pet"].sync_platforms(platforms)
            last_window_scan = now

        # Drag: only a gesture that actually moved counts as a drag, so a plain
        # click never sticks a pet as the drag target (which would freeze it).
        if drag["dragging"] and drag["moved"]:
            if drag_target is None and drag["position"]:
                drag_target = pet_under_point(pets, mouse) or pets[0]
            if drag_target and drag["position"]:
                drag_target["pet"].drag_to(*drag["position"])
        elif not drag["dragging"]:
            if drag_target and drag["released"] and drag["moved"]:
                drag_target["pet"].drop()
            drag_target = None

        if drag["clicks"]:
            target = pet_under_point(pets, mouse) or pets[0]
            target["pet"].on_click(drag["clicks"], mouse)

        for entry in pets:
            pet = entry["pet"]
            if entry is drag_target:
                continue
            if not drag["dragging"]:
                pet.observe_cursor(mouse)
            pet.update(platforms, mouse)

        # Age out bred children whose lifespan has elapsed.
        survivors = [pets[0]]
        for entry in pets[1:]:
            pet = entry["pet"]
            if pet.life is not None:
                pet.life -= 1
                if pet.life <= 0:
                    entry["overlay"].close()
                    entry["fx"].close()
                    if entry is drag_target:
                        drag_target = None
                    continue
            survivors.append(entry)
        pets = survivors

        for entry in pets:
            render_pet(entry)

        if now - last_reassert > 0.5:
            for entry in pets:
                entry["overlay"].reassert_top()
                entry["fx"].reassert_top()
            last_reassert = now

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
