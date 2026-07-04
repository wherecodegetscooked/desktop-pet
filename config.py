"""Tunable constants and shared configuration for the desktop pet.

Grouped by concern: display/sprite, colours, macOS/AppKit enums, physics and
behaviour tuning, speech, effects, mouse interaction, and anger. Tweak the
values here to change how the pet looks and behaves.
"""

FPS = 60
SCALE = 3
SPRITE_W = 20
SPRITE_H = 18
WINDOW_W = SPRITE_W * SCALE
WINDOW_H = SPRITE_H * SCALE

PET_COLOR = (236, 145, 92, 255)
PET_SHADE = (195, 92, 72, 255)
BELLY_COLOR = (255, 198, 139, 255)
EYE_COLOR = (26, 20, 18, 255)
EYE_WHITE = (245, 246, 248, 255)
HIGHLIGHT = (255, 221, 176, 255)
CLEAR = (0, 0, 0, 0)

NS_BACKING_STORE_BUFFERED = 2
NS_WINDOW_STYLE_BORDERLESS = 0
NS_WINDOW_STYLE_NONACTIVATING_PANEL = 1 << 7
NS_WINDOW_COLLECTION_CAN_JOIN_ALL_SPACES = 1 << 0
NS_WINDOW_COLLECTION_IGNORES_CYCLE = 1 << 6
NS_WINDOW_COLLECTION_FULLSCREEN_AUXILIARY = 1 << 8
NS_APPLICATION_ACTIVATION_POLICY_ACCESSORY = 1
NS_STATUS_ITEM_VARIABLE_LENGTH = -1.0
CG_WINDOW_LEVEL_ASSISTIVE_TECH_HIGH = 20
# CGEventSource input-activity queries (used for AFK sleep and typing energy).
# These read HID idle time / keydown counts without needing accessibility perms.
CG_EVENT_SOURCE_STATE_HID = 1
CG_ANY_INPUT_EVENT_TYPE = 0xFFFFFFFF
CG_EVENT_KEY_DOWN = 10
WINDOW_LIST_ON_SCREEN_ONLY = 1
WINDOW_LIST_EXCLUDE_DESKTOP = 16
GROUND_PLATFORM_NAME = "Desktop"
GRAVITY = 0.42
NSEVENT_LEFT_MOUSE_DOWN = 1
NSEVENT_LEFT_MOUSE_UP = 2
NSEVENT_LEFT_MOUSE_DRAGGED = 6
MENU_ICON_SIZE = 18.0
CLICK_MOVE_THRESHOLD = 5             # Px of motion that turns a click into a drag.

# Jump tuning ---------------------------------------------------------------
# Increase these to make the pet jump more often or jump higher.
RANDOM_JUMP_STATE_CHANCE = 0.03      # Chance that a new random state is JUMP.
WINDOW_JUMP_CHANCE = 0.002           # Per-frame chance to jump to another window.
PLATFORM_DROP_CHANCE = 0.002        # Per-frame chance to drop through current ledge.
NORMAL_JUMP_POWER_MIN = 5.5          # Smaller hop when jumping without a target.
NORMAL_JUMP_POWER_MAX = 6.0
TARGET_JUMP_POWER_MIN = 8.0          # Minimum power for window-to-window jumps.
MAX_TARGET_JUMP_POWER = 38.0         # Raise this to reach very high windows.
TARGET_JUMP_EXTRA_HEIGHT = 72        # Extra arc height above the destination edge.
MAX_TARGET_JUMP_SPEED_X = 6.0        # Horizontal speed cap for long jumps.
MAX_TARGET_DISTANCE = 0.3           # Fraction of screen width considered reachable.
MAX_TARGET_HEIGHT = 1.5              # Fraction of screen height considered reachable.
MIN_PLATFORM_Y = 0                   # Allows high ledges where pet stands off-screen.
# How close (px) the pet's centre may get to a window edge while just pacing on
# it. He turns around here instead of teetering off, which stops him jittering
# or getting stuck in window corners. Deliberate exits (drop-through, window
# jumps) ignore this.
PLATFORM_EDGE_MARGIN = 8

# Speech tuning -------------------------------------------------------------
SPEAK_CHANCE = 0.012                  # Per-frame chance to start talking (off cooldown).
SPEAK_COOLDOWN_MIN = 360              # Min frames of silence between lines (~6s).
SPEAK_COOLDOWN_MAX = 1200             # Max frames of silence between lines (~20s).
SPEECH_MIN_FRAMES = 150              # Shortest time a bubble stays up (~2.5s).
SPEECH_PER_CHAR = 6                  # Extra frames shown per character of text.

