"""The pet's behaviour model: state machine, physics, and reactions.

`Pet` is pure logic — it owns position, velocity, the current animation state,
talking/anger/particle bookkeeping, and the platform-jumping AI. It holds no
windowing or drawing code; the overlay renders whatever the pet's fields say.
"""

import math
import random

from config import (
    AFK_SLEEP_SECONDS,
    BALL_KICK_VX,
    BALL_KICK_VY,
    BAT_RANGE,
    CURIOUS_CHANCE,
    CURIOUS_DURATION,
    CURIOUS_PHRASES,
    CURIOUS_SPEED,
    FETCH_REACH_HEIGHT,
    FETCH_SPEED,
    PALETTES,
    PET_NAMES,
    PLAY_PHRASES,
    SCARED_DURATION,
    SCARED_PHRASES,
    SCARED_TREMBLE,
    SHAKE_REVERSALS,
    SHAKE_SPEED,
    SHAKE_WINDOW,
    ANGER_DECAY,
    ANGRY_DURATION,
    ANGRY_PHRASES,
    ANGRY_THRESHOLD,
    BORED_SECONDS,
    BORED_PHRASES,
    EXCITED_FX_CHANCE,
    EXCITED_HOLD,
    EXCITED_HOP_CHANCE,
    EXCITED_OFF,
    EXCITED_ON,
    EXCITED_PHRASES,
    FOCUS_PHRASES,
    FOLLOW_CHANCE,
    FOLLOW_RUN_DISTANCE,
    FOLLOW_STOP_DISTANCE,
    FPS,
    GRAVITY,
    GROUND_PLATFORM_NAME,
    IDLE_FX_MAX,
    IDLE_FX_MIN,
    LOVE_DECAY,
    LOVE_DURATION,
    LOVE_MAX,
    LOVE_PHRASES,
    LOVE_THRESHOLD,
    MAX_PARTICLES,
    MAX_TARGET_DISTANCE,
    MAX_TARGET_HEIGHT,
    MAX_TARGET_JUMP_POWER,
    MAX_TARGET_JUMP_SPEED_X,
    NORMAL_JUMP_POWER_MAX,
    NORMAL_JUMP_POWER_MIN,
    NOTE_INTERVAL_MAX,
    NOTE_INTERVAL_MIN,
    PERSONALITIES,
    PERSONALITY_TRAITS,
    PET_STROKE_CALM,
    PET_STROKE_LOVE,
    PHRASES,
    PLATFORM_DROP_CHANCE,
    PLATFORM_EDGE_MARGIN,
    RAGE_AIM_PHRASES,
    RAGE_CATCH_PHRASES,
    RAGE_CHASE_SPEED,
    RAGE_DURATION,
    RAGE_LOCK_PHRASES,
    RAGE_PHRASES,
    RAGE_THRESHOLD,
    CAPTURE_LOCK_FRAMES,
    VICTORY_DURATION,
    VICTORY_PHRASES,
    COURT_SPEED,
    COURT_REACH,
    COURT_HEART_CHANCE,
    COURT_PHRASES,
    BABY_GROW_RATE,
    BABY_NAME_SUFFIX,
    BABY_PHRASES,
    DEATH_FRAMES,
    DEATH_KINDS,
    WEAPON_STATS,
    RANDOM_JUMP_STATE_CHANCE,
    RIGHT_DAMPING,
    RIGHT_SETTLE,
    RIGHT_STIFFNESS,
    SOCIAL_CHANCE,
    SOCIAL_GREET_LOVE,
    SOCIAL_REACH,
    SPEAK_CHANCE,
    SPEAK_COOLDOWN_MAX,
    SPEAK_COOLDOWN_MIN,
    SPEECH_MIN_FRAMES,
    SPEECH_PER_CHAR,
    STROKE_MAX_SPEED,
    STROKE_MIN_SPEED,
    TARGET_JUMP_EXTRA_HEIGHT,
    TYPING_RATE_SMOOTHING,
    TARGET_JUMP_POWER_MIN,
    THROW_AIR_FRICTION,
    THROW_FRICTION,
    THROW_MAX_SPEED,
    THROW_MIN_SPEED,
    THROW_REST_SPEED,
    THROW_RESTITUTION,
    TUMBLE_SPIN_SCALE,
    WEAPONS,
    WINDOW_H,
    WINDOW_JUMP_CHANCE,
    WINDOW_W,
    ZZZ_INTERVAL_MAX,
    ZZZ_INTERVAL_MIN,
)


class State:
    IDLE = "IDLE"
    WALK = "WALK"
    RUN = "RUN"
    JUMP = "JUMP"


