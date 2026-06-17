"""Entry point and main loop for the desktop pet.

Wires the pieces together: an interactive `MacOverlay` for the pet, a second
non-interactive overlay for effects (speech bubble + particles), a
`WindowTracker` for platforms, and a `Pet` for behaviour. Each frame it pumps
events, updates the pet, and pushes freshly drawn surfaces to both overlays.
"""

import signal
import sys
import time

import pygame

from config import BUBBLE_GAP, CLEAR, FPS, FX_H, FX_W, WINDOW_H, WINDOW_W
from overlay import MacOverlay
from pet import Pet
from render import draw_pet_frame, draw_speech_bubble, particle_sprite
from window_tracker import WindowTracker


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
    overlay = MacOverlay(WINDOW_W, WINDOW_H)
    fx = MacOverlay(FX_W, FX_H, interactive=False)
    display_rects, bounds = overlay.refresh_displays()
    window_tracker = WindowTracker(display_rects, bounds)
    platforms = window_tracker.platforms()
    pet = Pet(bounds)
    pet.place_on_best_platform(platforms)
    canvas = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    fx_canvas = pygame.Surface((FX_W, FX_H), pygame.SRCALPHA)
    clock = pygame.time.Clock()
    last_reassert = 0.0
    last_window_scan = 0.0
    fx_visible = False

    while running:
        now = time.monotonic()
        overlay.pump_events()
        if overlay.should_quit():
            running = False
            continue
        drag = overlay.consume_drag_state()
        mouse = overlay.mouse_position()

        if now - last_window_scan > 0.75:
            display_rects, bounds = overlay.refresh_displays()
            window_tracker.set_desktop(display_rects, bounds)
            pet.set_bounds(bounds)
            platforms = window_tracker.platforms()
            if not pet.airborne:
                pet.sync_platforms(platforms)
            last_window_scan = now

        if drag["moved"] and drag["position"] and (drag["dragging"] or drag["released"]):
            pet.drag_to(*drag["position"])
        if drag["released"] and drag["moved"]:
            pet.drop()
        if drag["clicks"]:
            pet.on_click(drag["clicks"], mouse)

        if not drag["dragging"]:
            pet.update(platforms, mouse)

        canvas.fill(CLEAR)
        canvas.blit(draw_pet_frame(pet), (0, 0))

        overlay.move(round(pet.x), round(pet.y))
        overlay.show_surface(canvas)

        if pet.talking or pet.particles:
            origin_x = round(pet.x + WINDOW_W / 2 - FX_W / 2)
            origin_y = round(pet.y + WINDOW_H / 2 - FX_H / 2)
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
                bx = (FX_W - surf.get_width()) // 2
                if pet.speech_tail_up:
                    by = round(pet.y + WINDOW_H - origin_y - BUBBLE_GAP)
                else:
                    by = round(pet.y - origin_y - surf.get_height() + BUBBLE_GAP)
                fx_canvas.blit(surf, (bx, by))

            fx.move(origin_x, origin_y)
            fx.show_surface(fx_canvas)
            fx_visible = True
        elif fx_visible:
            fx_canvas.fill(CLEAR)
            fx.show_surface(fx_canvas)
            fx_visible = False

        if now - last_reassert > 0.5:
            overlay.reassert_top()
            fx.reassert_top()
            last_reassert = now

        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