# Pixel speech bubble dimensions.
BUBBLE_SCALE = 3                     # Nearest-neighbour upscale for the pixel look.
BUBBLE_MAX_TEXT_W = 96               # Wrap width in base (pre-scale) pixels.
BUBBLE_TEXT_COLOR = (40, 30, 28, 255)
BUBBLE_FILL_COLOR = (255, 250, 235, 255)
BUBBLE_GAP = 8                       # Pixels between the bubble tail tip and the pet.

# Effects overlay (speech bubble + particles) ------------------------------
# A transparent, click-through window centred on the pet. Big enough to hold a
# bubble either above or below the pet plus floating particles.
FX_W = 420
FX_H = 440
PARTICLE_SCALE = 3
MAX_PARTICLES = 60
HEART_COLOR = (255, 95, 130, 255)
STAR_COLOR = (255, 214, 92, 255)
ANGER_COLOR = (232, 64, 52, 255)
ZZZ_COLOR = (150, 170, 210, 255)
DUST_COLOR = (205, 198, 186, 255)
SWEAT_COLOR = (120, 195, 235, 255)
QUESTION_COLOR = (255, 236, 150, 255)
NOTE_COLOR = (176, 150, 240, 255)
# Combat / removal effect colours.
SLASH_COLOR = (245, 248, 255, 255)   # White blade streak.
SPARK_COLOR = (255, 240, 170, 255)   # Bright little sparks.
BOOM_COLOR = (255, 176, 76, 255)     # Orange impact burst.
HIT_COLOR = (255, 92, 80, 255)       # Red hit-marker cross.
BULLET_COLOR = (250, 222, 120, 255)  # Pistol projectile.
GHOST_COLOR = (214, 224, 244, 255)   # Floating ghost on a ghostly death.
POOF_COLOR = (236, 238, 244, 255)    # Puff cloud on a poof death.
SHOCK_COLOR = (255, 236, 200, 255)   # Expanding shockwave ring (hammer/impact).
TRAIL_COLOR = (198, 214, 255, 255)   # Dash / motion streak behind a lunge.
FLAME_COLOR = (255, 168, 72, 255)    # Jetpack exhaust flame.
ARROW_COLOR = (210, 176, 120, 255)   # Bow projectile shaft.
MUZZLE_COLOR = (255, 246, 196, 255)  # Muzzle / bowstring flash.

# Combat effect strength — how much visual punch each hit throws. Bumped up so
# attacks read clearly; still small sprites so the overlay stays cheap.
FX_SPARK_COUNT = 7                   # Sparks flung on a clean melee hit.
FX_SMASH_SPARK_COUNT = 12            # Extra sparks on a heavy hammer smash.
FX_DUST_COUNT = 4                    # Dust puffs kicked up on an impact.
FX_TRAIL_COUNT = 5                   # Motion streaks left by a dash/lunge.

# App-aware activity props --------------------------------------------------
# The pet reacts to what you're doing: it works on a laptop during a focus
# session or in an editor, munches popcorn while a video plays, and wears
# headphones (with floating notes) whenever music is running.
NOTE_INTERVAL_MIN = 26               # Frames between floating music notes.
NOTE_INTERVAL_MAX = 60
LAPTOP_LID = (70, 74, 84, 255)
LAPTOP_LID_EDGE = (120, 126, 140, 255)
LAPTOP_BASE = (152, 158, 170, 255)
LAPTOP_KEY = (44, 48, 56, 255)
LAPTOP_LOGO = (150, 210, 255, 255)
POPCORN_BUCKET = (214, 72, 66, 255)
POPCORN_STRIPE = (246, 246, 246, 255)
POPCORN_KERNEL = (250, 226, 130, 255)
HEADPHONE_BAND = (52, 56, 68, 255)
HEADPHONE_CUP = (74, 80, 96, 255)
MIC_BOOM = (52, 56, 68, 255)            # Headset mic boom arm (worn on a call).
MIC_FOAM = (236, 92, 88, 255)           # Mic foam tip (a warm "live" accent).

# Mouse interaction --------------------------------------------------------
FOLLOW_CHANCE = 0.004                # Per-frame chance to start chasing the cursor.
FOLLOW_STOP_DISTANCE = 12            # Stop once this close (px) to the cursor.
FOLLOW_RUN_DISTANCE = 220            # Run instead of walk when farther than this.
IDLE_FX_MIN = 360                    # Min frames between spontaneous heart/stars.
IDLE_FX_MAX = 1080

