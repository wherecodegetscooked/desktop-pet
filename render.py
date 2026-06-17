"""All pixel drawing: the pet sprite, the speech bubble, and particles.

Everything here is pure rendering — it takes plain data (a `Pet`, a string, a
particle kind) and returns pygame surfaces. The hand-rolled 5x7 bitmap font
keeps the retro look without an SDL_ttf dependency.
"""

import pygame

from config import (
    ANGER_COLOR,
    BELLY_COLOR,
    BUBBLE_FILL_COLOR,
    BUBBLE_MAX_TEXT_W,
    BUBBLE_SCALE,
    BUBBLE_TEXT_COLOR,
    CLEAR,
    DUST_COLOR,
    EYE_COLOR,
    EYE_WHITE,
    GUARD_COLOR,
    GUN_COLOR,
    GUN_GRIP_COLOR,
    HANDLE_COLOR,
    HEART_COLOR,
    HIGHLIGHT,
    PARTICLE_SCALE,
    PET_COLOR,
    PET_SHADE,
    SPRITE_H,
    SPRITE_W,
    STAR_COLOR,
    STEEL_COLOR,
    WEAPON_SCALE,
    WINDOW_H,
    WINDOW_W,
    ZZZ_COLOR,
)
from pet import State

BLUSH_COLOR = (255, 150, 170, 255)


def px(surface, x, y, color):
    if 0 <= x < SPRITE_W and 0 <= y < SPRITE_H:
        surface.set_at((x, y), color)


def rect(surface, x, y, w, h, color):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            px(surface, xx, yy, color)


# Hand-rolled 5x7 pixel font (SDL_ttf is unavailable on this Python build, and
# a bitmap font keeps the retro look and the bundle dependency-free). Text is
# upper-cased before rendering. Unknown glyphs fall back to "?".
GLYPH_W = 5
GLYPH_H = 7
SPACE_W = 3
GLYPH_GAP = 1
LINE_GAP = 2

FONT_5x7 = {
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ####", "#    ", "#    ", "#  ##", "#   #", "#   #", " ####"],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "J": ["#####", "    #", "    #", "    #", "#   #", "#   #", " ### "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "# # #", "#  ##", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "!": ["  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "],
    "?": [" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "],
    ".": ["     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "],
    ",": ["     ", "     ", "     ", "     ", " ##  ", " ##  ", "#    "],
    "'": ["  #  ", "  #  ", "  #  ", "     ", "     ", "     ", "     "],
    "-": ["     ", "     ", "     ", "#####", "     ", "     ", "     "],
    ":": ["     ", " ##  ", " ##  ", "     ", " ##  ", " ##  ", "     "],
}


def _char_width(ch):
    if ch == " ":
        return SPACE_W
    return GLYPH_W


def _text_width(text):
    width = 0
    for ch in text:
        width += _char_width(ch) + GLYPH_GAP
    return max(0, width - GLYPH_GAP)


def _wrap_lines(text, max_w):
    lines = []
    current = ""
    for word in text.split():
        trial = word if not current else current + " " + word
        if _text_width(trial) <= max_w or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def render_pixel_text(text, color):
    text = text.upper()
    width = max(1, _text_width(text))
    surface = pygame.Surface((width, GLYPH_H), pygame.SRCALPHA)
    surface.fill(CLEAR)
    x = 0
    for ch in text:
        if ch == " ":
            x += SPACE_W + GLYPH_GAP
            continue
        glyph = FONT_5x7.get(ch, FONT_5x7["?"])
        for row, line in enumerate(glyph):
            for col, cell in enumerate(line):
                if cell == "#":
                    surface.set_at((x + col, row), color)
        x += GLYPH_W + GLYPH_GAP
    return surface


