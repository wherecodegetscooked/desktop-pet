"""The fetch ball: a simple bouncy physics object the pets chase and bat around.

`Ball` is pure logic like `Pet` — it owns a centre position and velocity and
falls under gravity, bouncing off the floor, walls, and window tops and rolling
to a rest. The overlay renders it; the pets read its position to play fetch.
"""

from config import (
    BALL_AIR_FRICTION,
    BALL_BASE_R,
    BALL_FRICTION,
    BALL_RESTITUTION,
    BALL_REST_SPEED,
    BALL_SCALE,
    GRAVITY,
)


class Ball:
    def __init__(self, x, y, bounds):
        # (x, y) is the ball's centre in global screen coordinates.
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.radius = BALL_BASE_R * BALL_SCALE
        self.spin = 0.0
        self.resting = False
        self.on_ground = False
        self.set_bounds(bounds)

    def set_bounds(self, bounds):
        self.min_x, self.min_y, self.max_x, self.max_y = bounds

    def kick(self, vx, vy):
        self.vx = vx
        self.vy = vy
        self.resting = False
        self.on_ground = False

    def _bottom(self):
        return self.y + self.radius

    def _landing_y(self, platforms, prev_bottom):
        """Top of the highest platform the ball's bottom crossed this frame
        (descending), or the desktop floor — whichever it lands on first."""
        bottom = self._bottom()
        best = None
        for platform in platforms:
            if not (platform["x"] <= self.x <= platform["x"] + platform["w"]):
                continue
            top = platform["y"]
            if prev_bottom <= top <= bottom:
                if best is None or top < best:
                    best = top
        if bottom > self.max_y and (best is None or self.max_y < best):
            best = self.max_y
        return best

    def update(self, platforms):
        self.vy += GRAVITY
        prev_bottom = self._bottom()
        self.x += self.vx
        self.y += self.vy
        self.vx *= BALL_AIR_FRICTION
        self.spin += self.vx * 0.12

        # Side walls.
        if self.x - self.radius < self.min_x:
            self.x = self.min_x + self.radius
            self.vx = abs(self.vx) * BALL_RESTITUTION
        elif self.x + self.radius > self.max_x:
            self.x = self.max_x - self.radius
            self.vx = -abs(self.vx) * BALL_RESTITUTION

        self.on_ground = False
        if self.vy >= 0:
            land_y = self._landing_y(platforms, prev_bottom)
            if land_y is not None:
                self.y = land_y - self.radius
                if self.vy > BALL_REST_SPEED * 2:
                    self.vy = -self.vy * BALL_RESTITUTION  # bounce
                else:
                    self.vy = 0.0
                self.vx *= BALL_FRICTION  # rolling friction
                self.on_ground = True
                self.resting = (
                    abs(self.vx) < BALL_REST_SPEED and abs(self.vy) < BALL_REST_SPEED
                )