# Anger ---------------------------------------------------------------------
ANGRY_THRESHOLD = 3                  # Clicks (before cooling down) that anger the pet.
ANGRY_DURATION = 420                 # Frames the pet stays grumpy (~7s).
ANGER_DECAY = 0.010                  # Anger cooled per frame (slower = stays cross longer).

# Rage / combat -------------------------------------------------------------
# Once enraged he commits to the fight. He will NOT calm down on a timer alone:
# he has to actually land RAGE_HITS_TO_CALM clean blows (or capture the cursor),
# and even then only after RAGE_MIN_DURATION has passed. A hard RAGE_MAX_DURATION
# ceiling stops a fight lasting forever if the cursor is parked out of reach.
RAGE_THRESHOLD = 6                   # Total anger that tips him into violence.
RAGE_DURATION = 900                  # Base frames he stays violent (~15s).
RAGE_MIN_DURATION = 480              # He can't calm before this many frames (~8s).
RAGE_MAX_DURATION = 2400             # Hard ceiling so a fight can't run forever (~40s).
RAGE_HITS_TO_CALM = 3               # Clean hits he must land before he'll calm down.
RAGE_CHASE_SPEED = 3.4               # How fast he charges the cursor when armed.
WEAPONS = ["knife", "sword", "spear", "hammer", "bow", "pistol"]
# Weapons that shoot rather than swing — the combat brain reaches for one of
# these when the cursor is floating somewhere it cannot get to on foot.
RANGED_WEAPONS = ["bow", "pistol"]
MELEE_WEAPONS = ["knife", "sword", "spear", "hammer"]

# Per-weapon combat profile. Each weapon feels distinct: the range it strikes
# from, the windup -> strike -> recovery timing (frames), the cooldown between
# swings, how far it lunges in, how hard it knocks the cursor back, the effect
# drawn on a hit, and how many clean hits it takes to corner and capture the
# cursor. Keep this table the single source of truth so new weapons only need a
# row here plus pixel art in render.py.
#   range      : distance (px, pet centre -> cursor) at which he'll swing.
#   approach   : horizontal gap he tries to close before swinging.
#   windup     : frames of telegraph before the blow lands.
#   strike     : frames the hit is "live" (slash/impact visible).
#   recovery   : frames he's committed after the blow before acting again.
#   cooldown   : extra frames after recovery before the next swing.
#   lunge      : px he dashes forward on the strike (0 = stand and poke/shoot).
#   knockback  : px the cursor is shoved away on a hit.
#   hits_to_win: clean hits needed before the capture finale triggers.
#   ranged     : True fires a projectile instead of a melee swing.
#   effect     : which hit effect render/pet draw ("slash"/"stab"/"smash"/"shot").
WEAPON_STATS = {
    "knife": {  # dagger: lightning-fast pokes, close range, light taps.
        "range": 54, "approach": 40, "windup": 5, "strike": 3, "recovery": 7,
        "cooldown": 10, "lunge": 8, "knockback": 9, "hits_to_win": 5,
        "ranged": False, "effect": "slash",
    },
    "sword": {  # a quick dash-in and a wide slash, medium range.
        "range": 82, "approach": 72, "windup": 9, "strike": 5, "recovery": 15,
        "cooldown": 26, "lunge": 40, "knockback": 28, "hits_to_win": 3,
        "ranged": False, "effect": "slash",
    },
    "spear": {  # reach weapon: jabs from farther out with a short lunge.
        "range": 120, "approach": 106, "windup": 11, "strike": 5, "recovery": 16,
        "cooldown": 30, "lunge": 24, "knockback": 22, "hits_to_win": 3,
        "ranged": False, "effect": "stab",
    },
    "hammer": {  # slow, heavy overhead swing with a big impact and knockback.
        "range": 68, "approach": 56, "windup": 22, "strike": 6, "recovery": 26,
        "cooldown": 44, "lunge": 12, "knockback": 54, "hits_to_win": 2,
        "ranged": False, "effect": "smash",
    },
    "bow": {  # ranged: draws back, then looses an arrow that streaks to the aim.
        "range": 340, "approach": 240, "windup": 18, "strike": 4, "recovery": 16,
        "cooldown": 32, "lunge": 0, "knockback": 40, "hits_to_win": 3,
        "ranged": True, "effect": "arrow",
    },
    "pistol": {  # ranged: aims, then fires a small projectile from afar.
        "range": 300, "approach": 220, "windup": 14, "strike": 4, "recovery": 18,
        "cooldown": 36, "lunge": 0, "knockback": 66, "hits_to_win": 2,
        "ranged": True, "effect": "shot",
    },
}