def draw_speech_bubble(text, tail_up=False):
    """Render a pixel speech bubble: cream box, dark border, and a tail that
    points down at the pet (default) or up at it (when the pet is near the top
    of the screen and the bubble sits below it)."""
    lines = _wrap_lines(text, BUBBLE_MAX_TEXT_W)
    rendered = [render_pixel_text(line, BUBBLE_TEXT_COLOR) for line in lines]
    line_h = GLYPH_H + LINE_GAP
    text_w = max(s.get_width() for s in rendered)
    text_h = line_h * len(rendered) - LINE_GAP

    pad = 3
    border = 1
    tail_h = 4
    tail_w = 8
    body_w = text_w + pad * 2 + border * 2
    body_h = text_h + pad * 2 + border * 2
    body_top = tail_h if tail_up else 0
    base = pygame.Surface((body_w, body_h + tail_h), pygame.SRCALPHA)
    base.fill(CLEAR)

    body = pygame.Rect(0, body_top, body_w, body_h)
    pygame.draw.rect(base, BUBBLE_TEXT_COLOR, body)
    pygame.draw.rect(
        base,
        BUBBLE_FILL_COLOR,
        pygame.Rect(border, body_top + border, body_w - border * 2, body_h - border * 2),
    )
    # Trim the four corner pixels for a softly rounded pixel edge.
    for corner in [
        (0, body_top),
        (body_w - 1, body_top),
        (0, body_top + body_h - 1),
        (body_w - 1, body_top + body_h - 1),
    ]:
        base.set_at(corner, CLEAR)

    for i, surface in enumerate(rendered):
        x = border + pad + (text_w - surface.get_width()) // 2
        base.blit(surface, (x, body_top + border + pad + i * line_h))

    cx = body_w // 2
    if tail_up:
        # Tail at the top, apex pointing up.
        pygame.draw.polygon(
            base,
            BUBBLE_TEXT_COLOR,
            [(cx - tail_w // 2, tail_h), (cx + tail_w // 2, tail_h), (cx, 0)],
        )
        pygame.draw.polygon(
            base,
            BUBBLE_FILL_COLOR,
            [(cx - tail_w // 2 + 1, tail_h + 1), (cx + tail_w // 2 - 1, tail_h + 1), (cx, 2)],
        )
    else:
        # Tail at the bottom, apex pointing down.
        pygame.draw.polygon(
            base,
            BUBBLE_TEXT_COLOR,
            [(cx - tail_w // 2, body_h - 1), (cx + tail_w // 2, body_h - 1), (cx, body_h - 1 + tail_h)],
        )
        pygame.draw.polygon(
            base,
            BUBBLE_FILL_COLOR,
            [(cx - tail_w // 2 + 1, body_h - 2), (cx + tail_w // 2 - 1, body_h - 2), (cx, body_h - 3 + tail_h)],
        )

    return pygame.transform.scale(
        base, (base.get_width() * BUBBLE_SCALE, base.get_height() * BUBBLE_SCALE)
    )


# Pixel particle sprites, built lazily after pygame is initialised.
HEART_PIXELS = [
    " ## ## ",
    "#######",
    "#######",
    " ##### ",
    "  ###  ",
    "   #   ",
]
STAR_PIXELS = [
    "   #   ",
    "   #   ",
    "## # ##",
    " ##### ",
    "  ###  ",
    " ## ## ",
    "##   ##",
]
ZZZ_PIXELS = [
    "#####",
    "   # ",
    "  #  ",
    " #   ",
    "#####",
]
DUST_PIXELS = [
    " ## ",
    "####",
    " ## ",
]
PARTICLE_PIXELS = {
    "heart": (HEART_PIXELS, HEART_COLOR),
    "star": (STAR_PIXELS, STAR_COLOR),
    "anger": (STAR_PIXELS, ANGER_COLOR),
    "zzz": (ZZZ_PIXELS, ZZZ_COLOR),
    "dust": (DUST_PIXELS, DUST_COLOR),
}
_PARTICLE_CACHE = {}


def particle_sprite(kind):
    sprite = _PARTICLE_CACHE.get(kind)
    if sprite is None:
        pattern, color = PARTICLE_PIXELS[kind]
        h = len(pattern)
        w = len(pattern[0])
        base = pygame.Surface((w, h), pygame.SRCALPHA)
        base.fill(CLEAR)
        for y, row in enumerate(pattern):
            for x, cell in enumerate(row):
                if cell == "#":
                    base.set_at((x, y), color)
        sprite = pygame.transform.scale(base, (w * PARTICLE_SCALE, h * PARTICLE_SCALE))
        _PARTICLE_CACHE[kind] = sprite
    return sprite


# Pixel weapons, drawn pointing right (the main loop flips them to match the
# pet's facing). Each maps pattern characters to colours.
KNIFE_PIXELS = [
    "        #   ",
    "==== #####  ",
    "==== #######",
    "==== #####  ",
    "        #   ",
]
SWORD_PIXELS = [
    "   |            ",
    "===|############",
    "===|############",
    "===|############",
    "   |            ",
]
PISTOL_PIXELS = [
    "  ######    ",
    "  #######   ",
    "=########   ",
    "==###       ",
    " ==         ",
    "            ",
]
WEAPON_PIXELS = {
    "knife": (KNIFE_PIXELS, {"#": STEEL_COLOR, "=": HANDLE_COLOR}),
    "sword": (SWORD_PIXELS, {"#": STEEL_COLOR, "|": GUARD_COLOR, "=": HANDLE_COLOR}),
    "pistol": (PISTOL_PIXELS, {"#": GUN_COLOR, "=": GUN_GRIP_COLOR}),
}
_WEAPON_CACHE = {}


def draw_weapon(kind):
    """Return a scaled weapon sprite, pointing right, cached per kind."""
    sprite = _WEAPON_CACHE.get(kind)
    if sprite is None:
        pattern, colors = WEAPON_PIXELS[kind]
        h = len(pattern)
        w = len(pattern[0])
        base = pygame.Surface((w, h), pygame.SRCALPHA)
        base.fill(CLEAR)
        for y, row in enumerate(pattern):
            for x, cell in enumerate(row):
                color = colors.get(cell)
                if color is not None:
                    base.set_at((x, y), color)
        sprite = pygame.transform.scale(base, (w * WEAPON_SCALE, h * WEAPON_SCALE))
        _WEAPON_CACHE[kind] = sprite
    return sprite


def draw_pet_frame(pet):
    small = pygame.Surface((SPRITE_W, SPRITE_H), pygame.SRCALPHA)
    small.fill(CLEAR)

    bob = 0
    if pet.state in (State.WALK, State.RUN):
        step_speed = 7 if pet.state == State.WALK else 4
        bob = 1 if (pet.frame // step_speed) % 2 else 0
    if pet.state == State.JUMP:
        bob = -1

    body_y = 4 + bob
    rect(small, 5, body_y + 1, 10, 8, PET_COLOR)
    rect(small, 4, body_y + 3, 12, 5, PET_COLOR)
    rect(small, 7, body_y + 6, 6, 4, BELLY_COLOR)
    rect(small, 6, body_y + 1, 2, 1, HIGHLIGHT)
    rect(small, 13, body_y + 4, 2, 4, PET_SHADE)

    # Ears
    px(small, 5, body_y, PET_COLOR)
    px(small, 6, body_y - 1, PET_COLOR)
    px(small, 14, body_y, PET_COLOR)
    px(small, 13, body_y - 1, PET_COLOR)

    # Arms
    arm_swing = 1 if (pet.frame // 7) % 2 else 0
    if pet.state == State.IDLE:
        arm_swing = 0
    rect(small, 3, body_y + 6 - arm_swing, 2, 2, PET_COLOR)
    rect(small, 15, body_y + 5 + arm_swing, 2, 2, PET_COLOR)

    # Legs
    phase = (pet.frame // (7 if pet.state == State.WALK else 4)) % 2
    leg_lift = pet.state in (State.WALK, State.RUN)
    for i, leg_x in enumerate([6, 9, 12, 14]):
        lifted = leg_lift and (i % 2 == phase)
        leg_h = 1 if lifted else 3
        rect(small, leg_x, body_y + 9, 1, leg_h, PET_SHADE)

    # Face
    eye_y = body_y + 4
    left_eye_x = 7 + pet.look_offset
    right_eye_x = 12 + pet.look_offset
    if pet.asleep:
        # Closed, peaceful eyes: soft downward curls. Fixed in place (no glancing
        # with look_offset) since the eyes are shut while he sleeps.
        for ex in (7, 12):
            px(small, ex - 1, eye_y, EYE_COLOR)
            px(small, ex, eye_y + 1, EYE_COLOR)
            px(small, ex + 1, eye_y, EYE_COLOR)
    elif pet.excited:
        # Wide-awake excited eyes: tall and dark with a bright catchlight. The
        # grin sells the excitement, so the eyes stay mostly dark.
        for sx in (7, 11):
            rect(small, sx, eye_y - 1, 2, 3, EYE_COLOR)
            px(small, sx, eye_y - 1, EYE_WHITE)
    elif pet.bored:
        # Heavy-lidded, sleepy eyes: a brown lid droops over the top of a small
        # dark eye, so he looks tired instead of having a hard black monoline.
        for sx in (7, 11):
            rect(small, sx, eye_y, 2, 2, EYE_COLOR)
            rect(small, sx, eye_y, 2, 1, PET_SHADE)
            px(small, sx, eye_y + 1, EYE_WHITE)
    elif pet.loved and not pet.angry:
        # Smitten: happy upward-arc eyes and rosy cheeks.
        for ex in (left_eye_x, right_eye_x):
            px(small, ex - 1, eye_y + 1, EYE_COLOR)
            px(small, ex, eye_y, EYE_COLOR)
            px(small, ex + 1, eye_y + 1, EYE_COLOR)
        px(small, left_eye_x - 1, eye_y + 2, BLUSH_COLOR)
        px(small, right_eye_x + 1, eye_y + 2, BLUSH_COLOR)
    elif pet.blink:
        rect(small, left_eye_x, eye_y + 1, 2, 1, EYE_COLOR)
        rect(small, right_eye_x, eye_y + 1, 2, 1, EYE_COLOR)
    else:
        # Normal: a dark eye with a single white catchlight that glances around
        # with look_offset - friendly and alive, but not a wide white sclera.
        look = max(-1, min(1, pet.look_offset))
        for sx in (7, 11):
            ex = sx + look
            rect(small, ex, eye_y, 2, 2, EYE_COLOR)
            px(small, ex, eye_y, EYE_WHITE)

    if pet.angry:
        # Slanted brows (high on the outside, low toward the nose). Anchored to
        # the fixed eye columns so they sit over the (non-glancing) angry eyes.
        px(small, 6, eye_y - 2, EYE_COLOR)
        px(small, 7, eye_y - 1, EYE_COLOR)
        px(small, 13, eye_y - 2, EYE_COLOR)
        px(small, 12, eye_y - 1, EYE_COLOR)

    mouth_y = body_y + 7
    if pet.asleep:
        # Small open sleeping mouth.
        px(small, 10, mouth_y, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
    elif pet.angry:
        # Downturned frown.
        px(small, 8, mouth_y + 1, EYE_COLOR)
        px(small, 9, mouth_y, EYE_COLOR)
        px(small, 10, mouth_y, EYE_COLOR)
        px(small, 11, mouth_y, EYE_COLOR)
        px(small, 12, mouth_y + 1, EYE_COLOR)
    elif pet.excited:
        # Big open grin.
        px(small, 8, mouth_y, EYE_COLOR)
        px(small, 9, mouth_y + 1, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
        px(small, 11, mouth_y + 1, EYE_COLOR)
        px(small, 12, mouth_y, EYE_COLOR)
    elif pet.bored:
        # Flat, unimpressed line.
        px(small, 9, mouth_y + 1, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
        px(small, 11, mouth_y + 1, EYE_COLOR)
    elif pet.loved:
        # Upturned smile.
        px(small, 8, mouth_y, EYE_COLOR)
        px(small, 9, mouth_y + 1, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
        px(small, 11, mouth_y, EYE_COLOR)
    elif pet.state == State.RUN:
        rect(small, 9, mouth_y, 2, 1, EYE_COLOR)
    elif pet.state == State.JUMP:
        px(small, 10, mouth_y, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
    else:
        px(small, 9, mouth_y, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
        px(small, 11, mouth_y, EYE_COLOR)

    if not pet.facing_right:
        small = pygame.transform.flip(small, True, False)

    scaled = pygame.transform.scale(small, (WINDOW_W, WINDOW_H))

    if (getattr(pet, "tumbling", False) or getattr(pet, "righting", False)) and abs(
        getattr(pet, "angle", 0.0)
    ) > 0.5:
        # Spin while thrown. Rotation grows the surface, so re-center it in the
        # fixed-size window (the corners clip slightly during a fast tumble).
        rotated = pygame.transform.rotate(scaled, pet.angle)
        canvas = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        canvas.fill(CLEAR)
        canvas.blit(
            rotated,
            (
                (WINDOW_W - rotated.get_width()) // 2,
                (WINDOW_H - rotated.get_height()) // 2,
            ),
        )
        return canvas

    return scaled
