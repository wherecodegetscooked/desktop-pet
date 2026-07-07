"""Tests fuer die Ball-Physik (fallen, abprallen, ausrollen, landen).

Ball ist reine Logik wie Pet — kein Display noetig. Bounds sind
(min_x, min_y, max_x, max_y); Plattformen sind Dicts mit x/y/w.
"""

from ball import Ball
from config import BALL_BASE_R, BALL_SCALE, GRAVITY

BOUNDS = (0, 0, 800, 600)
RADIUS = BALL_BASE_R * BALL_SCALE


def test_falls_under_gravity():
    ball = Ball(400, 100, BOUNDS)
    ball.update([])
    assert ball.vy == GRAVITY
    assert ball.y > 100


def test_settles_on_floor():
    ball = Ball(400, 100, BOUNDS)
    for _ in range(600):
        ball.update([])
    assert ball.resting is True
    assert ball.on_ground is True
    # Kommt genau auf dem Boden zur Ruhe (Unterkante am max_y).
    assert ball.y == BOUNDS[3] - RADIUS


def test_bounces_off_right_wall():
    ball = Ball(BOUNDS[2] - RADIUS - 2, 100, BOUNDS)
    ball.kick(8.0, 0.0)
    ball.update([])
    assert ball.x + ball.radius <= BOUNDS[2]
    assert ball.vx < 0  # nach dem Wandkontakt umgedreht


def test_bounces_off_left_wall():
    ball = Ball(BOUNDS[0] + RADIUS + 2, 100, BOUNDS)
    ball.kick(-8.0, 0.0)
    ball.update([])
    assert ball.x - ball.radius >= BOUNDS[0]
    assert ball.vx > 0


def test_lands_on_platform():
    platform = {"x": 300, "y": 200, "w": 200, "h": 1}
    ball = Ball(400, 150, BOUNDS)
    ball.kick(0.0, 4.0)
    landed = False
    for _ in range(200):
        ball.update([platform])
        if ball.on_ground and abs(ball.y - (200 - RADIUS)) < 1:
            landed = True
            break
    assert landed


def test_ignores_platform_it_is_not_above():
    # Plattform seitlich versetzt -> der Ball faellt daran vorbei auf den Boden.
    platform = {"x": 0, "y": 200, "w": 50, "h": 1}
    ball = Ball(400, 150, BOUNDS)
    for _ in range(600):
        ball.update([platform])
    assert ball.y == BOUNDS[3] - RADIUS


def test_kick_clears_resting():
    ball = Ball(400, 100, BOUNDS)
    for _ in range(600):
        ball.update([])
    assert ball.resting is True
    ball.kick(5.0, -7.0)
    assert ball.resting is False
    assert ball.on_ground is False
