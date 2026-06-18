"""Generate the macOS app icon (icon.icns) from the pet sprite.

Renders a rounded, gradient app-icon tile with the pet on it, then uses the
system `sips`/`iconutil` to assemble a multi-resolution .icns. Re-run this
whenever the sprite changes:  python make_icon.py
"""

import os
import subprocess
import tempfile

import pygame

from pet import Pet, State
from render import draw_pet_frame

SIZE = 1024
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def render_icon():
    pygame.init()
    icon = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    icon.fill((0, 0, 0, 0))

    # Soft sky-to-teal vertical gradient so the warm pet pops.
    top, bottom = (188, 229, 243), (92, 167, 209)
    gradient = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    for y in range(SIZE):
        colour = _lerp(top, bottom, y / SIZE)
        pygame.draw.line(gradient, (*colour, 255), (0, y), (SIZE, y))

    # Clip the gradient to the rounded "squircle-ish" app-icon shape.
    mask = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 0))
    pygame.draw.rect(
        mask, (255, 255, 255, 255), (0, 0, SIZE, SIZE), border_radius=int(SIZE * 0.224)
    )
    gradient.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    icon.blit(gradient, (0, 0))

    # The pet, upscaled crisply (nearest-neighbour keeps the pixel-art look).
    pet = Pet((0, 0, 1440, 900))
    pet.state = State.IDLE
    pet.frame = 0
    pet.facing_right = True
    pet.look_offset = 0
    pet.blink = False
    sprite = draw_pet_frame(pet)
    scale = 12
    pet_img = pygame.transform.scale(
        sprite, (sprite.get_width() * scale, sprite.get_height() * scale)
    )
    pw, ph = pet_img.get_size()
    px = (SIZE - pw) // 2
    py = (SIZE - ph) // 2 + 30

    # A soft grounding shadow (stacked translucent ellipses, since we have no blur).
    shadow = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    cx = SIZE // 2
    ey = py + ph - 78
    for i, (rw, alpha) in enumerate([(0.46, 26), (0.38, 38), (0.30, 52)]):
        w = int(pw * rw)
        h = int(w * 0.3)
        pygame.draw.ellipse(shadow, (38, 60, 82, alpha), (cx - w // 2, ey - h // 2 + i * 4, w, h))
    icon.blit(shadow, (0, 0))
    icon.blit(pet_img, (px, py))
    return icon


def main():
    icon = render_icon()
    tmp = tempfile.mkdtemp()
    tga = os.path.join(tmp, "icon.tga")
    pygame.image.save(icon, tga)  # TGA keeps the alpha channel
    png = os.path.join(tmp, "icon_1024.png")
    subprocess.run(
        ["sips", "-s", "format", "png", tga, "--out", png],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    iconset = os.path.join(tmp, "icon.iconset")
    os.makedirs(iconset, exist_ok=True)
    entries = [
        (16, "16x16"), (32, "16x16@2x"), (32, "32x32"), (64, "32x32@2x"),
        (128, "128x128"), (256, "128x128@2x"), (256, "256x256"),
        (512, "256x256@2x"), (512, "512x512"), (1024, "512x512@2x"),
    ]
    for size, name in entries:
        out = os.path.join(iconset, f"icon_{name}.png")
        subprocess.run(
            ["sips", "-z", str(size), str(size), png, "--out", out],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    icns = os.path.join(PROJECT_DIR, "icon.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    # Keep a PNG preview alongside for the README / quick look.
    subprocess.run(
        ["sips", "-s", "format", "png", tga, "--out", os.path.join(PROJECT_DIR, "icon.png")],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print("Wrote", icns)


if __name__ == "__main__":
    main()