# Combat AI / mobility ------------------------------------------------------
# The brain first asks whether it can actually reach the cursor. If the cursor
# floats higher than FLY_TRIGGER_HEIGHT above the pet's feet (out of walking /
# small-hop reach), a melee fighter fires up a little jetpack and flies at it
# rather than hopping uselessly toward the top of the screen. A ranged fighter
# just lines up and shoots. If a flight runs out of fuel without landing a hit
# too many times, the pet adapts and pulls a ranged weapon instead.
FLY_TRIGGER_HEIGHT = 74              # Cursor this far above feet -> unreachable on foot.
FLY_THRUST = 0.7                     # Accel per frame toward the cursor while flying.
FLY_MAX_SPEED = 6.5                  # Speed cap while flying.
FLY_LIFTOFF_VY = -3.0               # Initial upward kick on take-off.
FLY_DURATION = 170                   # Frames of jetpack fuel per launch (~2.8s).
FLY_COOLDOWN = 40                    # Frames grounded before he can fly again.
FLY_HOVER_RANGE = 1.05               # Range multiplier for attacking mid-air.
FLY_FLAME_CHANCE = 0.85              # Per-frame chance of a jetpack flame puff.
REACH_FAILS_TO_RANGED = 2            # Fruitless flights before switching to ranged.

# Playful jetpack hop: even when perfectly calm, now and then he fires the
# jetpack for fun instead of a normal jump — floating up and drifting a little
# before settling back down. He rises, hovers, then eases back down UNDER POWER
# (a controlled descent, not a free-fall) and touches down softly, so he never
# looks like he's teleporting to the floor.
JETPACK_HOP_CHANCE = 0.15            # Fraction of untargeted jumps done as a hop.
JETPACK_HOP_DURATION = 60            # Frames of rise + hover before easing down.
JOY_FLY_THRUST = 0.35               # Upward thrust per frame while rising.
JOY_FLY_RISE_CAP = 4.0              # Cap on climb speed so the hop isn't a rocket.
JOY_FLY_DESCEND_SPEED = 2.6         # Gentle, capped speed of the powered descent.

# Capturing the cursor: after landing hits_to_win clean blows he pounces, pins
# the pointer for a beat (celebrating), then flings it across the screen and
# does a little victory dance before calming down.
CAPTURE_LOCK_FRAMES = 66             # Frames the cursor stays pinned in the finale.
VICTORY_DURATION = 96                # Frames of celebration after a capture (~1.6s).

# Petting / love ------------------------------------------------------------
# Petting is a slow back-and-forth stroke of the cursor over the pet. Each
# direction reversal at a gentle speed counts as one stroke.
STROKE_MIN_SPEED = 1.5               # Min cursor px/frame to count as a stroke.
STROKE_MAX_SPEED = 22.0              # Above this it's a flick, not a stroke.
PET_STROKE_LOVE = 0.9                # Love gained per stroke.
PET_STROKE_CALM = 0.6                # Anger soothed per stroke.
LOVE_THRESHOLD = 4                   # Love needed before he feels loved.
LOVE_MAX = 8.0                       # Love is capped here.
LOVE_DURATION = 360                  # Frames he stays smitten (~6s) once love fades.
LOVE_DECAY = 0.01                    # Love cooled per frame.

# Breeding ------------------------------------------------------------------
# Breeding is a little courtship: two pets waddle toward each other trailing
# hearts, and when they meet a baby pops out. The baby starts tiny and grows up,
# inheriting a blend of its parents' colour, temperament, name, and weapon
# taste. A cooldown stops it being spammed; MAX_PETS caps the population.
MAX_PETS = 12                        # Hard cap so breeding can't run away.
BREED_COOLDOWN = 900                 # Frames between breedings (~15s).
COURT_SPEED = 1.7                    # Walk speed while waddling toward a mate.
COURT_REACH = 60                     # Distance (px) at which the parents "meet".
COURT_TIMEOUT = 480                  # Give up closing the gap after this (~8s).
COURT_HEART_CHANCE = 0.12            # Per-frame chance of a heart while courting.
# The meeting: once both parents arrive they play a short cuddle — a shower of
# hearts and a little bounce — before the baby actually pops out.
COURT_MEET_FRAMES = 96               # Length of the breeding moment (~1.6s).
COURT_MEET_HEART_CHANCE = 0.55       # Per-frame heart chance during the meeting.

