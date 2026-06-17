"""The pet's behaviour model: state machine, physics, and reactions.

`Pet` is pure logic — it owns position, velocity, the current animation state,
talking/anger/particle bookkeeping, and the platform-jumping AI. It holds no
windowing or drawing code; the overlay renders whatever the pet's fields say.
"""

import math
import random

from config import (
    ANGER_DECAY,
    ANGRY_DURATION,
    ANGRY_PHRASES,
    ANGRY_THRESHOLD,
    FOLLOW_CHANCE,
    FOLLOW_RUN_DISTANCE,
    FOLLOW_STOP_DISTANCE,
    GRAVITY,
    GROUND_PLATFORM_NAME,
    IDLE_FX_MAX,
    IDLE_FX_MIN,
    MAX_PARTICLES,
    MAX_TARGET_DISTANCE,
    MAX_TARGET_HEIGHT,
    MAX_TARGET_JUMP_POWER,
    MAX_TARGET_JUMP_SPEED_X,
    NORMAL_JUMP_POWER_MAX,
    NORMAL_JUMP_POWER_MIN,
    PHRASES,
    PLATFORM_DROP_CHANCE,
    RANDOM_JUMP_STATE_CHANCE,
    SPEAK_CHANCE,
    SPEAK_COOLDOWN_MAX,
    SPEAK_COOLDOWN_MIN,
    SPEECH_MIN_FRAMES,
    SPEECH_PER_CHAR,
    TARGET_JUMP_EXTRA_HEIGHT,
    TARGET_JUMP_POWER_MIN,
    WINDOW_H,
    WINDOW_JUMP_CHANCE,
    WINDOW_W,
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
        self.pick_state()

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
        self.start_talk(random.choice(PHRASES))

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
            life = random.randint(42, 66)
            self.particles.append(
                {
                    "kind": kind,
                    "x": head_x + random.uniform(-9, 9),
                    "y": self.y + random.uniform(-3, 7),
                    "vx": random.uniform(-0.7, 0.7),
                    "vy": random.uniform(-1.8, -0.9),
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

    # -- Mouse interaction -------------------------------------------------

    def on_click(self, clicks, mouse=None):
        """React to taps: hearts when calm, anger after a few quick pokes."""
        for _ in range(clicks):
            if self.angry:
                self.spawn_particles("anger", random.randint(2, 3))
            else:
                self.spawn_particles("heart", random.randint(1, 2))
        self.anger += clicks
        if not self.angry and self.anger >= ANGRY_THRESHOLD:
            self._become_angry()

    def _become_angry(self):
        self.angry = True
        self.angry_timer = ANGRY_DURATION
        self.following = False
        self.spawn_particles("anger", 5)
        self.start_talk(random.choice(ANGRY_PHRASES))

    def _update_anger(self):
        self.anger = max(0.0, self.anger - ANGER_DECAY)
        if self.angry:
            self.angry_timer -= 1
            if self.angry_timer <= 0 and self.anger < 1.0:
                self.angry = False

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
        self._update_anger()
        self._maybe_idle_fx()

        if self.talking and self._update_talking():
            return

        if not self.talking and not self.airborne and self.state != State.JUMP:
            self._maybe_talk()
            if self.talking:
                return

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
                self.pick_state()

        if self.state_timer <= 0 and not self.airborne:
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
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.jump_vy = 0.0
        self.airborne = False
        self.platform = None
        self.jump_target = None
        self.state = State.IDLE
        self.state_timer = 60
        self.following = False
        if self.talking:
            self._stop_talking(repick=False)

    def drop(self):
        self.airborne = True
        self.platform = None
        self.jump_target = None
        self.state = State.JUMP
        self.jump_vy = 0.0
        self.jump_cooldown = 30
        self.following = False

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
        return platform["x"] + 8 <= foot <= platform["x"] + platform["w"] - 8

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
