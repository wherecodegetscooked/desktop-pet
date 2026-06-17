"""The pet's behaviour model: state machine, physics, and reactions.

`Pet` is pure logic — it owns position, velocity, the current animation state,
talking/anger/particle bookkeeping, and the platform-jumping AI. It holds no
windowing or drawing code; the overlay renders whatever the pet's fields say.
"""

import math
import random

from config import (
    AFK_SLEEP_SECONDS,
    ANGER_DECAY,
    ANGRY_DURATION,
    ANGRY_PHRASES,
    ANGRY_THRESHOLD,
    BORED_FRAMES,
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
    PET_STROKE_CALM,
    PET_STROKE_LOVE,
    PHRASES,
    PLATFORM_DROP_CHANCE,
    PLATFORM_EDGE_MARGIN,
    RAGE_CHASE_SPEED,
    RAGE_DURATION,
    RAGE_PHRASES,
    RAGE_THRESHOLD,
    RANDOM_JUMP_STATE_CHANCE,
    RIGHT_DAMPING,
    RIGHT_SETTLE,
    RIGHT_STIFFNESS,
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
        # Violence: once anger boils over he arms himself and chases the cursor.
        self.rage = False
        self.rage_timer = 0
        self.weapon = None
        # Affection: slow strokes make him fall in love.
        self.love = 0.0
        self.loved = False
        self.loved_timer = 0
        self._last_cursor_x = None
        self._stroke_dir = 0
        # Breeding: spawned children carry a lifespan (frames); adults stay None.
        self.life = None
        # Activity-driven energy: sleep when the machine is idle, get excited
        # when the human types fast, bored when present but not typing.
        self.asleep = False
        self.excited = False
        self.bored = False
        self.idle_seconds = 0.0
        self.typing_rate = 0.0
        self.excited_hold = 0
        # Start as if he was just active, so he wakes up neutral rather than
        # immediately bored on launch.
        self.frames_since_key = 0
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
        self.pick_state()

    @property
    def mood(self):
        if self.rage:
            return "rage"
        if self.angry:
            return "angry"
        if self.asleep:
            return "asleep"
        if self.loved:
            return "love"
        if self.excited:
            return "excited"
        if self.bored:
            return "bored"
        return "neutral"

    def _phrase_pool(self):
        if self.rage:
            return RAGE_PHRASES
        if self.angry:
            return ANGRY_PHRASES
        if self.loved:
            return LOVE_PHRASES
        if self.excited:
            return EXCITED_PHRASES
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

    def _update_particles(self):
        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.02
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
        if keys > 0:
            self.frames_since_key = 0
        else:
            self.frames_since_key += 1
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

        self.bored = (
            not self.excited
            and calm
            and idle_seconds < AFK_SLEEP_SECONDS
            and self.frames_since_key >= BORED_FRAMES
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
        self.anger += clicks
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
        """Boil over: arm himself and go after whoever is poking him."""
        self.rage = True
        self.angry = True
        self.angry_timer = ANGRY_DURATION
        self.rage_timer = RAGE_DURATION
        self.weapon = random.choice(WEAPONS)
        self.following = False
        self.loved = False
        self.love = 0.0
        self.spawn_particles("anger", 8)
        self.start_talk(random.choice(RAGE_PHRASES))

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
            if self.rage_timer <= 0 and self.anger < 1.0:
                self.rage = False
                self.weapon = None
        if self.angry:
            self.angry_timer -= 1
            if self.angry_timer <= 0 and self.anger < 1.0 and not self.rage:
                self.angry = False
        if self.loved:
            self.loved_timer -= 1
            if self.loved_timer <= 0 and self.love < 1.0:
                self.loved = False

    def _update_rage(self, mouse, platforms):
        """Aggressively pursue the cursor on foot: run toward it, jump up onto
        windows to climb toward it, and walk off ledges to drop down to it.
        Respects gravity and platforms — he never flies straight at it."""
        if mouse is None:
            return
        if self.airborne or self.state == State.JUMP:
            return  # let the current jump arc finish
        dx = mouse[0] - self._feet_x()
        if abs(dx) > 8:
            self.vx = (1 if dx > 0 else -1) * RAGE_CHASE_SPEED
            self.state = State.RUN
        else:
            self.vx = 0.0
            self.state = State.IDLE
            if random.random() < 0.2:
                self.spawn_particles("anger", 1)
        if self.vx > 0.1:
            self.facing_right = True
        elif self.vx < -0.1:
            self.facing_right = False
        self.state_timer = 30
        # Climb toward the cursor when it's above him, hopping window to window.
        if mouse[1] < self.y + WINDOW_H - 40:
            self._rage_jump(mouse, platforms)

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
        if random.random() > FOLLOW_CHANCE:
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
        r = random.random()
        if r < 0.50:
            self.state = State.WALK
            speed = random.uniform(0.35, 1.05)
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * speed
            self.vy = random.uniform(-0.12, 0.12)
            self.state_timer = random.randint(160, 420)
        elif r < 0.90:
            self.state = State.IDLE
            self.vx = 0.0
            self.vy = 0.0
            self.state_timer = random.randint(120, 360)
        elif r < 1.0 - RANDOM_JUMP_STATE_CHANCE:
            self.state = State.RUN
            speed = random.uniform(1.8, 3.0)
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * speed
            self.vy = random.uniform(-0.18, 0.18)
            self.state_timer = random.randint(30, 75)
        else:
            if self.jump_cooldown > 0:
                self.state = State.WALK
                self.vx = random.choice([-1, 1]) * random.uniform(0.35, 1.05)
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

    def update(self, platforms, mouse=None):
        self.frame += 1
        self.state_timer -= 1
        self.jump_cooldown = max(0, self.jump_cooldown - 1)
        self.speech_cooldown = max(0, self.speech_cooldown - 1)
        self._update_face()
        self._update_particles()
        self._update_mood()

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

        if self.rage:
            # Armed and furious: chase the cursor on foot (jumping across
            # windows), but keep the bubble counting down so it never roots him.
            if self.talking:
                self.speech_timer -= 1
                if self.speech_timer <= 0:
                    self._stop_talking(repick=False)
            self._update_rage(mouse, platforms)
        else:
            if self.talking and self._update_talking():
                return

            if not self.talking and not self.airborne and self.state != State.JUMP:
                self._maybe_talk()
                if self.talking:
                    return

            self._energy_fx()

            # While focusing he stays put: no cursor-chasing, window hops, or
            # ledge drops. Excited bounces are likewise suppressed in _energy_fx.
            if not self.focusing:
                if self.following:
                    self._update_follow(mouse)
                elif mouse is not None and not self.airborne and self.state != State.JUMP:
                    self._maybe_follow_mouse(mouse)

                if not self.following and not self.airborne and self.state != State.JUMP:
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
        # Track how fast he's being dragged so a flick on release becomes a throw.
        if self._drag_prev is not None:
            self._throw_vx = nx - self._drag_prev[0]
            self._throw_vy = ny - self._drag_prev[1]
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