# Babies --------------------------------------------------------------------
# A newborn stays tiny and cute for a good while. It holds at BABY_MIN_SCALE for
# BABY_GROW_DELAY frames (barely growing), then grows the rest of the way over
# BABY_GROW_FRAMES so the change is gradual and noticeable — no snapping to full
# size after a blink.
BABY_MIN_SCALE = 0.42                # How small a newborn starts (fraction of adult).
BABY_GROW_DELAY = 2400               # Frames it stays tiny before growing (~40s).
BABY_GROW_FRAMES = 3000              # Frames to grow to full after the delay (~50s).
BABY_NAME_SUFFIX = " Jr"             # Appended when a baby takes a parent's name.
# Babies are defenceless: a click/attack scares them into running away and hiding
# instead of arming up, and it flags nearby adults to come to the rescue.
BABY_FLEE_SPEED = 2.6                # Run speed while fleeing a threat.
BABY_FLEE_DURATION = 200             # Frames a baby stays scared and running (~3.3s).
BABY_DEFENSE_RADIUS = 320            # Adults within this of a threatened baby defend it.

# Group combat --------------------------------------------------------------
# Pets back each other up. When one adult goes to war, other adults CLOSE ENOUGH
# to it (not the whole screen) notice and join in — but only on a chance roll so
# they don't all pile in on the same frame. Babies never join.
GROUP_SUPPORT_RADIUS = 260           # Distance (px) within which adults join a fight.
GROUP_JOIN_CHANCE = 0.05             # Per-frame chance a nearby adult joins in.
GROUP_JOIN_ANGER = 4.0               # Anger seeded into a recruit (tips it toward rage).

# Removal / death -----------------------------------------------------------
# Removing a pet plays a short, silly send-off instead of a blink-out. Removing
# every pet at once is gated behind a confirmation so it can't happen by accident.
DEATH_FRAMES = 60                    # Length of the removal animation (~1s).
DEATH_KINDS = ["poof", "explosion", "ghost", "fall"]

# Personality & social ------------------------------------------------------
# Each pet gets a temperament that scales its behaviour: how much it idles vs
# moves, how fast, how often it jumps, how sociable it is, how quickly it
# angers, and how playful it is. Bred children inherit a blend of their
# parents'. Sociable pets wander over to each other and trade hearts.
PERSONALITIES = [
    {"name": "Lazy",    "idle": 1.9, "speed": 0.8,  "jump": 0.5, "social": 0.8, "anger": 0.9, "play": 0.8},
    {"name": "Hyper",   "idle": 0.5, "speed": 1.3,  "jump": 1.7, "social": 1.2, "anger": 1.0, "play": 1.5},
    {"name": "Clingy",  "idle": 1.0, "speed": 1.05, "jump": 0.9, "social": 2.4, "anger": 0.8, "play": 1.2},
    {"name": "Grumpy",  "idle": 1.3, "speed": 0.95, "jump": 0.8, "social": 0.5, "anger": 1.7, "play": 0.7},
    {"name": "Playful", "idle": 0.8, "speed": 1.1,  "jump": 1.2, "social": 1.7, "anger": 0.9, "play": 1.9},
    {"name": "Calm",    "idle": 1.3, "speed": 0.9,  "jump": 0.7, "social": 1.0, "anger": 0.7, "play": 1.0},
]
PERSONALITY_TRAITS = ("idle", "speed", "jump", "social", "anger", "play")
SOCIAL_CHANCE = 0.004                # Per-frame base chance to wander to another pet.
SOCIAL_REACH = 30                    # Distance (px) at which a greeting happens.
SOCIAL_GREET_LOVE = 1.6              # Love gained from a friendly greeting.

# Idle / AFK sleep ----------------------------------------------------------
# When the whole machine sees no keyboard or mouse for this long, the pet curls
# up and sleeps (Zzz particles). Any input wakes it. Tune AFK_SLEEP_SECONDS down
# for a sleepier pet.
AFK_SLEEP_SECONDS = 90               # Seconds of no input before dozing off.
ZZZ_INTERVAL_MIN = 40                # Frames between sleepy "Z" puffs.
ZZZ_INTERVAL_MAX = 80