class Pet:
    def __init__(self, bounds):
        self.set_bounds(bounds)
        self.x = float((self.min_x + self.max_x) // 2)
        self.y = float((self.min_y + self.max_y) // 2)
        self.vx = 0.0
        self.vy = 0.0
        self.state = State.IDLE
        self.state_timer = 0
        self.facing_right = True
        self.frame = 0
        self.blink = False
        self.blink_timer = random.randint(90, 240)
        self.look_offset = 0
        self.look_timer = random.randint(60, 180)
        self.ground_y = self.y
        self.jump_vy = 0.0
        self.airborne = False
        self.platform = None
        self.jump_target = None
        self.jump_cooldown = 0
        self.talking = False
        self.speech_text = ""
        self.speech_timer = 0
        self.speech_cooldown = random.randint(120, 600)
        self.speech_dirty = False
        self.speech_surface = None
        self.speech_tail_up = False
        self.following = False
        self.follow_timer = 0
        self.particles = []
        self.idle_fx_timer = random.randint(IDLE_FX_MIN, IDLE_FX_MAX)
        self.anger = 0.0
        self.angry = False
        self.angry_timer = 0
        # Violence: once anger boils over he arms himself and goes into combat.
        self.rage = False
        self.rage_timer = 0
        self.weapon = None
        # Each pet has a favourite weapon it reaches for when enraged; bred
        # children inherit a parent's taste (see make_baby).
        self.weapon_pref = random.choice(WEAPONS)
        # Combat timeline: an attack runs windup -> strike -> recovery, then a
        # cooldown before the next one. He lands clean hits until enough connect
        # to trigger the capture finale.
        self.combat_phase = None     # None | "windup" | "strike" | "recovery"
        self.phase_timer = 0
        self.phase_max = 1
        self.attack_cooldown = 0
        self.hits_landed = 0
        self._aim = None             # cursor pos committed to at swing start
        self.attack_landed = False
        # Cursor capture. The finale pins the pointer (cursor_lock: the main loop
        # warps to this every frame until released), then flings it once
        # (cursor_grab: one-shot warp target). Individual hits also knock the
        # cursor back via cursor_grab. All None when idle.
        self.cursor_grab = None
        self.cursor_lock = None
        self.capturing = False
        self.lock_timer = 0
        # Victory: a short celebration after a successful capture.
        self.victory = False
        self.victory_timer = 0
        # Affection: slow strokes make him fall in love.
        self.love = 0.0
        self.loved = False
        self.loved_timer = 0
        self._last_cursor_x = None
        self._stroke_dir = 0
        # App-aware reactions: what the human is doing right now (set by the
        # main loop). `activity` is "work" | "video" | "gaming" | None; `music`
        # is True while a music app is running.
        self.activity = None
        self.music = False
        self._note_timer = random.randint(NOTE_INTERVAL_MIN, NOTE_INTERVAL_MAX)
        # Activity-driven energy: sleep when the machine is idle, get excited
        # when the human types fast, bored when present but not typing.
        self.asleep = False
        self.excited = False
        self.bored = False
        self.idle_seconds = 0.0
        self.typing_rate = 0.0
        self.excited_hold = 0
        self.zzz_timer = random.randint(ZZZ_INTERVAL_MIN, ZZZ_INTERVAL_MAX)
        # Pomodoro: focusing pets settle down and "work" alongside you.
        self.focusing = False
        # Throwing: a flicked release sends him tumbling, then he rights himself.
        self.tumbling = False
        self.righting = False
        self.angle = 0.0
        self.spin_speed = 0.0
        self.right_vel = 0.0
        self._drag_prev = None
        self._throw_vx = 0.0
        self._throw_vy = 0.0
        # Shake-to-scare: count quick drag reversals.
        self._shake_dir = 0
        self._shake_count = 0
        self._shake_decay = 0
        # Personality: a recolourable palette and a name.
        self.palette_index = 0
        self.palette = PALETTES[0]
        self.name = random.choice(PET_NAMES)
        # Temperament: scales idle/speed/jump/social/anger/play. Bred children
        # inherit a blend (see inherit_personality).
        self.personality = dict(random.choice(PERSONALITIES))
        # Social wandering toward other pets.
        self.socializing = False
        self.social_timer = 0
        self.social_target_x = 0.0
        self._peers = []
        # Breeding: babies grow from BABY_MIN_SCALE up to full size; courting
        # pets waddle toward a meeting point trading hearts.
        self.baby = False
        self.growth = 1.0
        self.courting = False
        self.court_target_x = 0.0
        self.court_timer = 0
        self.court_arrived = False
        # Removal: a short send-off animation before the pet is culled.
        self.dying = False
        self.dead = False
        self.death_kind = ""
        self.death_timer = 0
        self.death_max = 1
        # Extra moods.
        self.curious = False
        self.curious_timer = 0
        self.scared = False
        self.scared_timer = 0
        self.pick_state()

    @property
    def mood(self):
        if self.rage:
            return "rage"
        if self.angry:
            return "angry"
        if self.scared:
            return "scared"
        if self.victory:
            return "victory"
        if self.asleep:
            return "asleep"
        if self.loved:
            return "love"
        if self.excited:
            return "excited"
        if self.curious:
            return "curious"
        if self.bored:
            return "bored"
        return "neutral"

    def _phrase_pool(self):
        if self.rage:
            return RAGE_PHRASES
        if self.victory:
            return VICTORY_PHRASES
        if self.courting:
            return COURT_PHRASES
        if self.angry:
            return ANGRY_PHRASES
        if self.scared:
            return SCARED_PHRASES
        if self.loved:
            return LOVE_PHRASES
        if self.excited:
            return EXCITED_PHRASES
        if self.curious:
            return CURIOUS_PHRASES
        if self.bored:
            return BORED_PHRASES
        if self.focusing:
            return FOCUS_PHRASES
        return PHRASES

    def set_bounds(self, bounds):
        """Update the roamable area to the union of all displays.

        screen_w / screen_h stay as the *span* of the whole desktop so the
        jump-reachability heuristics keep working across monitors.
        """
        self.min_x, self.min_y, self.max_x, self.max_y = bounds
        self.screen_w = self.max_x - self.min_x
        self.screen_h = self.max_y - self.min_y

    def start_talk(self, text):
        self.talking = True
        self.speech_text = text
        self.speech_dirty = True
        self.speech_surface = None
        self.speech_timer = max(SPEECH_MIN_FRAMES, len(text) * SPEECH_PER_CHAR)
        self.state = State.IDLE
        self.vx = 0.0
        self.vy = 0.0

    def _maybe_talk(self):
        if self.speech_cooldown > 0:
            return
        if self.state not in (State.IDLE, State.WALK):
            return
        if random.random() > SPEAK_CHANCE:
            return
        self.start_talk(random.choice(self._phrase_pool()))

    def _update_talking(self):
        """Keep the pet planted while a bubble is up. Returns True if the rest
        of update() should be skipped this frame."""
        self.speech_timer -= 1
        if self.airborne:
            self._stop_talking(repick=False)
            return False
        if self.speech_timer <= 0:
            self._stop_talking(repick=True)
            return False
        self.state = State.IDLE
        self.vx = 0.0
        self.vy = 0.0
        if self.platform and self._feet_inside_platform(self.platform):
            self.y = self.platform["y"] - WINDOW_H
        return True

    def _stop_talking(self, repick):
        self.talking = False
        self.speech_text = ""
        self.speech_surface = None
        self.speech_dirty = False
        self.speech_cooldown = random.randint(SPEAK_COOLDOWN_MIN, SPEAK_COOLDOWN_MAX)
        if repick and not self.airborne:
            self.pick_state()

    # -- Particles ---------------------------------------------------------

    def spawn_particles(self, kind, count):
        head_x = self.x + WINDOW_W * 0.5
        for _ in range(count):
            if len(self.particles) >= MAX_PARTICLES:
                break
            if kind == "zzz":
                # Sleepy "Z" drifting slowly up and away from the head.
                life = random.randint(60, 90)
                ox = random.uniform(-2, 6)
                oy = random.uniform(-6, -1)
                vx = random.uniform(0.1, 0.4) * (1 if self.facing_right else -1)
                vy = random.uniform(-0.7, -0.4)
            elif kind == "dust":
                # Puff kicked up at the feet on a bounce.
                life = random.randint(16, 26)
                ox = random.uniform(-7, 7)
                oy = random.uniform(WINDOW_H - 6, WINDOW_H)
                vx = random.uniform(-1.4, 1.4)
                vy = random.uniform(-0.7, -0.1)
            elif kind == "popcorn":
                # Little kernels popping up out of the held tub.
                life = random.randint(18, 30)
                ox = random.uniform(-7, 7)
                oy = random.uniform(WINDOW_H * 0.45, WINDOW_H * 0.7)
                vx = random.uniform(-0.9, 0.9)
                vy = random.uniform(-1.7, -0.9)
            else:
                life = random.randint(42, 66)
                ox = random.uniform(-9, 9)
                oy = random.uniform(-3, 7)
                vx = random.uniform(-0.7, 0.7)
                vy = random.uniform(-1.8, -0.9)
            self.particles.append(
                {
                    "kind": kind,
                    "x": head_x + ox,
                    "y": self.y + oy,
                    "vx": vx,
                    "vy": vy,
                    "life": life,
                    "maxlife": life,
                }
            )

    def _add_particle(self, kind, x, y, vx, vy, life, grav=0.02, flip=False):
        """Append a fully-specified particle at an arbitrary world position.

        Used by the combat and removal effects, which need to place sprites at
        the cursor / impact point rather than around the pet's head like
        spawn_particles does."""
        if len(self.particles) >= MAX_PARTICLES:
            return
        self.particles.append(
            {
                "kind": kind,
                "x": x,
                "y": y,
                "vx": vx,
                "vy": vy,
                "life": life,
                "maxlife": life,
                "grav": grav,
                "flip": flip,
            }
        )

    def _update_particles(self):
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += p.get("grav", 0.02)
            p["life"] -= 1
        if self.particles:
            self.particles = [p for p in self.particles if p["life"] > 0]

    def _maybe_idle_fx(self):
        self.idle_fx_timer -= 1
        if self.idle_fx_timer > 0:
            return
        self.idle_fx_timer = random.randint(IDLE_FX_MIN, IDLE_FX_MAX)
        if not self.angry and not self.airborne:
            self.spawn_particles(random.choice(["heart", "star"]), 1)

    def set_activity(self, activity, music):
        """Reflect what the human is doing this detection tick (see activity.py).
        Purely visual: the props are drawn by the renderer from these fields."""
        self.activity = activity
        self.music = music

    def _activity_fx(self):
        """Float music notes while music plays; sparkle a little while gaming.
        Skipped in moods where props are hidden (asleep, upset, mid-throw)."""
        if (
            self.airborne
            or self.asleep
            or self.angry
            or self.rage
            or self.scared
        ):
            return
        if self.music:
            self._note_timer -= 1
            if self._note_timer <= 0:
                self._note_timer = random.randint(NOTE_INTERVAL_MIN, NOTE_INTERVAL_MAX)
                self.spawn_particles("note", 1)
        elif self.activity == "video" and random.random() < 0.05:
            self.spawn_particles("popcorn", 1)
        elif self.activity == "gaming" and random.random() < 0.03:
            self.spawn_particles("star", 1)

    # -- Activity / energy -------------------------------------------------

    def observe_activity(self, idle_seconds, keys):
        """Fold in the machine's input activity once per frame: `idle_seconds`
        is time since any keyboard/mouse event, `keys` is keydowns this frame.
        Drives dozing off (AFK), excitement (fast typing), and boredom."""
        self.idle_seconds = idle_seconds
        # Smoothed keys/sec. A single keystroke barely nudges this (warmup); it
        # also coasts down slowly after you stop (cooldown), so the mood is
        # stable instead of flipping on every letter.
        instant_rate = keys * FPS
        self.typing_rate += (instant_rate - self.typing_rate) * TYPING_RATE_SMOOTHING
        self.excited_hold = max(0, self.excited_hold - 1)

        calm = not self.rage and not self.angry
        want_sleep = (
            idle_seconds >= AFK_SLEEP_SECONDS
            and calm
            and not self.airborne
            and not self.tumbling
        )
        if want_sleep and not self.asleep:
            self.asleep = True
            self.zzz_timer = random.randint(ZZZ_INTERVAL_MIN, ZZZ_INTERVAL_MAX)
            self.following = False
            if self.talking:
                self._stop_talking(repick=False)
        elif not want_sleep and self.asleep:
            self.asleep = False
            self.spawn_particles("star", 1)
            self.state_timer = random.randint(30, 60)

        if self.asleep:
            self.excited = False
            self.bored = False
            self.excited_hold = 0
            return

        # Excitement with hysteresis: needs sustained typing to switch on, then
        # holds for a beat and only drops once typing has clearly trailed off.
        if not calm:
            self.excited = False
            self.excited_hold = 0
        elif self.typing_rate >= EXCITED_ON:
            self.excited = True
            self.excited_hold = EXCITED_HOLD
        elif self.excited and self.typing_rate < EXCITED_OFF and self.excited_hold == 0:
            self.excited = False

        # Bored only when there's truly no input (no typing, no cursor movement,
        # no clicks) for a while — any activity makes him neutral again. Past
        # AFK_SLEEP_SECONDS he's asleep instead.
        self.bored = (
            not self.excited
            and calm
            and BORED_SECONDS <= idle_seconds < AFK_SLEEP_SECONDS
        )

    def _update_sleep(self, platforms):
        """Hold still on the current platform and puff out the odd sleepy Z."""
        self.vx = 0.0
        self.vy = 0.0
        self.state = State.IDLE
        if self.platform and self._feet_inside_platform(self.platform):
            self.y = self.platform["y"] - WINDOW_H
        self.zzz_timer -= 1
        if self.zzz_timer <= 0:
            self.zzz_timer = random.randint(ZZZ_INTERVAL_MIN, ZZZ_INTERVAL_MAX)
            self.spawn_particles("zzz", 1)

    def _energy_fx(self):
        """Bounce and sparkle when excited (skips hops while focusing so he
        stays seated). Boredom shows through the face and phrases, not effects."""
        if self.airborne or self.state == State.JUMP or not self.excited:
            return
        if (
            not self.focusing
            and self.jump_cooldown == 0
            and self.state in (State.IDLE, State.WALK)
            and random.random() < EXCITED_HOP_CHANCE
        ):
            self.spawn_particles("star", 1)
            self.start_jump()
        elif random.random() < EXCITED_FX_CHANCE:
            self.spawn_particles("star", 1)

    # -- Pomodoro focus ----------------------------------------------------

    def start_focus(self):
        self.focusing = True
        self.following = False
        if not self.airborne and not self.tumbling:
            self.pick_state()

    def end_focus(self, party=False):
        self.focusing = False
        if party and not self.airborne and not self.tumbling:
            self.spawn_particles(random.choice(["star", "heart"]), 6)

    # -- Mouse interaction -------------------------------------------------

    def on_click(self, clicks, mouse=None):
        """React to taps. Clicks are hostile: a couple are tolerated (hearts),
        but poking too often angers him and eventually tips him into violence.
        Clicking also drains any affection he was building up."""
        for _ in range(clicks):
            if self.rage or self.angry:
                self.spawn_particles("anger", random.randint(2, 3))
            else:
                self.spawn_particles("heart", random.randint(1, 2))
        self.anger += clicks * self._trait("anger")
        self.love = max(0.0, self.love - clicks)
        if self.loved and self.love < 1.0:
            self.loved = False
        if not self.rage and self.anger >= RAGE_THRESHOLD:
            self._become_rage()
        elif not self.angry and self.anger >= ANGRY_THRESHOLD:
            self._become_angry()

    def _become_angry(self):
        self.angry = True
        self.angry_timer = ANGRY_DURATION
        self.following = False
        self.loved = False
        self.spawn_particles("anger", 5)
        self.start_talk(random.choice(ANGRY_PHRASES))

    def _become_rage(self):
        """Boil over: draw the favourite weapon and switch into combat mode."""
        self.rage = True
        self.angry = True
        self.angry_timer = ANGRY_DURATION
        self.rage_timer = RAGE_DURATION
        self.weapon = self.weapon_pref or random.choice(WEAPONS)
        self._reset_combat()
        self.following = False
        self.socializing = False
        self.courting = False
        self.loved = False
        self.victory = False
        self.love = 0.0
        # A beat of drawing the weapon: brace, face nothing in particular, and
        # throw out a couple of warning sparks before the chase begins.
        self.vx = 0.0
        self.state = State.IDLE
        self.spawn_particles("anger", 8)
        self.start_talk(random.choice(RAGE_PHRASES))

    def _reset_combat(self):
        """Clear the per-fight combat timeline (between fights / on calming)."""
        self.combat_phase = None
        self.phase_timer = 0
        self.phase_max = 1
        self.attack_cooldown = 18  # brief beat to draw the weapon before swinging
        self.hits_landed = 0
        self._aim = None
        self.attack_landed = False

    def _weapon_stats(self):
        return WEAPON_STATS.get(self.weapon or "knife", WEAPON_STATS["knife"])

    # -- Petting / affection ----------------------------------------------

    def observe_cursor(self, mouse):
        """Detect slow back-and-forth strokes over the pet (petting). Each
        direction reversal at a gentle speed counts as one stroke. Call once
        per frame with the global cursor position (or None)."""
        if mouse is None or self.airborne:
            self._last_cursor_x = None
            self._stroke_dir = 0
            return
        over = (
            self.x - 8 <= mouse[0] <= self.x + WINDOW_W + 8
            and self.y - 8 <= mouse[1] <= self.y + WINDOW_H + 8
        )
        if not over:
            self._last_cursor_x = None
            self._stroke_dir = 0
            return
        if self._last_cursor_x is not None:
            dx = mouse[0] - self._last_cursor_x
            if STROKE_MIN_SPEED <= abs(dx) <= STROKE_MAX_SPEED:
                direction = 1 if dx > 0 else -1
                if self._stroke_dir and direction != self._stroke_dir:
                    self._on_pet()
                self._stroke_dir = direction
        self._last_cursor_x = mouse[0]

    def _on_pet(self):
        if self.rage:
            return  # too furious to be soothed
        self.love = min(LOVE_MAX, self.love + PET_STROKE_LOVE)
        self.anger = max(0.0, self.anger - PET_STROKE_CALM)
        if self.angry and self.anger < 1.0:
            self.angry = False
        if not self.loved and self.love >= LOVE_THRESHOLD:
            self._become_loved()
        elif random.random() < 0.2:
            self.spawn_particles("heart", 1)

    def _become_loved(self):
        self.loved = True
        self.loved_timer = LOVE_DURATION
        self.angry = False
        self.spawn_particles("heart", 5)
        self.start_talk(random.choice(LOVE_PHRASES))

    def _update_mood(self):
        self.anger = max(0.0, self.anger - ANGER_DECAY)
        self.love = max(0.0, self.love - LOVE_DECAY)
        if self.rage:
            self.rage_timer -= 1
            if (
                self.rage_timer <= 0
                and self.anger < 1.0
                and not self.capturing
                and self.lock_timer <= 0
                and not self.combat_phase
            ):
                self.rage = False
                self.weapon = None
                self._reset_combat()
        if self.angry:
            self.angry_timer -= 1
            if self.angry_timer <= 0 and self.anger < 1.0 and not self.rage:
                self.angry = False
        if self.loved:
            self.loved_timer -= 1
            if self.loved_timer <= 0 and self.love < 1.0:
                self.loved = False

        if self.scared:
            self.scared_timer -= 1
            if self.scared_timer <= 0:
                self.scared = False
        if self.curious:
            self.curious_timer -= 1
            if self.curious_timer <= 0:
                self.curious = False

        # Now and then, when he's otherwise idle and content, something catches
        # his eye and he gets curious.
        if (
            not self.curious
            and not self.scared
            and not self.asleep
            and not self.rage
            and not self.angry
            and not self.excited
            and not self.bored
            and not self.loved
            and not self.focusing
            and not self.airborne
            and not self.tumbling
            and not self.righting
            and random.random() < CURIOUS_CHANCE
        ):
            self.curious = True
            self.curious_timer = CURIOUS_DURATION
            self.spawn_particles("question", 1)

    def _become_scared(self):
        self.scared = True
        self.scared_timer = SCARED_DURATION
        self.curious = False
        self.following = False
        self.courting = False
        self.loved = False
        self.spawn_particles("sweat", random.randint(2, 3))
        self.start_talk(random.choice(SCARED_PHRASES))

    def cycle_palette(self):
        """Recolour to the next palette (menu 'Recolour')."""
        self.palette_index = (self.palette_index + 1) % len(PALETTES)
        self.palette = PALETTES[self.palette_index]
        self.spawn_particles("star", 3)

    def rename(self, name=None):
        """Give him a new name and have him announce it (menu 'Rename')."""
        self.name = name or random.choice(PET_NAMES)
        self.spawn_particles("heart", 2)
        self.start_talk("I'm " + self.name + "!")

    # -- Curiosity / fright / fetch ---------------------------------------

    def _update_curious(self, mouse):
        """Trot over toward the cursor to investigate, with the odd '?'."""
        dx = mouse[0] - self._feet_x()
        if abs(dx) < FOLLOW_STOP_DISTANCE + 6:
            self.vx = 0.0
            self.state = State.IDLE
        else:
            direction = 1 if dx > 0 else -1
            self.vx = direction * CURIOUS_SPEED
            self.facing_right = direction > 0
            self.state = State.WALK
        self.state_timer = 20
        if random.random() < 0.02:
            self.spawn_particles("question", 1)

    def _update_scared(self, mouse):
        """Shiver in place and shy away from the cursor."""
        self.state = State.IDLE
        self.vx = random.uniform(-SCARED_TREMBLE, SCARED_TREMBLE)
        if mouse is not None:
            self.facing_right = mouse[0] <= self._feet_x()
        if random.random() < 0.05:
            self.spawn_particles("sweat", 1)

    def _wants_to_play(self, ball):
        """Whether he'll chase the ball right now (it has to be roughly at his
        level — he won't run off a window trying to reach one far below)."""
        if ball is None:
            return False
        if (
            self.asleep
            or self.rage
            or self.angry
            or self.scared
            or self.tumbling
            or self.righting
            or self.focusing
        ):
            return False
        return abs(ball.y - self.y) <= FETCH_REACH_HEIGHT

    def _update_fetch(self, ball):
        """Charge the ball; once close enough, bat it away to keep the game going."""
        dx = ball.x - self._feet_x()
        if abs(dx) <= BAT_RANGE:
            direction = 1 if dx >= 0 else -1
            ball.kick(direction * BALL_KICK_VX, -BALL_KICK_VY)
            self.facing_right = direction > 0
            self.vx = 0.0
            self.state = State.IDLE
            self.state_timer = 18
            self.jump_cooldown = max(self.jump_cooldown, 10)
            self.spawn_particles("star", 1)
            if random.random() < 0.12:
                self.start_talk(random.choice(PLAY_PHRASES))
        else:
            direction = 1 if dx > 0 else -1
            self.vx = direction * FETCH_SPEED
            self.facing_right = direction > 0
            self.state = State.RUN
            self.state_timer = 20

    # -- Combat ------------------------------------------------------------

    def _update_combat(self, mouse, platforms):
        """Run the combat brain while enraged: close to weapon range, then run
        the windup -> strike -> recovery timeline. Each weapon has its own reach,
        timing, lunge, and effect (see WEAPON_STATS). After enough clean hits he
        pounces and captures the cursor. Respects gravity and platforms — he
        never flies straight at it."""
        stats = self._weapon_stats()

        # Mid-swing: finish the committed attack regardless of cursor movement.
        # Fall back to the aim point if the cursor reading is momentarily gone.
        if self.combat_phase:
            self._advance_attack(mouse if mouse is not None else self._aim, stats)
            return

        if mouse is None:
            return

        self.attack_cooldown = max(0, self.attack_cooldown - 1)

        center_x = self.x + WINDOW_W / 2
        center_y = self.y + WINDOW_H / 2
        dist = math.hypot(mouse[0] - center_x, mouse[1] - center_y)
        grounded = not self.airborne and self.state != State.JUMP

        # In range, off cooldown, on his feet: commit to a swing/shot.
        if dist <= stats["range"] and self.attack_cooldown == 0 and grounded:
            self._start_attack(mouse, stats)
            return

        if not grounded:
            return  # let the current jump arc finish

        # Otherwise position for the weapon: close the horizontal gap to roughly
        # the weapon's preferred standoff, climbing or dropping to match height.
        feet_y = self.y + WINDOW_H
        dx = mouse[0] - self._feet_x()
        dy = mouse[1] - feet_y

        on_ledge = (
            self.platform is not None
            and self.platform["name"] != GROUND_PLATFORM_NAME
        )
        if dy > 50 and on_ledge and self.jump_cooldown == 0:
            self.drop()
            return

        if abs(dx) > stats["approach"]:
            self.vx = (1 if dx > 0 else -1) * RAGE_CHASE_SPEED
            self.state = State.RUN
            self.facing_right = dx > 0
        else:
            # Within standoff but not yet in striking range (e.g. cursor above):
            # hold, face the target, and brace for the next swing.
            self.vx = 0.0
            self.state = State.IDLE
            self.facing_right = mouse[0] >= center_x
            if random.random() < 0.08:
                self.spawn_particles("anger", 1)
        self.state_timer = 30
        # Climb toward the cursor when it's above him, hopping window to window.
        if mouse[1] < feet_y - 40:
            self._rage_jump(mouse, platforms)

    def _start_attack(self, mouse, stats):
        """Commit to a swing: lock the aim, face the target, begin the windup."""
        center_x = self.x + WINDOW_W / 2
        self.combat_phase = "windup"
        self.phase_timer = stats["windup"]
        self.phase_max = max(1, stats["windup"])
        self._aim = (mouse[0], mouse[1])
        self.attack_landed = False
        self.facing_right = mouse[0] >= center_x
        self.vx = 0.0
        self.state = State.IDLE
        self.spawn_particles("anger", 1)  # a small telegraph
        if random.random() < 0.4:
            self.start_talk(random.choice(RAGE_AIM_PHRASES))

    def _advance_attack(self, mouse, stats):
        """Tick the windup -> strike -> recovery timeline frame by frame."""
        self.vx = 0.0
        self.phase_timer -= 1
        if self.combat_phase == "windup":
            self.state = State.IDLE
            if self.phase_timer <= 0:
                self._do_strike(mouse, stats)
        elif self.combat_phase == "strike":
            if self.phase_timer <= 0:
                self.combat_phase = "recovery"
                self.phase_timer = stats["recovery"]
                self.phase_max = max(1, stats["recovery"])
        elif self.combat_phase == "recovery":
            if self.phase_timer <= 0:
                self.combat_phase = None
                self.attack_cooldown = stats["cooldown"]
                if self.hits_landed >= stats["hits_to_win"]:
                    self._begin_capture(mouse)

    def _do_strike(self, mouse, stats):
        """The blow lands: lunge in, draw the effect, and (if it connects) knock
        the cursor back and count the hit."""
        self.combat_phase = "strike"
        self.phase_timer = stats["strike"]
        self.phase_max = max(1, stats["strike"])
        sign = 1 if self.facing_right else -1
        center_x = self.x + WINDOW_W / 2
        center_y = self.y + WINDOW_H / 2

        # Dash in (blades lunge a lot, pistol not at all). Horizontal only so he
        # stays grounded.
        lunge = stats.get("lunge", 0)
        if lunge:
            self.x = max(self.min_x, min(self.max_x - WINDOW_W, self.x + sign * lunge))
            self._spawn_dust()
            center_x = self.x + WINDOW_W / 2

        aim = mouse if mouse is not None else self._aim
        if aim is None:
            return
        ang = math.atan2(aim[1] - center_y, aim[0] - center_x)
        reach = stats["range"] * 0.7
        tip_x = center_x + math.cos(ang) * reach
        tip_y = center_y + math.sin(ang) * reach

        if stats["ranged"]:
            self._fire_projectile(center_x, center_y, sign, aim)

        # Connect check against the (possibly lunged) pet centre.
        dist = math.hypot(aim[0] - center_x, aim[1] - center_y)
        if dist <= stats["range"] * 1.15:
            self.attack_landed = True
            self.hits_landed += 1
            fx_x, fx_y = (aim[0], aim[1]) if stats["ranged"] else (tip_x, tip_y)
            self._combat_fx(stats["effect"], fx_x, fx_y, sign)
            self._add_particle("hit", aim[0], aim[1], 0.0, -0.4, 16, grav=0.0)
            self._knockback_cursor(aim, center_x, center_y, stats["knockback"])
            if random.random() < 0.35:
                self.start_talk(random.choice(RAGE_CATCH_PHRASES))
        else:
            # A whiff: just a little dust off the swing.
            self._add_particle("dust", tip_x, tip_y + 4, sign * 0.6, -0.2, 12)

    def _fire_projectile(self, center_x, center_y, sign, aim):
        """Pistol shot: a muzzle flash and a bullet streaking toward the aim."""
        mux = center_x + sign * WINDOW_W * 0.42
        muy = center_y
        self._add_particle("spark", mux, muy, sign * 1.6, 0.0, 6, grav=0.0)
        bdx = aim[0] - mux
        bdy = aim[1] - muy
        bdist = max(1.0, math.hypot(bdx, bdy))
        speed = 16.0
        self._add_particle(
            "bullet", mux, muy, bdx / bdist * speed, bdy / bdist * speed,
            int(bdist / speed) + 2, grav=0.0,
        )

    def _knockback_cursor(self, aim, center_x, center_y, amount):
        """Shove the cursor away from the pet by `amount` px (clamped on-screen)."""
        if not amount:
            return
        kdx = aim[0] - center_x
        kdy = aim[1] - center_y
        kd = max(1.0, math.hypot(kdx, kdy))
        nx = max(self.min_x + 4, min(self.max_x - 4, aim[0] + kdx / kd * amount))
        ny = max(self.min_y + 4, min(self.max_y - 4, aim[1] + kdy / kd * amount))
        self.cursor_grab = (nx, ny)

    def _combat_fx(self, effect, x, y, sign):
        """Spawn the pixel hit effect for a weapon at the impact point."""
        if effect == "slash":
            self._add_particle("slash", x, y, sign * 0.6, -0.3, 9, grav=0.0,
                               flip=sign < 0)
            for _ in range(4):
                self._add_particle("spark", x, y, random.uniform(-2, 2) + sign,
                                   random.uniform(-2, 1), random.randint(8, 14),
                                   grav=0.12)
        elif effect == "stab":
            self._add_particle("slash", x, y, sign * 1.2, 0.0, 8, grav=0.0,
                               flip=sign < 0)
            for _ in range(3):
                self._add_particle("spark", x, y, sign * random.uniform(0.5, 2.5),
                                   random.uniform(-1, 1), random.randint(6, 12),
                                   grav=0.1)
        elif effect == "smash":
            self._add_particle("boom", x, y, 0.0, 0.0, 14, grav=0.0)
            for _ in range(6):
                self._add_particle("spark", x, y, random.uniform(-3, 3),
                                   random.uniform(-3, 0.5), random.randint(10, 18),
                                   grav=0.18)
            self._add_particle("dust", x - 4, y + 6, -1.2, -0.2, 18, grav=0.05)
            self._add_particle("dust", x + 4, y + 6, 1.2, -0.2, 18, grav=0.05)
        elif effect == "shot":
            self._add_particle("boom", x, y, 0.0, 0.0, 10, grav=0.0)
            for _ in range(4):
                self._add_particle("spark", x, y, random.uniform(-2, 2),
                                   random.uniform(-2, 2), random.randint(6, 12),
                                   grav=0.1)

    def _begin_capture(self, mouse):
        """Enough clean hits landed — pounce, pin the cursor, and celebrate."""
        aim = mouse if mouse is not None else self._aim
        self.capturing = True
        self.combat_phase = None
        if aim is not None:
            self.cursor_lock = (aim[0], aim[1])
        self.lock_timer = CAPTURE_LOCK_FRAMES
        self.spawn_particles("star", 5)
        self.spawn_particles("heart", 3)
        self.start_talk(random.choice(RAGE_LOCK_PHRASES))

    def _release_cursor(self):
        """End the pin: fling the pointer away and break into a victory dance."""
        self.cursor_lock = None
        span_y = self.max_y - self.min_y
        self.cursor_grab = (
            random.uniform(self.min_x + 40, self.max_x - 40),
            random.uniform(self.min_y + 40, self.min_y + span_y * 0.4),
        )
        self.spawn_particles("star", 6)
        self.start_talk(random.choice(RAGE_CATCH_PHRASES))
        self._calm_after_capture()
        self.victory = True
        self.victory_timer = VICTORY_DURATION

    def _calm_after_capture(self):
        """Revenge served — drop the weapon and cool right off."""
        self.rage = False
        self.rage_timer = 0
        self.weapon = None
        self.angry = False
        self.angry_timer = 0
        self.anger = 0.0
        self.capturing = False
        self._reset_combat()

    def _rage_jump(self, mouse, platforms):
        """Jump onto whichever reachable window edge gets him closest to the
        cursor (used while enraged to scale up toward it)."""
        if self.jump_cooldown > 0 or self.airborne or self.state == State.JUMP:
            return
        foot = self._feet_x()
        current_y = self.y + WINDOW_H
        best = None
        best_score = None
        for platform in platforms:
            if platform["name"] == GROUND_PLATFORM_NAME:
                continue
            vertical = platform["y"] - current_y
            if vertical > -20:
                continue  # not meaningfully higher than where he stands
            if vertical < -self.screen_h * MAX_TARGET_HEIGHT:
                continue  # too high to reach
            center = platform["x"] + platform["w"] * 0.5
            if abs(center - foot) > self.screen_w * MAX_TARGET_DISTANCE:
                continue  # too far sideways
            score = abs(center - mouse[0]) + abs(platform["y"] - mouse[1])
            if best_score is None or score < best_score:
                best_score = score
                best = platform
        if best:
            self.start_jump(best)

    def _maybe_follow_mouse(self, mouse):
        if self.angry or self.following:
            return
        if self.state not in (State.IDLE, State.WALK):
            return
        if abs(mouse[0] - self._feet_x()) < FOLLOW_STOP_DISTANCE * 2:
            return
        if random.random() > FOLLOW_CHANCE * self._trait("social"):
            return
        self.following = True
        self.follow_timer = random.randint(120, 300)

    def _update_follow(self, mouse):
        if mouse is None or self.airborne or self.angry:
            self.following = False
            return
        self.follow_timer -= 1
        dx = mouse[0] - self._feet_x()
        if abs(dx) < FOLLOW_STOP_DISTANCE or self.follow_timer <= 0:
            reached = abs(dx) < FOLLOW_STOP_DISTANCE + 4
            self.following = False
            self.vx = 0.0
            self.state = State.IDLE
            self.state_timer = random.randint(40, 90)
            if reached:
                self.spawn_particles("heart", 1)
            return
        direction = 1 if dx > 0 else -1
        speed = 2.4 if abs(dx) > FOLLOW_RUN_DISTANCE else 1.0
        self.vx = direction * speed
        self.state = State.RUN if speed > 1.6 else State.WALK
        self.state_timer = 30

    # -- Personality & social ---------------------------------------------

    def _trait(self, key):
        return self.personality.get(key, 1.0)

    def inherit_personality(self, a, b):
        """Blend two parents' temperaments (with a little mutation) for a bred
        child, taking a name from one of them."""
        self.personality = {
            trait: round(
                (a.get(trait, 1.0) + b.get(trait, 1.0)) / 2 * random.uniform(0.85, 1.15),
                2,
            )
            for trait in PERSONALITY_TRAITS
        }
        self.personality["name"] = random.choice(
            [a.get("name", "Calm"), b.get("name", "Calm")]
        )

    def observe_peers(self, peers):
        """Record the other pets' centres (x, y) for this frame's social check."""
        self._peers = peers

    def _maybe_socialize(self):
        """Occasionally wander to the nearest other pet to say hi. Skipped when
        busy or out of sorts; sociable temperaments do it far more often."""
        if self.socializing or not self._peers:
            return False
        if self.state not in (State.IDLE, State.WALK):
            return False
        if (
            self.angry or self.rage or self.scared or self.asleep
            or self.focusing or self.following
        ):
            return False
        if random.random() > SOCIAL_CHANCE * self._trait("social"):
            return False
        self.social_target_x = min(
            self._peers, key=lambda c: abs(c[0] - self._feet_x())
        )[0]
        self.socializing = True
        self.social_timer = random.randint(180, 420)
        return True

    def _update_social(self):
        """Walk toward the nearest peer; greet on arrival, then drift off."""
        self.social_timer -= 1
        if self._peers:
            self.social_target_x = min(
                self._peers, key=lambda c: abs(c[0] - self._feet_x())
            )[0]
        dx = self.social_target_x - self._feet_x()
        if abs(dx) < SOCIAL_REACH or self.social_timer <= 0:
            reached = abs(dx) < SOCIAL_REACH
            self.socializing = False
            self.vx = 0.0
            self.state = State.IDLE
            self.state_timer = random.randint(40, 90)
            if reached:
                self._greet()
            return
        direction = 1 if dx > 0 else -1
        self.vx = direction * 1.6 * self._trait("speed")
        self.facing_right = direction > 0
        self.state = State.WALK
        self.state_timer = 20

    def _greet(self):
        """Trade a little affection with a nearby pet; playful ones hop."""
        self.spawn_particles("heart", random.randint(1, 3))
        self.love = min(LOVE_MAX, self.love + SOCIAL_GREET_LOVE)
        if self.love >= LOVE_THRESHOLD:
            self.loved = True
            self.loved_timer = LOVE_DURATION
        if self._trait("play") > 1.3 and self.jump_cooldown == 0 and not self.airborne:
            self.start_jump()

    # -- Breeding (courtship & growing up) ---------------------------------

    def make_baby(self, parent_a, parent_b):
        """Turn this freshly-spawned pet into parent_a & parent_b's child:
        inherit a blended temperament, one parent's colours, a name (sometimes a
        'Jr' of a parent's), and a weapon taste — then start tiny and grow up."""
        self.inherit_personality(parent_a.personality, parent_b.personality)
        # Colour: take after one parent.
        source = random.choice([parent_a, parent_b])
        self.palette_index = source.palette_index
        self.palette = source.palette
        # Name: half the time a parent's name with a 'Jr', else a fresh one.
        if random.random() < 0.5:
            self.name = random.choice([parent_a.name, parent_b.name]) + BABY_NAME_SUFFIX
        else:
            self.name = random.choice(PET_NAMES)
        # Weapon taste leans on the parents'.
        self.weapon_pref = random.choice(
            [parent_a.weapon_pref, parent_b.weapon_pref]
        )
        self.baby = True
        self.growth = 0.0
        self.spawn_particles("heart", 4)
        self.start_talk(random.choice(BABY_PHRASES))

    def court_to(self, target_x):
        """Waddle toward a meeting point to breed (set by the breeding manager)."""
        if self.rage or self.scared or self.asleep or self.airborne or self.dying:
            return
        self.courting = True
        self.court_target_x = float(target_x)
        self.court_timer = 0
        self.court_arrived = False
        self.following = False
        self.socializing = False
        if self.talking:
            self._stop_talking(repick=False)

    def stop_courting(self):
        self.courting = False
        self.court_arrived = False

    def _update_court(self):
        """Walk toward the rendezvous, trailing hearts; settle once there."""
        self.court_timer += 1
        dx = self.court_target_x - self._feet_x()
        if abs(dx) <= COURT_REACH:
            self.court_arrived = True
            self.vx = 0.0
            self.state = State.IDLE
            self.facing_right = dx >= 0
            if random.random() < COURT_HEART_CHANCE:
                self.spawn_particles("heart", 1)
            return
        direction = 1 if dx > 0 else -1
        self.vx = direction * COURT_SPEED * self._trait("speed")
        self.facing_right = direction > 0
        self.state = State.WALK
        self.state_timer = 20
        if random.random() < COURT_HEART_CHANCE * 0.5:
            self.spawn_particles("heart", 1)

    def _update_growth(self):
        """Grow a baby up to full size, sparkling once it finishes."""
        if not self.baby:
            return
        self.growth = min(1.0, self.growth + BABY_GROW_RATE)
        if self.growth >= 1.0:
            self.baby = False
            self.spawn_particles("star", 4)
            self.start_talk("All grown up!")

    # -- Removal (death animation) ----------------------------------------

    def start_death(self, kind=None):
        """Begin a short send-off animation; the main loop culls the pet once
        death_timer runs out (self.dead). A no-op if already on the way out."""
        if self.dying:
            return
        self.dying = True
        self.dead = False
        self.death_kind = kind or random.choice(DEATH_KINDS)
        self.death_timer = DEATH_FRAMES
        self.death_max = DEATH_FRAMES
        # Stop everything else cleanly.
        self.rage = False
        self.weapon = None
        self.cursor_lock = None
        self.capturing = False
        self.lock_timer = 0
        self.following = False
        self.socializing = False
        self.courting = False
        if self.talking:
            self._stop_talking(repick=False)
        cx = self.x + WINDOW_W / 2
        cy = self.y + WINDOW_H / 2
        if self.death_kind == "poof":
            for _ in range(6):
                self._add_particle("poof", cx + random.uniform(-10, 10),
                                   cy + random.uniform(-8, 8),
                                   random.uniform(-1.2, 1.2), random.uniform(-1.4, -0.2),
                                   random.randint(20, 32), grav=0.02)
        elif self.death_kind == "explosion":
            self._add_particle("boom", cx, cy, 0.0, 0.0, 18, grav=0.0)
            for _ in range(10):
                self._add_particle("spark", cx, cy, random.uniform(-4, 4),
                                   random.uniform(-4, 1), random.randint(12, 22),
                                   grav=0.15)
            self.spawn_particles("anger", 3)
        elif self.death_kind == "ghost":
            self._add_particle("ghost", cx, cy, 0.0, -0.8, DEATH_FRAMES, grav=0.0)
        elif self.death_kind == "fall":
            self.spin_speed = random.choice([-1, 1]) * random.uniform(8, 14)
            self.jump_vy = -2.0
            self._spawn_dust()

    def _update_death(self):
        """Advance the send-off; spawn its trailing particles and mark dead."""
        self.death_timer -= 1
        k = self.death_kind
        cx = self.x + WINDOW_W / 2
        cy = self.y + WINDOW_H / 2
        if k == "poof":
            if self.death_timer % 4 == 0:
                self._add_particle("poof", cx + random.uniform(-8, 8),
                                   cy + random.uniform(-6, 6),
                                   random.uniform(-0.8, 0.8), random.uniform(-1.0, -0.2),
                                   random.randint(16, 26), grav=0.02)
        elif k == "explosion":
            if self.death_timer % 5 == 0:
                self._add_particle("spark", cx, cy, random.uniform(-3, 3),
                                   random.uniform(-3, 0.5), random.randint(10, 18),
                                   grav=0.15)
        elif k == "ghost":
            self.y -= 1.3  # float upward as a little ghost
        elif k == "fall":
            self.angle += self.spin_speed
            self.jump_vy += GRAVITY
            self.y += self.jump_vy
        if self.death_timer <= 0:
            self.dead = True

    def pick_state(self):
        if self.focusing and not self.rage:
            # Heads-down: mostly sit and work, with the occasional short shuffle.
            if random.random() < 0.8:
                self.state = State.IDLE
                self.vx = 0.0
                self.vy = 0.0
                self.state_timer = random.randint(180, 360)
            else:
                self.state = State.WALK
                self.vx = random.choice([-1, 1]) * random.uniform(0.3, 0.7)
                self.vy = random.uniform(-0.1, 0.1)
                self.state_timer = random.randint(60, 140)
            return
        # Temperament shifts the odds: lazy pets idle more, hyper ones run and
        # jump more, etc. Speed scales how fast he moves.
        idle_w = self._trait("idle")
        jump_w = self._trait("jump")
        speed_mult = self._trait("speed")
        weights = (
            ("walk", 0.50),
            ("idle", 0.32 * idle_w),
            ("run", 0.16 / idle_w),
            ("jump", (RANDOM_JUMP_STATE_CHANCE + 0.05) * jump_w),
        )
        roll = random.random() * sum(w for _, w in weights)
        acc = 0.0
        choice = weights[-1][0]
        for kind, w in weights:
            acc += w
            if roll <= acc:
                choice = kind
                break

        if choice == "walk":
            self.state = State.WALK
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * random.uniform(0.35, 1.05) * speed_mult
            self.vy = random.uniform(-0.12, 0.12)
            self.state_timer = random.randint(160, 420)
        elif choice == "idle":
            self.state = State.IDLE
            self.vx = 0.0
            self.vy = 0.0
            self.state_timer = random.randint(120, 360)
        elif choice == "run":
            self.state = State.RUN
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * random.uniform(1.8, 3.0) * speed_mult
            self.vy = random.uniform(-0.18, 0.18)
            self.state_timer = random.randint(30, 75)
        else:  # jump
            if self.jump_cooldown > 0:
                self.state = State.WALK
                self.vx = random.choice([-1, 1]) * random.uniform(0.35, 1.05) * speed_mult
                self.vy = random.uniform(-0.12, 0.12)
                self.state_timer = random.randint(120, 260)
            else:
                self.state = State.JUMP
                self.start_jump()

    def start_jump(self, target=None):
        self.state = State.JUMP
        self.airborne = True
        self.jump_target = target
        self.jump_vy = -random.uniform(NORMAL_JUMP_POWER_MIN, NORMAL_JUMP_POWER_MAX)
        if target:
            target_center = target["x"] + target["w"] * 0.5
            pet_center = self.x + WINDOW_W * 0.5
            target_feet_y = target["y"]
            current_feet_y = self.y + WINDOW_H
            rise = max(0, current_feet_y - target_feet_y)
            distance = target_center - pet_center
            clearance = TARGET_JUMP_EXTRA_HEIGHT
            self.jump_vy = -min(
                MAX_TARGET_JUMP_POWER,
                max(TARGET_JUMP_POWER_MIN, math.sqrt(2 * GRAVITY * (rise + clearance))),
            )
            airtime = max(34, (abs(self.jump_vy) * 2) / GRAVITY)
            self.vx = max(
                -MAX_TARGET_JUMP_SPEED_X,
                min(MAX_TARGET_JUMP_SPEED_X, distance / airtime),
            )
        elif abs(self.vx) < 0.3:
            self.vx = random.uniform(-2.5, 2.5)
        self.vy = 0.0
        self.state_timer = 240

    def update(self, platforms, mouse=None, ball=None):
        self.frame += 1
        self.state_timer -= 1
        self.jump_cooldown = max(0, self.jump_cooldown - 1)
        self.speech_cooldown = max(0, self.speech_cooldown - 1)
        self._update_face()
        self._update_particles()

        # On the way out: play the send-off and nothing else.
        if self.dying:
            self._update_death()
            return

        self._update_growth()
        self._update_mood()

        # Victory lap after a successful capture: bounce and sparkle for a beat
        # while otherwise behaving normally (he's calmed down by now).
        if self.victory:
            self.victory_timer -= 1
            if self.victory_timer % 12 == 0:
                self.spawn_particles(random.choice(["star", "heart"]), 1)
            if (
                self.victory_timer % 24 == 0
                and self.jump_cooldown == 0
                and not self.airborne
                and self.state in (State.IDLE, State.WALK)
            ):
                self.start_jump()
            if self.victory_timer <= 0:
                self.victory = False

        # A pinned cursor counts down and releases on its own, independent of
        # mood — so it can never get stuck held (e.g. if rage lapses mid-pin).
        # While pinned he gleefully bounces on his catch and showers it in stars.
        if self.lock_timer > 0:
            self.vx = 0.0
            self.state = State.IDLE
            self.lock_timer -= 1
            if self.lock_timer % 6 == 0:
                self.spawn_particles(random.choice(["star", "heart", "anger"]), 1)
            if self.lock_timer <= 0:
                self._release_cursor()
            return

        if self.tumbling:
            self._update_tumble(platforms)
            return
        if self.righting:
            self._update_righting(platforms)
            return
        if self.asleep:
            self._update_sleep(platforms)
            return

        self._maybe_idle_fx()
        self._activity_fx()

        if self.rage:
            # Armed and in combat: position for the weapon and run the attack
            # timeline, but keep the bubble counting down so it never roots him.
            if self.talking:
                self.speech_timer -= 1
                if self.speech_timer <= 0:
                    self._stop_talking(repick=False)
            self._update_combat(mouse, platforms)
        else:
            if self.talking and self._update_talking():
                return

            if not self.talking and not self.airborne and self.state != State.JUMP:
                self._maybe_talk()
                if self.talking:
                    return

            self._energy_fx()

            grounded = not self.airborne and self.state != State.JUMP
            if self.scared:
                # Spooked: tremble in place; no chasing, fetching, or wandering.
                if grounded:
                    self._update_scared(mouse)
            elif self.courting and grounded:
                # Courtship: waddle to the rendezvous and wait there for a mate.
                self._update_court()
            elif self.focusing:
                # Heads-down: stays put (pick_state keeps him calm).
                pass
            elif ball is not None and grounded and self._wants_to_play(ball):
                self._update_fetch(ball)
            elif self.curious and grounded and mouse is not None:
                self._update_curious(mouse)
            else:
                if self.socializing:
                    self._update_social()
                elif self.following:
                    self._update_follow(mouse)
                elif grounded and self._maybe_socialize():
                    pass
                elif mouse is not None and grounded:
                    self._maybe_follow_mouse(mouse)

                if (
                    not self.following
                    and not self.socializing
                    and not self.courting
                    and grounded
                ):
                    if not self._maybe_drop_through_platform():
                        self._maybe_jump_to_window(platforms)

        if self.airborne or self.state == State.JUMP:
            self.jump_vy += GRAVITY
            self.y += self.jump_vy
            self.x += self.vx
            self._land_if_possible(platforms)
        else:
            # On a window ledge, turn back at the edge instead of teetering off
            # it (which made him jitter and snag in window corners). Ground and
            # deliberate exits (rage, following, drop-through, jumps) are exempt.
            if (
                self.platform is not None
                and self.platform["name"] != GROUND_PLATFORM_NAME
                and not self.rage
                and not self.following
            ):
                self._halt_at_ledge_edge()
            self.x += self.vx
            if self.platform and self._feet_inside_platform(self.platform):
                self.y = self.platform["y"] - WINDOW_H
            else:
                self.airborne = True
                self.state = State.JUMP
                self.jump_vy = 0.0

        if self.vx > 0.1:
            self.facing_right = True
        elif self.vx < -0.1:
            self.facing_right = False

        if self.x < self.min_x:
            self.x = self.min_x
            self.vx = abs(self.vx)
            self.facing_right = True
        elif self.x + WINDOW_W > self.max_x:
            self.x = self.max_x - WINDOW_W
            self.vx = -abs(self.vx)
            self.facing_right = False

        if self.y + WINDOW_H > self.max_y:
            self.y = self.max_y - WINDOW_H
            self.airborne = False
            self.platform = self._ground_under_feet(platforms)
            if self.state == State.JUMP:
                self.jump_cooldown = 30
                if not self.rage:
                    self.pick_state()

        if self.state_timer <= 0 and not self.airborne and not self.rage:
            self.pick_state()

    def _update_face(self):
        self.blink_timer -= 1
        if self.blink_timer <= 0:
            if self.blink:
                self.blink = False
                self.blink_timer = random.randint(100, 260)
            else:
                self.blink = True
                self.blink_timer = random.randint(5, 9)

        self.look_timer -= 1
        if self.look_timer <= 0:
            self.look_offset = random.choice([-1, 0, 1])
            self.look_timer = random.randint(45, 160)

    def place_on_best_platform(self, platforms):
        current = self._matching_platform(platforms, self.platform)
        if current and self._feet_inside_platform(current):
            self.platform = current
            self.y = current["y"] - WINDOW_H
            self.airborne = False
            return

        below = [
            platform
            for platform in platforms
            if self._feet_x() >= platform["x"]
            and self._feet_x() <= platform["x"] + platform["w"]
            and platform["y"] >= self.y + WINDOW_H - 4
        ]
        self.platform = min(below, key=lambda item: item["y"], default=platforms[0])
        self.y = self.platform["y"] - WINDOW_H
        self.airborne = False

    def sync_platforms(self, platforms):
        current = self._matching_platform(platforms, self.platform)
        if current and self._feet_inside_platform(current):
            self.platform = current
            self.y = current["y"] - WINDOW_H
            return

        self.platform = None
        self.airborne = True
        self.state = State.JUMP
        self.jump_target = None
        self.jump_vy = max(0.0, self.jump_vy)

    def drag_to(self, x, y):
        nx, ny = float(x), float(y)
        # Track how fast he's being dragged so a flick on release becomes a throw,
        # and watch for a rapid back-and-forth shake, which frightens him.
        if self._shake_decay > 0:
            self._shake_decay -= 1
            if self._shake_decay == 0:
                self._shake_count = 0
                self._shake_dir = 0
        if self._drag_prev is not None:
            dx = nx - self._drag_prev[0]
            self._throw_vx = dx
            self._throw_vy = ny - self._drag_prev[1]
            if abs(dx) >= SHAKE_SPEED:
                sign = 1 if dx > 0 else -1
                if self._shake_dir and sign != self._shake_dir:
                    self._shake_count += 1
                    self._shake_decay = SHAKE_WINDOW
                self._shake_dir = sign
            if self._shake_count >= SHAKE_REVERSALS and not self.scared:
                self._become_scared()
                self._shake_count = 0
                self._shake_decay = 0
        self._drag_prev = (nx, ny)
        self.x = nx
        self.y = ny
        self.vx = 0.0
        self.vy = 0.0
        self.jump_vy = 0.0
        self.airborne = False
        self.platform = None
        self.jump_target = None
        self.tumbling = False
        self.righting = False
        self.angle = 0.0
        self.spin_speed = 0.0
        self.right_vel = 0.0
        self.state = State.IDLE
        self.state_timer = 60
        self.following = False
        self.courting = False
        self.court_arrived = False
        if self.talking:
            self._stop_talking(repick=False)

    def release(self):
        """Let go after a drag. A fast flick launches him into a tumbling throw;
        a gentle let-go just drops him so gravity takes over."""
        vx, vy = self._throw_vx, self._throw_vy
        self._drag_prev = None
        self._throw_vx = 0.0
        self._throw_vy = 0.0
        if math.hypot(vx, vy) >= THROW_MIN_SPEED:
            self.vx = max(-THROW_MAX_SPEED, min(THROW_MAX_SPEED, vx))
            self.jump_vy = max(-THROW_MAX_SPEED, min(THROW_MAX_SPEED, vy))
            self.spin_speed = -self.vx * TUMBLE_SPIN_SCALE
            self.tumbling = True
            self.airborne = True
            self.platform = None
            self.jump_target = None
            self.state = State.JUMP
            self.following = False
        else:
            self.drop()

    def drop(self):
        self.airborne = True
        self.platform = None
        self.jump_target = None
        self.tumbling = False
        self.righting = False
        self.angle = 0.0
        self.state = State.JUMP
        self.jump_vy = 0.0
        self.jump_cooldown = 30
        self.following = False

    def _update_tumble(self, platforms):
        """Ballistic tumble: arc under gravity, spin, and bounce off walls,
        windows, and the floor with damping until the motion dies and he stands."""
        self.jump_vy += GRAVITY
        self.x += self.vx
        self.y += self.jump_vy
        self.vx *= THROW_AIR_FRICTION
        self.angle += self.spin_speed
        self.spin_speed *= 0.99

        # Side walls: reflect and lose a little energy.
        if self.x < self.min_x:
            self.x = self.min_x
            self.vx = abs(self.vx) * THROW_RESTITUTION
            self.spin_speed = -self.spin_speed * 0.6
            self._spawn_dust()
        elif self.x + WINDOW_W > self.max_x:
            self.x = self.max_x - WINDOW_W
            self.vx = -abs(self.vx) * THROW_RESTITUTION
            self.spin_speed = -self.spin_speed * 0.6
            self._spawn_dust()

        if self.vx > 0.1:
            self.facing_right = True
        elif self.vx < -0.1:
            self.facing_right = False

        # Floor / window tops: only while descending, so he can arc up freely.
        if self.jump_vy > 0:
            platform = self._landing_platform(platforms)
            if platform is None and self.y + WINDOW_H > self.max_y:
                platform = self._ground_under_feet(platforms)
            if platform:
                self.y = platform["y"] - WINDOW_H
                self.jump_vy = -self.jump_vy * THROW_RESTITUTION
                self.vx *= THROW_FRICTION
                self.spin_speed *= 0.5
                self._spawn_dust()
                if (
                    abs(self.jump_vy) < THROW_REST_SPEED
                    and abs(self.vx) < THROW_REST_SPEED
                ):
                    # Out of bounce energy. He may be lying on his side or back,
                    # so hand off to the righting spring rather than snapping up.
                    self.tumbling = False
                    self.righting = True
                    self.angle = ((self.angle + 180) % 360) - 180
                    self.right_vel = self.spin_speed * 0.5
                    self.spin_speed = 0.0
                    self.vx = 0.0
                    self.jump_vy = 0.0
                    self.platform = platform
                    self.airborne = False
                    self.jump_cooldown = 20

    def _update_righting(self, platforms):
        """Ease him from however he landed back onto his feet with a damped
        wobble, instead of flipping upright in a single frame."""
        if self.platform and self._feet_inside_platform(self.platform):
            self.y = self.platform["y"] - WINDOW_H
        self.right_vel += -RIGHT_STIFFNESS * self.angle
        self.right_vel *= RIGHT_DAMPING
        self.angle += self.right_vel
        if abs(self.angle) < RIGHT_SETTLE and abs(self.right_vel) < RIGHT_SETTLE:
            self.angle = 0.0
            self.right_vel = 0.0
            self.righting = False
            self.pick_state()

    def _spawn_dust(self):
        self.spawn_particles("dust", random.randint(2, 3))

    def _maybe_drop_through_platform(self):
        if self.jump_cooldown > 0:
            return False
        if self.state not in (State.IDLE, State.WALK):
            return False
        if not self.platform or self.platform["name"] == GROUND_PLATFORM_NAME:
            return False
        if random.random() > PLATFORM_DROP_CHANCE:
            return False

        direction = 1 if self.facing_right else -1
        if abs(self.vx) < 0.2:
            self.vx = direction * random.uniform(0.25, 0.8)
        self.y += 3
        self.airborne = True
        self.platform = None
        self.jump_target = None
        self.state = State.JUMP
        self.jump_vy = 1.2
        self.jump_cooldown = 45
        return True

    def _matching_platform(self, platforms, platform):
        if not platform:
            return None
        for candidate in platforms:
            if candidate.get("id") == platform.get("id"):
                return candidate
        for candidate in platforms:
            if candidate.get("base_id") == platform.get("base_id"):
                if self._feet_inside_platform(candidate):
                    return candidate
        return None

    def _ground_under_feet(self, platforms):
        foot = self._feet_x()
        grounds = [
            platform
            for platform in platforms
            if platform["name"] == GROUND_PLATFORM_NAME
            and platform["x"] <= foot <= platform["x"] + platform["w"]
        ]
        if grounds:
            return min(grounds, key=lambda item: item["y"])
        return platforms[0] if platforms else None

    def _feet_x(self):
        return self.x + WINDOW_W * 0.5

    def _feet_inside_platform(self, platform):
        foot = self._feet_x()
        return (
            platform["x"] + PLATFORM_EDGE_MARGIN
            <= foot
            <= platform["x"] + platform["w"] - PLATFORM_EDGE_MARGIN
        )

    def _halt_at_ledge_edge(self):
        """Stop right at the ledge edge instead of teetering off it: clamp to the
        edge and stand still for a beat (no turning around, no sliding away). He
        leaves a window only deliberately — via drop-through or a jump. No-op on
        ledges too narrow to stand on, where normal falling takes over."""
        platform = self.platform
        left = platform["x"] + PLATFORM_EDGE_MARGIN
        right = platform["x"] + platform["w"] - PLATFORM_EDGE_MARGIN
        if right <= left:
            return
        next_foot = self._feet_x() + self.vx
        at_edge = False
        if next_foot < left:
            self.x = left - WINDOW_W * 0.5
            at_edge = True
        elif next_foot > right:
            self.x = right - WINDOW_W * 0.5
            at_edge = True
        if at_edge:
            self.vx = 0.0
            if self.state in (State.WALK, State.RUN):
                self.state = State.IDLE
                self.state_timer = random.randint(60, 150)

    def _landing_platform(self, platforms):
        previous_feet_y = self.y + WINDOW_H - self.jump_vy
        feet_y = self.y + WINDOW_H
        foot_x = self._feet_x()
        candidates = []
        for platform in platforms:
            if not (platform["x"] <= foot_x <= platform["x"] + platform["w"]):
                continue
            if previous_feet_y <= platform["y"] <= feet_y:
                candidates.append(platform)
        return min(candidates, key=lambda item: item["y"], default=None)

    def _land_if_possible(self, platforms):
        if self.jump_vy < 0:
            return
        platform = self._landing_platform(platforms)
        if not platform:
            return
        self.platform = platform
        self.y = platform["y"] - WINDOW_H
        self.airborne = False
        self.jump_target = None
        self.jump_cooldown = 30
        if self.rage:
            self.state = State.IDLE
        else:
            self.pick_state()

    def _maybe_jump_to_window(self, platforms):
        if self.jump_cooldown > 0:
            return
        if self.state not in (State.IDLE, State.WALK):
            return
        if random.random() > WINDOW_JUMP_CHANCE:
            return

        foot = self._feet_x()
        current_y = self.y + WINDOW_H
        candidates = []
        for platform in platforms:
            if platform.get("id") == (self.platform or {}).get("id"):
                continue
            if platform.get("base_id") == (self.platform or {}).get("base_id"):
                continue
            if platform["name"] == GROUND_PLATFORM_NAME:
                continue
            center = platform["x"] + platform["w"] * 0.5
            distance = abs(center - foot)
            vertical = platform["y"] - current_y
            if (
                distance < self.screen_w * MAX_TARGET_DISTANCE
                and -self.screen_h * MAX_TARGET_HEIGHT < vertical < 260
            ):
                candidates.append(platform)

        if candidates:
            candidates.sort(
                key=lambda platform: (
                    platform["y"],
                    abs((platform["x"] + platform["w"] * 0.5) - foot),
                )
            )
            self.start_jump(random.choice(candidates[:3]))
