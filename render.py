"""All pixel drawing: the pet sprite, the speech bubble, and particles.

Everything here is pure rendering — it takes plain data (a `Pet`, a string, a
particle kind) and returns pygame surfaces. The hand-rolled 5x7 bitmap font
keeps the retro look without an SDL_ttf dependency.
"""

import pygame

from config import (
    ANGER_COLOR,
    BABY_MIN_SCALE,
    BALL_BASE_R,
    BALL_COLOR,
    BALL_HIGHLIGHT,
    BALL_SCALE,
    BALL_SHADE,
    BALL_WIN,
    SNACK_APPLE_COLOR,
    SNACK_APPLE_SHADE,
    SNACK_APPLE_HI,
    SNACK_LEAF_COLOR,
    SNACK_STEM_COLOR,
    SNACK_SCALE,
    SNACK_WIN,
    BELLY_COLOR,
    BOOM_COLOR,
    BUBBLE_FILL_COLOR,
    BUBBLE_MAX_TEXT_W,
    BUBBLE_SCALE,
    BUBBLE_TEXT_COLOR,
    BULLET_COLOR,
    CLEAR,
    DUST_COLOR,
    EYE_COLOR,
    EYE_WHITE,
    GHOST_COLOR,
    GUARD_COLOR,
    GUARD_SHADE,
    GUN_COLOR,
    GUN_GRIP_COLOR,
    GUN_SHADE,
    GUN_HI,
    HAMMER_HEAD_COLOR,
    HAMMER_HEAD_SHADE,
    HANDLE_COLOR,
    HANDLE_SHADE,
    HEADPHONE_BAND,
    HEADPHONE_CUP,
    HEART_COLOR,
    HIGHLIGHT,
    HIT_COLOR,
    LAPTOP_BASE,
    LAPTOP_KEY,
    LAPTOP_LID,
    LAPTOP_LID_EDGE,
    LAPTOP_LOGO,
    NOTE_COLOR,
    PARTICLE_SCALE,
    MIC_BOOM,
    MIC_FOAM,
    PET_COLOR,
    PET_SHADE,
    POOF_COLOR,
    POPCORN_BUCKET,
    POPCORN_KERNEL,
    POPCORN_STRIPE,
    QUESTION_COLOR,
    SLASH_COLOR,
    SPARK_COLOR,
    SPRITE_H,
    SPRITE_W,
    STAR_COLOR,
    STEEL_COLOR,
    STEEL_SHADE,
    STEEL_HI,
    SWEAT_COLOR,
    SHOCK_COLOR,
    TRAIL_COLOR,
    FLAME_COLOR,
    ARROW_COLOR,
    MUZZLE_COLOR,
    BOW_WOOD_COLOR,
    BOW_WOOD_SHADE,
    BOW_STRING_COLOR,
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
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": ["#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    "%": ["##  #", "## # ", "  #  ", " #   ", " # ##", "#  ##", "     "],
    "/": ["    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "],
    "+": ["     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "],
    "(": ["   # ", "  #  ", " #   ", " #   ", " #   ", "  #  ", "   # "],
    ")": [" #   ", "  #  ", "   # ", "   # ", "   # ", "  #  ", " #   "],
    "×": ["     ", "#   #", " # # ", "  #  ", " # # ", "#   #", "     "],
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


def draw_name_tag(name):
    """Kleines Namensschild, das beim Hovern ueber einem Pet erscheint: dunkles
    Kaestchen mit hellem Pixel-Text. Wird ueber dem Kopf platziert."""
    scale = 2
    text = render_pixel_text(name, (238, 242, 250, 255))
    tw, th = text.get_width() * scale, text.get_height() * scale
    pad_x, pad_y = 6, 4
    w, h = tw + pad_x * 2, th + pad_y * 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill(CLEAR)
    pygame.draw.rect(surf, (26, 29, 44, 235), (0, 0, w, h))
    pygame.draw.rect(surf, (120, 130, 165, 255), (0, 0, w, h), 1)
    surf.blit(pygame.transform.scale(text, (tw, th)), (pad_x, pad_y))
    return surf


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
SWEAT_PIXELS = [
    " # ",
    " # ",
    "# #",
    "###",
    " # ",
]
NOTE_PIXELS = [
    "   ##",
    "   ##",
    "   # ",
    "   # ",
    "## # ",
    "#### ",
    "###  ",
]
POPCORN_PIXELS = [
    "## ",
    "###",
    " ##",
]
# Combat / removal effect sprites.
# A bigger, curved blade arc so a slash reads clearly as a sweep.
SLASH_PIXELS = [
    "      ##",
    "    ####",
    "  ####  ",
    " ####   ",
    "####    ",
    "###     ",
    "#       ",
]
SPARK_PIXELS = [
    " # ",
    "###",
    " # ",
]
# A chunkier starburst for a punchy impact.
BOOM_PIXELS = [
    "#   #   #",
    " #  #  # ",
    "  # # #  ",
    "   ###   ",
    "###   ###",
    "   ###   ",
    "  # # #  ",
    " #  #  # ",
    "#   #   #",
]
# An expanding shockwave ring (drawn once; particle scale/life sell the growth).
SHOCK_PIXELS = [
    "  #####  ",
    " #     # ",
    "#       #",
    "#       #",
    "#       #",
    " #     # ",
    "  #####  ",
]
HIT_PIXELS = [
    "#   #",
    " # # ",
    "  #  ",
    " # # ",
    "#   #",
]
BULLET_PIXELS = [
    "###",
    "###",
]
# A little arrow pointing right (flipped by the caller when it flies left).
ARROW_PIXELS = [
    "     # ",
    "#######",
    "#######",
    "     # ",
]
# A short bright motion streak.
TRAIL_PIXELS = [
    "#####",
    " ### ",
]
# A teardrop jetpack flame.
FLAME_PIXELS = [
    " # ",
    "###",
    "###",
    " # ",
]
# A short muzzle / bowstring flash.
MUZZLE_PIXELS = [
    "  #  ",
    "# # #",
    " ### ",
    "#####",
    " ### ",
    "# # #",
    "  #  ",
]
GHOST_PIXELS = [
    " ### ",
    "#####",
    "## ##",
    "#####",
    "#####",
    "# # #",
]
POOF_PIXELS = [
    " ## ",
    "####",
    "####",
    " ## ",
]
PARTICLE_PIXELS = {
    "heart": (HEART_PIXELS, HEART_COLOR),
    "star": (STAR_PIXELS, STAR_COLOR),
    "anger": (STAR_PIXELS, ANGER_COLOR),
    "zzz": (ZZZ_PIXELS, ZZZ_COLOR),
    "dust": (DUST_PIXELS, DUST_COLOR),
    "sweat": (SWEAT_PIXELS, SWEAT_COLOR),
    "question": (FONT_5x7["?"], QUESTION_COLOR),
    "note": (NOTE_PIXELS, NOTE_COLOR),
    "popcorn": (POPCORN_PIXELS, POPCORN_KERNEL),
    "slash": (SLASH_PIXELS, SLASH_COLOR),
    "spark": (SPARK_PIXELS, SPARK_COLOR),
    "boom": (BOOM_PIXELS, BOOM_COLOR),
    "shock": (SHOCK_PIXELS, SHOCK_COLOR),
    "trail": (TRAIL_PIXELS, TRAIL_COLOR),
    "flame": (FLAME_PIXELS, FLAME_COLOR),
    "arrow": (ARROW_PIXELS, ARROW_COLOR),
    "muzzle": (MUZZLE_PIXELS, MUZZLE_COLOR),
    "hit": (HIT_PIXELS, HIT_COLOR),
    "bullet": (BULLET_PIXELS, BULLET_COLOR),
    "ghost": (GHOST_PIXELS, GHOST_COLOR),
    "poof": (POOF_PIXELS, POOF_COLOR),
}
_PARTICLE_CACHE = {}


def particle_sprite(kind):
    sprite = _PARTICLE_CACHE.get(kind)
    if sprite is None:
        pattern, color = PARTICLE_PIXELS[kind]
        h = len(pattern)
        w = max(len(row) for row in pattern)
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
# pet's facing). Each row can be any length — the builder pads to the widest.
# Legend shared across weapons:
#   #=steel  s=steel shade  h=steel highlight  ==wood  w=wood shade
#   |=guard  g=guard shade  o=gun body  k=gun shade  l=gun highlight
#   b=bow wood  d=bow wood shade  t=bowstring
# Dagger: short leaf blade, brass crossguard, wooden grip with a pommel.
KNIFE_PIXELS = [
    "         h    ",
    "       hh#s   ",
    "  gw|########s",
    "  ==|#########",
    "  gw|#######ss",
    "       sss#   ",
    "         s    ",
]
# Sword: long fullered blade, wide crossguard, bound grip and round pommel.
SWORD_PIXELS = [
    "        hhhhhhhhhhhhh ",
    "   g|hhhhhhhhhhhhhhhhh",
    " w==|################",
    " w==|###############h",
    " w==|################",
    "   g|sssssssssssssssss",
    "        sssssssssssss ",
]
# Spear: long wooden shaft with a grip wrap and a steel leaf head, tip right.
SPEAR_PIXELS = [
    "                    h    ",
    "===w=====w========hhh#   ",
    "===========w======#####s ",
    "==w=====w=========######h",
    "===========w======#####s ",
    "==================sss#   ",
    "                    s    ",
]
# Hammer: stubby wrapped haft with a heavy blocky steel head, face on the right.
HAMMER_PIXELS = [
    "         hhhhhh",
    "         h####s",
    "         h####s",
    "  ==w=====#####",
    "  ==w=====#####",
    "         s####s",
    "         ss###s",
    "         ssssss",
]
# Pistol: slide, frame and wooden grip, muzzle pointing right.
PISTOL_PIXELS = [
    "   llllllll  ",
    "  loooooooool",
    " kooooooooook",
    "==koooookkkkk",
    "===ooookk    ",
    " ===okk      ",
    "  ===k       ",
]
# Bow: a curved wooden limb strung taut, an arrow nocked pointing right.
BOW_PIXELS = [
    " td       b ",
    " t d     bd ",
    " t  d   bd  ",
    " t   b#####h",
    " t  d   bd  ",
    " t d     bd ",
    " td       b ",
]
WEAPON_PIXELS = {
    "knife": (KNIFE_PIXELS, {
        "#": STEEL_COLOR, "s": STEEL_SHADE, "h": STEEL_HI,
        "=": HANDLE_COLOR, "w": HANDLE_SHADE,
        "|": GUARD_COLOR, "g": GUARD_SHADE,
    }),
    "sword": (SWORD_PIXELS, {
        "#": STEEL_COLOR, "s": STEEL_SHADE, "h": STEEL_HI,
        "=": HANDLE_COLOR, "w": HANDLE_SHADE,
        "|": GUARD_COLOR, "g": GUARD_SHADE,
    }),
    "spear": (SPEAR_PIXELS, {
        "#": STEEL_COLOR, "s": STEEL_SHADE, "h": STEEL_HI,
        "=": HANDLE_COLOR, "w": HANDLE_SHADE,
    }),
    "hammer": (HAMMER_PIXELS, {
        "#": HAMMER_HEAD_COLOR, "s": HAMMER_HEAD_SHADE, "h": STEEL_HI,
        "=": HANDLE_COLOR, "w": HANDLE_SHADE,
    }),
    "pistol": (PISTOL_PIXELS, {
        "o": GUN_COLOR, "k": GUN_SHADE, "l": GUN_HI,
        "=": GUN_GRIP_COLOR,
    }),
    "bow": (BOW_PIXELS, {
        "b": BOW_WOOD_COLOR, "d": BOW_WOOD_SHADE, "t": BOW_STRING_COLOR,
        "#": ARROW_COLOR, "h": STEEL_HI,
    }),
}
_WEAPON_CACHE = {}


def draw_weapon(kind):
    """Return a scaled weapon sprite, pointing right, cached per kind."""
    sprite = _WEAPON_CACHE.get(kind)
    if sprite is None:
        pattern, colors = WEAPON_PIXELS[kind]
        h = len(pattern)
        w = max(len(row) for row in pattern)
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


def weapon_pose(pet):
    """Pose the pet's weapon for this frame, animating the swing.

    Returns ``(surface, dx, dy)`` where ``dx``/``dy`` are offsets from the pet
    sprite's top-left corner (the caller adds the on-screen pet position). The
    pose is driven by ``pet.combat_phase`` (windup -> strike -> recovery) and the
    progress through it, so blades rear back and swing through while a pistol
    holds a steady aim and recoils on the shot.
    """
    kind = pet.weapon
    base = draw_weapon(kind)
    ranged = kind in ("pistol", "bow")
    sign = 1 if pet.facing_right else -1

    phase = getattr(pet, "combat_phase", None)
    pmax = max(1, getattr(pet, "phase_max", 1))
    prog = 1.0 - max(0, getattr(pet, "phase_timer", 0)) / pmax  # 0 -> 1 across phase

    angle = -8.0   # relaxed ready pose, tip slightly down
    reach = 0.0    # extra px forward from the hand
    lift = 0.0     # px raised
    if ranged:
        if phase == "windup":
            angle, reach = 0.0, 2.0          # level off and take aim
        elif phase == "strike":
            angle, reach = 6.0, -5.0 + 5.0 * prog  # muzzle flips up, recoils back
        elif phase == "recovery":
            angle = 6.0 * (1.0 - prog)
    else:
        if phase == "windup":
            angle = -8.0 + 88.0 * prog       # rear up overhead
            lift = 6.0 * prog
        elif phase == "strike":
            angle = 80.0 - 150.0 * prog      # whip down and through
            reach = 10.0 * prog
            lift = 6.0 * (1.0 - prog)
        elif phase == "recovery":
            angle = -70.0 + 62.0 * prog      # ease back to ready

    img = base
    if not pet.facing_right:
        img = pygame.transform.flip(img, True, False)
        angle = -angle
    if abs(angle) > 0.5:
        img = pygame.transform.rotate(img, angle)

    hand_x = WINDOW_W * 0.5 + sign * (WINDOW_W * 0.30 + reach)
    hand_y = WINDOW_H * 0.45 - lift
    dx = hand_x - img.get_width() / 2
    dy = hand_y - img.get_height() / 2
    return img, dx, dy


# Jetpack strapped to the pet's back while flying: a little tank with two nozzles.
JETPACK_PIXELS = [
    " kk ",
    "koodk",
    "koodk",
    "koodk",
    "koodk",
    " kk ",
    "k  k",
]
_JETPACK_SPRITE = None


def draw_flight_rig(pet):
    """Return ``(surface, dx, dy)`` for the jetpack worn while flying, offset from
    the pet sprite's top-left. Sits on the pet's back (opposite his facing) and
    bobs a touch with the frame so it reads as thrusting."""
    global _JETPACK_SPRITE
    if _JETPACK_SPRITE is None:
        colors = {"o": GUN_COLOR, "k": GUN_SHADE, "d": GUN_HI}
        h = len(JETPACK_PIXELS)
        w = max(len(row) for row in JETPACK_PIXELS)
        base = pygame.Surface((w, h), pygame.SRCALPHA)
        base.fill(CLEAR)
        for y, row in enumerate(JETPACK_PIXELS):
            for x, cell in enumerate(row):
                color = colors.get(cell)
                if color is not None:
                    base.set_at((x, y), color)
        _JETPACK_SPRITE = pygame.transform.scale(
            base, (w * WEAPON_SCALE, h * WEAPON_SCALE)
        )
    img = _JETPACK_SPRITE
    # Behind the pet: to his left when facing right, and vice versa.
    back = -1 if pet.facing_right else 1
    bob = 1.0 if (pet.frame // 4) % 2 else -1.0
    x = WINDOW_W * 0.5 + back * WINDOW_W * 0.34
    y = WINDOW_H * 0.42 + bob
    dx = x - img.get_width() / 2
    dy = y - img.get_height() / 2
    return img, dx, dy


_BALL_SPRITE = None


def draw_ball():
    """The fetch ball, centred in a BALL_WIN-sized transparent canvas."""
    global _BALL_SPRITE
    if _BALL_SPRITE is None:
        d = BALL_BASE_R * 2 + 1
        c = BALL_BASE_R
        base = pygame.Surface((d, d), pygame.SRCALPHA)
        base.fill(CLEAR)
        pygame.draw.circle(base, BALL_COLOR, (c, c), BALL_BASE_R)
        base.set_at((c + 1, c + 1), BALL_SHADE)
        base.set_at((c + 2, c + 1), BALL_SHADE)
        base.set_at((c + 1, c + 2), BALL_SHADE)
        base.set_at((c - 1, c - 1), BALL_HIGHLIGHT)
        _BALL_SPRITE = pygame.transform.scale(base, (d * BALL_SCALE, d * BALL_SCALE))
    canvas = pygame.Surface((BALL_WIN, BALL_WIN), pygame.SRCALPHA)
    canvas.fill(CLEAR)
    sprite = _BALL_SPRITE
    canvas.blit(
        sprite,
        ((BALL_WIN - sprite.get_width()) // 2, (BALL_WIN - sprite.get_height()) // 2),
    )
    return canvas


# Snack-Apfel: Legende a=Apfel s=Schatten h=Glanz l=Blatt t=Stiel.
_SNACK_PIXELS = [
    "  t l   ",
    "  tll   ",
    " aaaa   ",
    "haaaaas ",
    "haaaaaas",
    "haaaaaas",
    " aaaaas ",
    "  aaas  ",
]
_SNACK_LEGEND = {
    "a": SNACK_APPLE_COLOR,
    "s": SNACK_APPLE_SHADE,
    "h": SNACK_APPLE_HI,
    "l": SNACK_LEAF_COLOR,
    "t": SNACK_STEM_COLOR,
}
_SNACK_SPRITE = None


def draw_snack():
    """Der Snack (Apfel), zentriert in einem SNACK_WIN-grossen, transparenten
    Fenster. Statisch — er liegt einfach da, bis ein Pet ihn frisst."""
    global _SNACK_SPRITE
    if _SNACK_SPRITE is None:
        h = len(_SNACK_PIXELS)
        w = max(len(row) for row in _SNACK_PIXELS)
        base = pygame.Surface((w, h), pygame.SRCALPHA)
        base.fill(CLEAR)
        for y, row in enumerate(_SNACK_PIXELS):
            for x, cell in enumerate(row):
                color = _SNACK_LEGEND.get(cell)
                if color is not None:
                    base.set_at((x, y), color)
        _SNACK_SPRITE = pygame.transform.scale(base, (w * SNACK_SCALE, h * SNACK_SCALE))
    canvas = pygame.Surface((SNACK_WIN, SNACK_WIN), pygame.SRCALPHA)
    canvas.fill(CLEAR)
    sprite = _SNACK_SPRITE
    canvas.blit(
        sprite,
        ((SNACK_WIN - sprite.get_width()) // 2, (SNACK_WIN - sprite.get_height()) // 2),
    )
    return canvas


def _draw_headphones(small, body_y):
    """A headphone band over the head with cushioned cups over the ears."""
    for x in range(6, 14):
        px(small, x, body_y - 1, HEADPHONE_BAND)
    px(small, 5, body_y, HEADPHONE_BAND)
    px(small, 14, body_y, HEADPHONE_BAND)
    rect(small, 4, body_y + 1, 2, 4, HEADPHONE_CUP)
    rect(small, 14, body_y + 1, 2, 4, HEADPHONE_CUP)


def _draw_headset(small, body_y):
    """A headset worn on a call: a band with cushioned ear cups plus a mic boom
    curving from the front cup down to a foam tip in front of the mouth."""
    # Band over the head.
    for x in range(6, 14):
        px(small, x, body_y - 1, HEADPHONE_BAND)
    px(small, 5, body_y, HEADPHONE_BAND)
    px(small, 14, body_y, HEADPHONE_BAND)
    # Cushioned ear cups over both ears.
    rect(small, 4, body_y + 1, 2, 4, HEADPHONE_CUP)
    rect(small, 14, body_y + 1, 2, 4, HEADPHONE_CUP)
    # Mic boom arm curving from the front (right) cup toward the mouth.
    px(small, 16, body_y + 4, MIC_BOOM)
    px(small, 16, body_y + 5, MIC_BOOM)
    px(small, 15, body_y + 6, MIC_BOOM)
    px(small, 14, body_y + 7, MIC_BOOM)
    # Foam mic tip in front of the mouth.
    rect(small, 12, body_y + 7, 2, 2, MIC_FOAM)


def _draw_popcorn(small, body_y):
    """A red-and-white striped popcorn tub held at the belly, popped on top."""
    top = body_y + 7
    for x in (7, 9, 11):
        px(small, x, top - 1, POPCORN_KERNEL)
    rect(small, 7, top, 6, 1, POPCORN_STRIPE)
    for i, x in enumerate(range(7, 13)):
        color = POPCORN_BUCKET if i % 2 == 0 else POPCORN_STRIPE
        rect(small, x, top + 1, 1, 4, color)


def _draw_laptop(small, body_y, frame):
    """An open laptop held at the torso (screen back toward us), with two keys
    alternately 'pressing' to suggest typing."""
    lid_top = body_y + 5
    rect(small, 6, lid_top, 8, 3, LAPTOP_LID)
    rect(small, 6, lid_top, 8, 1, LAPTOP_LID_EDGE)
    px(small, 9, lid_top + 1, LAPTOP_LOGO)
    px(small, 10, lid_top + 1, LAPTOP_LOGO)
    base_y = lid_top + 3
    rect(small, 5, base_y, 10, 1, LAPTOP_BASE)
    rect(small, 5, base_y + 1, 10, 1, LAPTOP_LID)
    px(small, 8 if (frame // 6) % 2 else 11, base_y, LAPTOP_KEY)


def pet_cache_key(pet):
    """Alle Felder, die das gezeichnete Sprite bestimmen, als Tupel gebündelt.

    Gleicher Key = pixelidentisches Bild, also darf die zwischengespeicherte
    Surface wiederverwendet und in main.py der CGImage-Push übersprungen werden.
    Frame-abhängige Animations-Buckets kommen nur rein, wo sie das aktuelle Bild
    wirklich verändern — so behält ein ruhender/schlafender Pet einen stabilen
    Key und verursacht kein Redraw pro Frame."""
    state = pet.state
    # Lauf-/Bein-Takt: nur beim Gehen/Rennen bewegt sich etwas.
    if state in (State.WALK, State.RUN):
        step_speed = 7 if state == State.WALK else 4
        step_bucket = (pet.frame // step_speed) % 2
    else:
        step_bucket = 0
    # Arm-Schwung gilt in allen Zuständen ausser IDLE (dort fix bei 0).
    arm_bucket = (pet.frame // 7) % 2 if state != State.IDLE else 0

    calm = not (
        pet.asleep
        or pet.angry
        or pet.rage
        or pet.scared
        or pet.tumbling
        or pet.righting
    )
    activity = pet.activity if calm else None
    music = pet.music if calm else False
    # Der Laptop-Prop "tippt" im 6er-Takt — nur dann zählt der Frame dafür.
    type_bucket = (pet.frame // 6) % 2 if (calm and activity == "work") else 0

    # look_offset/blink bewegen nur die "normalen"/Blinzel-/Love-Augen; in den
    # fixierten Mood-Augen (Schlaf, Angst, aufgeregt, neugierig, gelangweilt)
    # ignoriert die Zeichnung sie — dort ausmaskieren, damit z.B. ein Schläfer
    # trotz tickendem Blinzel-Timer einen stabilen Key behält.
    eyes_fixed = (
        pet.asleep
        or (pet.scared and not pet.angry)
        or pet.excited
        or (pet.curious and not pet.angry)
        or pet.bored
    )
    look = 0 if eyes_fixed else max(-1, min(1, pet.look_offset))
    blink_shows = pet.blink and not (
        eyes_fixed or pet.loved or pet.victory
    )

    spinning = (
        pet.tumbling
        or pet.righting
        or (pet.dying and pet.death_kind == "fall")
    )
    # Rotationswinkel nur in groben Stufen (feiner braucht das Auge nicht) und
    # nur wenn er sich wirklich dreht.
    angle_bucket = round(pet.angle / 4.0) if spinning else 0

    # Death-Fade in groben Alpha-Stufen statt jedem einzelnen Timer-Wert.
    if pet.dying:
        dmax = max(1, pet.death_max)
        death_stage = int(255 * pet.death_timer / dmax) >> 3
    else:
        death_stage = -1

    # Baby-Skala in Stufen (die Sprite-Grösse ändert sich nur grob sichtbar).
    growth_bucket = round(min(1.0, max(0.0, pet.growth)) * 40)

    return (
        state,
        step_bucket,
        arm_bucket,
        type_bucket,
        pet.facing_right,
        pet.palette_index,
        pet.asleep,
        pet.angry,
        pet.rage,
        pet.scared,
        pet.loved,
        pet.victory,
        pet.excited,
        pet.curious,
        pet.bored,
        blink_shows,
        look,
        activity,
        music,
        growth_bucket,
        angle_bucket,
        death_stage,
    )


def draw_pet_frame(pet):
    # Frame-Cache: hat sich am Aussehen nichts geändert, die zuletzt gezeichnete
    # Surface direkt zurückgeben statt sie neu aufzubauen (set_at/scale/rotate).
    key = pet_cache_key(pet)
    cached = getattr(pet, "_frame_cache", None)
    if cached is not None and getattr(pet, "_frame_cache_key", None) == key:
        return cached

    small = pygame.Surface((SPRITE_W, SPRITE_H), pygame.SRCALPHA)
    small.fill(CLEAR)

    # Per-pet palette (personality recolour), falling back to the defaults.
    palette = getattr(pet, "palette", None) or {}
    body = palette.get("color", PET_COLOR)
    shade = palette.get("shade", PET_SHADE)
    belly = palette.get("belly", BELLY_COLOR)
    hi = palette.get("highlight", HIGHLIGHT)

    bob = 0
    if pet.state in (State.WALK, State.RUN):
        step_speed = 7 if pet.state == State.WALK else 4
        bob = 1 if (pet.frame // step_speed) % 2 else 0
    if pet.state == State.JUMP:
        bob = -1

    body_y = 4 + bob
    rect(small, 5, body_y + 1, 10, 8, body)
    rect(small, 4, body_y + 3, 12, 5, body)
    rect(small, 7, body_y + 6, 6, 4, belly)
    rect(small, 6, body_y + 1, 2, 1, hi)
    rect(small, 13, body_y + 4, 2, 4, shade)

    # Ears
    px(small, 5, body_y, body)
    px(small, 6, body_y - 1, body)
    px(small, 14, body_y, body)
    px(small, 13, body_y - 1, body)

    # Arms
    arm_swing = 1 if (pet.frame // 7) % 2 else 0
    if pet.state == State.IDLE:
        arm_swing = 0
    rect(small, 3, body_y + 6 - arm_swing, 2, 2, body)
    rect(small, 15, body_y + 5 + arm_swing, 2, 2, body)

    # Legs
    phase = (pet.frame // (7 if pet.state == State.WALK else 4)) % 2
    leg_lift = pet.state in (State.WALK, State.RUN)
    for i, leg_x in enumerate([6, 9, 12, 14]):
        lifted = leg_lift and (i % 2 == phase)
        leg_h = 1 if lifted else 3
        rect(small, leg_x, body_y + 9, 1, leg_h, shade)

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
    elif pet.scared and not pet.angry:
        # Wide, frightened eyes: big whites with tiny darting pupils.
        for cx in (7, 12):
            rect(small, cx - 1, eye_y - 1, 3, 3, EYE_WHITE)
            px(small, cx, eye_y, EYE_COLOR)
    elif (pet.loved or getattr(pet, "victory", False)) and not pet.angry:
        # Smitten / triumphant: happy upward-arc eyes and rosy cheeks.
        for ex in (left_eye_x, right_eye_x):
            px(small, ex - 1, eye_y + 1, EYE_COLOR)
            px(small, ex, eye_y, EYE_COLOR)
            px(small, ex + 1, eye_y + 1, EYE_COLOR)
        px(small, left_eye_x - 1, eye_y + 2, BLUSH_COLOR)
        px(small, right_eye_x + 1, eye_y + 2, BLUSH_COLOR)
    elif pet.excited:
        # Wide-awake excited eyes: tall and dark with a bright catchlight. The
        # grin sells the excitement, so the eyes stay mostly dark.
        for sx in (7, 11):
            rect(small, sx, eye_y - 1, 2, 3, EYE_COLOR)
            px(small, sx, eye_y - 1, EYE_WHITE)
    elif pet.curious and not pet.angry:
        # Alert, attentive eyes; glint on the inner side (the '?' tells the rest).
        for sx in (7, 11):
            rect(small, sx, eye_y, 2, 2, EYE_COLOR)
            px(small, sx + 1, eye_y, EYE_WHITE)
    elif pet.bored:
        # Heavy-lidded, sleepy eyes: a brown lid droops over the top of a small
        # dark eye, so he looks tired instead of having a hard black monoline.
        for sx in (7, 11):
            rect(small, sx, eye_y, 2, 2, EYE_COLOR)
            rect(small, sx, eye_y, 2, 1, shade)
            px(small, sx, eye_y + 1, EYE_WHITE)
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
    elif pet.scared:
        # Nervous, wavy mouth.
        px(small, 8, mouth_y + 1, EYE_COLOR)
        px(small, 9, mouth_y, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
        px(small, 11, mouth_y, EYE_COLOR)
        px(small, 12, mouth_y + 1, EYE_COLOR)
    elif pet.curious:
        # Small, intrigued "o".
        px(small, 10, mouth_y, EYE_COLOR)
        px(small, 10, mouth_y + 1, EYE_COLOR)
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
    elif pet.loved or getattr(pet, "victory", False):
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

    # App-aware props: drawn over the body, hidden in moods where they'd look
    # wrong (asleep, upset, mid-throw). The props are symmetric, so they survive
    # the facing flip below cleanly.
    calm = not (
        pet.asleep
        or pet.angry
        or pet.rage
        or pet.scared
        or getattr(pet, "tumbling", False)
        or getattr(pet, "righting", False)
    )
    if calm:
        activity = getattr(pet, "activity", None)
        if activity == "call":
            _draw_headset(small, body_y)
        elif activity == "work":
            _draw_laptop(small, body_y, pet.frame)
        elif activity == "video":
            _draw_popcorn(small, body_y)
        if getattr(pet, "music", False):
            _draw_headphones(small, body_y)

    if not pet.facing_right:
        small = pygame.transform.flip(small, True, False)

    scaled = pygame.transform.scale(small, (WINDOW_W, WINDOW_H))

    # Babies start tiny and grow up. Shrink the sprite but keep the feet planted
    # on the window's bottom edge so the little one still stands on the ground.
    growth = getattr(pet, "growth", 1.0)
    if growth < 1.0:
        s = BABY_MIN_SCALE + (1.0 - BABY_MIN_SCALE) * max(0.0, min(1.0, growth))
        sw = max(1, int(WINDOW_W * s))
        sh = max(1, int(WINDOW_H * s))
        small_scaled = pygame.transform.scale(scaled, (sw, sh))
        scaled = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        scaled.fill(CLEAR)
        scaled.blit(small_scaled, ((WINDOW_W - sw) // 2, WINDOW_H - sh))

    # A thrown tumble, or a dramatic "fall" death, spins the sprite.
    angle = getattr(pet, "angle", 0.0)
    spinning = (
        getattr(pet, "tumbling", False)
        or getattr(pet, "righting", False)
        or (getattr(pet, "dying", False) and getattr(pet, "death_kind", "") == "fall")
    )
    if spinning and abs(angle) > 0.5:
        # Rotation grows the surface, so re-center it in the fixed-size window
        # (the corners clip slightly during a fast tumble).
        rotated = pygame.transform.rotate(scaled, angle)
        canvas = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        canvas.fill(CLEAR)
        canvas.blit(
            rotated,
            (
                (WINDOW_W - rotated.get_width()) // 2,
                (WINDOW_H - rotated.get_height()) // 2,
            ),
        )
        scaled = canvas

    # Fade out over the removal animation (works for any death style).
    if getattr(pet, "dying", False):
        dmax = max(1, getattr(pet, "death_max", 1))
        alpha = max(0, min(255, int(255 * getattr(pet, "death_timer", 0) / dmax)))
        scaled.fill((255, 255, 255, alpha), None, pygame.BLEND_RGBA_MULT)

    pet._frame_cache_key = key
    pet._frame_cache = scaled
    return scaled