# Typing energy -------------------------------------------------------------
# The pet reads your global keydown rate. Type steadily and he warms up into an
# excited, bouncy mood; sit at the keyboard without typing and he gets bored.
# Hysteresis (separate on/off thresholds), gentle smoothing, and a hold timer
# keep him from flipping moods on every single keystroke.
TYPING_RATE_SMOOTHING = 0.04         # EMA weight for new keystrokes (lower = calmer).
EXCITED_ON = 4.5                     # Sustained keys/sec needed to get excited (warmup).
EXCITED_OFF = 2.0                    # Drops back below this (plus the hold) to calm down.
EXCITED_HOLD = 90                    # Frames he stays excited after the last fast typing.
EXCITED_HOP_CHANCE = 0.02            # Per-frame chance to bounce while excited.
EXCITED_FX_CHANCE = 0.04             # Per-frame chance to sparkle while excited.
BORED_SECONDS = 30                   # No input at all this long (but < AFK) -> bored.

# Pomodoro focus ------------------------------------------------------------
# "Start Focus" in the menu bar makes every pet settle down and work alongside
# you; when the timer runs out they throw a little party.
FOCUS_MINUTES = 25

# Throwing physics ----------------------------------------------------------
# Flick-drag the pet and let go: a fast release launches him into a tumbling
# arc that bounces off the floor, walls, and windows before settling.
THROW_MIN_SPEED = 6.0                # Release px/frame needed to count as a throw.
THROW_MAX_SPEED = 26.0               # Cap on launch speed so he can't rocket away.
THROW_RESTITUTION = 0.55             # Vertical energy kept per bounce.
THROW_FRICTION = 0.7                 # Horizontal speed kept per floor bounce.
THROW_AIR_FRICTION = 0.992           # Horizontal damping while airborne.
THROW_REST_SPEED = 1.8               # Below this on a bounce he settles and stands.
TUMBLE_SPIN_SCALE = 2.2              # Degrees of spin per unit of horizontal speed.
# Once he stops bouncing he may be lying on his side or back; a damped angular
# spring rights him with a little wobble instead of snapping upright instantly.
RIGHT_STIFFNESS = 0.05               # Pull back toward upright (higher = snappier).
RIGHT_DAMPING = 0.82                 # Angular velocity retained per frame.
RIGHT_SETTLE = 1.5                   # Degrees / deg-per-frame below which he's up.

# Personality / name --------------------------------------------------------
# Each palette recolours the pet; a name gives him a little identity. Both are
# cycled from the menu bar (Recolour / Rename).
PALETTES = [
    {"name": "Ginger", "color": (236, 145, 92, 255), "shade": (195, 92, 72, 255),
     "belly": (255, 198, 139, 255), "highlight": (255, 221, 176, 255)},
    {"name": "Mint", "color": (118, 200, 158, 255), "shade": (74, 150, 116, 255),
     "belly": (214, 245, 228, 255), "highlight": (198, 245, 220, 255)},
    {"name": "Bubblegum", "color": (240, 150, 190, 255), "shade": (200, 100, 150, 255),
     "belly": (255, 216, 236, 255), "highlight": (255, 226, 242, 255)},
    {"name": "Slate", "color": (140, 150, 172, 255), "shade": (94, 104, 126, 255),
     "belly": (212, 220, 234, 255), "highlight": (222, 230, 242, 255)},
    {"name": "Gold", "color": (230, 196, 92, 255), "shade": (190, 150, 60, 255),
     "belly": (255, 236, 172, 255), "highlight": (255, 242, 192, 255)},
]
PET_NAMES = [
    "Pixel", "Mochi", "Biscuit", "Waffle", "Pebble", "Tofu", "Noodle", "Gizmo",
    "Sprout", "Mango", "Cosmo", "Bean", "Pip", "Hazel", "Yuki", "Pretzel",
]

# Curiosity -----------------------------------------------------------------
# Now and then something catches his eye and he trots over to investigate.
CURIOUS_CHANCE = 0.0002              # Per-frame chance to get curious while idle (~80s).
CURIOUS_DURATION = 240               # Frames a curious spell lasts (~4s).
CURIOUS_SPEED = 1.4                  # Walk speed while investigating.

# Fright (shake him to scare him) -------------------------------------------
SHAKE_SPEED = 11                     # Drag px/frame that counts as a shake stroke.
SHAKE_REVERSALS = 4                  # Quick direction flips that trigger fright.
SHAKE_WINDOW = 26                    # Frames the reversal tally lingers.
SCARED_DURATION = 180                # Frames he stays spooked (~3s).
SCARED_TREMBLE = 1.2                 # Pixels of nervous shiver while scared.

