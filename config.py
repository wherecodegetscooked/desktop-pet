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

# Mouse interaction --------------------------------------------------------
FOLLOW_CHANCE = 0.004                # Per-frame chance to start chasing the cursor.
FOLLOW_STOP_DISTANCE = 12            # Stop once this close (px) to the cursor.
FOLLOW_RUN_DISTANCE = 220            # Run instead of walk when farther than this.
IDLE_FX_MIN = 360                    # Min frames between spontaneous heart/stars.
IDLE_FX_MAX = 1080

# Anger ---------------------------------------------------------------------
ANGRY_THRESHOLD = 3                  # Clicks (before cooling down) that anger the pet.
ANGRY_DURATION = 240                 # Frames the pet stays grumpy (~4s).
ANGER_DECAY = 0.015                  # Anger cooled per frame.

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
    "Push to main!",
    "Write the tests.",
    "Read the docs.",
    "Refactor later.",
    "Ship now, polish later.",
    "Coffee break!",
    "Tabs or spaces?",
    "It works on my machine!",
    "Have you tried turning it off?",
    "Bug? Or feature?",
    "Rubber duck me!",
    "Commit early, commit often.",
    "Less talk, more code.",
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
]