# Fetch / ball --------------------------------------------------------------
# "Toss a ball" drops a bouncy ball; the nearest pet chases it and bats it.
BALL_SCALE = 3
BALL_BASE_R = 4                      # Ball radius in base (pre-scale) pixels.
BALL_WIN = 12 * BALL_SCALE           # Ball overlay window size in screen pixels.
BALL_COLOR = (90, 175, 235, 255)
BALL_SHADE = (54, 124, 186, 255)
BALL_HIGHLIGHT = (210, 238, 255, 255)
BALL_RESTITUTION = 0.62              # Bounce energy kept off floors/windows.
BALL_FRICTION = 0.93                 # Horizontal speed kept while rolling.
BALL_AIR_FRICTION = 0.995
BALL_REST_SPEED = 0.45               # Below this it has come to rest.
BALL_KICK_VX = 6.5                   # Sideways pop when the pet bats it.
BALL_KICK_VY = 7.5                   # Upward pop when the pet bats it.
FETCH_SPEED = 3.0                    # How fast the pet charges the ball.
BAT_RANGE = 24                       # Distance (px) at which the pet bats the ball.
FETCH_REACH_HEIGHT = 90              # Only chase a ball within this vertical reach.

# Weapon pixel art ----------------------------------------------------------
WEAPON_SCALE = 3
STEEL_COLOR = (206, 212, 224, 255)
STEEL_SHADE = (150, 158, 172, 255)
STEEL_HI = (244, 248, 255, 255)      # Bright edge/highlight on a blade.
HANDLE_COLOR = (120, 72, 40, 255)
HANDLE_SHADE = (86, 50, 26, 255)     # Darker underside of a wooden handle/shaft.
GUARD_COLOR = (222, 182, 64, 255)
GUARD_SHADE = (176, 138, 40, 255)    # Shaded side of a brass guard/pommel.
GUN_COLOR = (58, 60, 70, 255)
GUN_SHADE = (36, 38, 46, 255)        # Darker gun body.
GUN_HI = (120, 126, 140, 255)        # Slide highlight on the gun.
GUN_GRIP_COLOR = (120, 72, 40, 255)
HAMMER_HEAD_COLOR = (128, 134, 150, 255)  # Steel hammer head.
HAMMER_HEAD_SHADE = (92, 98, 114, 255)    # Shaded side of the hammer head.
BOW_WOOD_COLOR = (150, 96, 52, 255)  # Bow limb wood.
BOW_WOOD_SHADE = (108, 66, 34, 255)  # Shaded side of the bow limb.
BOW_STRING_COLOR = (232, 236, 244, 255)   # Taut bowstring.

ANGRY_PHRASES = [
    "Hey!",
    "Stop poking me!",
    "Quit it!",
    "Grrr!",
    "Leave me alone!",
    "Ouch!",
    "Cut it out!",
    "Rude!",
    "Not a button!",
]

PHRASES = [
    "Go work!",
    "Back to work!",
    "Focus, human!",
    "No slacking!",
    "You got this!",
    "Ship it!",
    "Just one more task.",
    "Deep breath. Begin.",
    "Eyes on the prize!",
    "Stop scrolling!",
    "Hydrate!",
    "Drink some water.",
    "Stretch your legs.",
    "Sit up straight!",
    "Blink. Rest your eyes.",
    "Take a tiny break.",
    "Snack time?",
    "You're doing great.",
    "Almost there!",
    "Keep going!",
    "One step at a time.",
    "Save your work!",
    "Did you commit?",
    "I like you :)",
    "Write the tests.",
    "Read the docs.",
    "Refactor later.",
    "I feel good. How about you?",
    "Coffee break!",
    "Tabs or spaces?",
    "It works on my machine!",
    "Have you tried turning it off?",
    "How are you doing?",
    "Rubber duck me!",
    "Commit early, commit often.",
    "Less talk, more do.",
    "Inbox zero, maybe?",
    "Plan, then do.",
    "Small wins count.",
    "Procrastination later!",
    "I believe in you.",
    "Touch grass soon!",
    "Posture check!",
    "Are we there yet?",
    "Mmm, pixels.",
    "I'm watching you.",
    "Don't give up!",
    "Make it happen!",
    "Today is the day!",
    "Crush that to-do list!",
    "Boop! Now work.",
    "Stay hungry, stay foolish.",
    "You're doing wonderfully.",
    "Sending good vibes.",
    "Little by little.",
    "You are unstoppable.",
    "Be kind to yourself.",
    "Smile!",
    "Keep shining.",
    "A little progress is still progress.",
    "You're capable of hard things.",
    "Sprinkle some joy.",
    "Breathe in, breathe out.",
    "Hug a pillow.",
    "Take your time.",
    "Dream big.",
    "Look at how far you've come.",
    "You make a difference.",
    "Keep learning.",
    "Celebrate small victories.",
    "Don't forget to eat!",
    "Honey never spoils.",
    "Wombat poop is cube-shaped.",
    "A hippopotamus's sweat is pink.",
    "A crocodile cannot stick its tongue out.",
    "A shrimp's heart is located in its head.",
    "Humans are the only animals that blush.",
]

LOVE_PHRASES = [
    "I love you!",
    "You're the best!",
    "More pets, please!",
    "So cozy.",
    "Purrrr.",
    "Best human ever.",
    "Aww, hi!",
    "You're so kind.",
    "I feel loved!",
    "Tee-hee!",
    "My favorite person.",
    "Pet me forever?",
    "Heart you!",
    "Cuddles!",
    "You make me happy.",
]

RAGE_CATCH_PHRASES = [
    "Gotcha!",
    "Caught you!",
    "Yeet!",
    "Begone!",
    "Mine now!",
    "Got your mouse!",
    "Outta here!",
    "Take that!",
]

RAGE_AIM_PHRASES = [
    "Hold still!",
    "Don't move!",
    "Steady...",
    "Cornered!",
    "Almost...",
    "Got you now!",
]

RAGE_LOCK_PHRASES = [
    "Locked!",
    "Pinned!",
    "Frozen!",
    "Stay put!",
    "No escape!",
]

RAGE_PHRASES = [
    "I'll get you!",
    "Come here!",
    "You asked for it!",
    "RAAAGH!",
    "No more nice pet!",
    "Taste this!",
    "You're done!",
    "Run while you can!",
    "Off with you!",
    "I warned you!",
    "Feel my wrath!",
    "En garde!",
    "Bang bang!",
    "Get back here!",
    "This is your fault!",
]

EXCITED_PHRASES = [
    "Wheee!",
    "Look at you go!",
    "On fire!",
    "Productive!",
    "Nice pace!",
    "Zoom zoom!",
    "Keep typing!",
    "So fast!",
    "Yes yes yes!",
    "Unstoppable!",
    "Flow state!",
    "Clack clack clack!",
]

BORED_PHRASES = [
    "So bored...",
    "Type something?",
    "Hello? Work?",
    "Yawn...",
    "Let's do stuff!",
    "I'm bored.",
    "Tap tap tap?",
    "Are we working?",
    "Wake the keyboard!",
    "Do something!",
    "Any minute now...",
    "Still waiting.",
]

FOCUS_PHRASES = [
    "Focusing...",
    "Deep work.",
    "In the zone.",
    "Heads down.",
    "Stay on task.",
    "Keep at it.",
    "No distractions.",
    "We got this.",
    "Eyes on it.",
    "Almost there!",
]

CURIOUS_PHRASES = [
    "Ooh, what's that?",
    "Hmm?",
    "What's this?",
    "Let me see!",
    "Interesting...",
    "Huh?",
    "Curious...",
    "What's over here?",
    "A new thing!",
    "Investigating!",
]

SCARED_PHRASES = [
    "Eek!",
    "Put me down!",
    "Whoa whoa!",
    "Too fast!",
    "Scary!",
    "Wh-what?!",
    "Stop shaking!",
    "I'm dizzy!",
    "Help!",
    "Yikes!",
]

PLAY_PHRASES = [
    "Fetch!",
    "Got it!",
    "Wheee!",
    "My ball!",
    "Again!",
    "Bonk!",
    "Catch me!",
    "Play time!",
]

VICTORY_PHRASES = [
    "Victory!",
    "Too easy!",
    "Champion!",
    "Who's next?",
    "Flawless!",
    "I win!",
    "Get rekt!",
    "Mic drop.",
    "GG!",
]

COURT_PHRASES = [
    "Hello there...",
    "Be mine?",
    "You're cute!",
    "Let's make a family!",
    "Come closer!",
    "Heart you!",
    "Tee-hee!",
]

BABY_PHRASES = [
    "Goo goo!",
    "Hi world!",
    "I'm new!",
    "Tiny me!",
    "Wheee!",
    "Hewwo!",
]
