import math
import random
import sys
from pathlib import Path

try:
    from PyQt6.QtCore import QPoint, QRect, Qt, QTimer
    from PyQt6.QtGui import QPainter, QPixmap, QTransform
    from PyQt6.QtWidgets import QApplication, QWidget
except ImportError as exc:
    raise SystemExit(
        "PyQt6 is required for the transparent desktop pet.\n"
        "Install dependencies with: pip install -r requirements.txt"
    ) from exc


FPS = 60
SPRITE_HEIGHT = 128
ANIMATION_MS = 140


class State:
    IDLE = "idle"
    WALK = "walk"
    RUN = "run"
    JUMP = "jump"


def find_sprite_files():
    root = Path(__file__).resolve().parent
    patterns = [
        "assets/pet/*.png",
        "assets/*.png",
        "frames/*.png",
        "sprite*.png",
    ]
    files = []
    for pattern in patterns:
        files.extend(root.glob(pattern))
    return sorted(dict.fromkeys(files))


def load_frames():
    frames = []
    for path in find_sprite_files():
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            frames.append(pixmap)

    if not frames:
        raise SystemExit(
            "No sprite PNGs found. Add sprite.png, sprite_01.png, or PNGs in "
            "assets/pet/."
        )

    return frames


def scaled_frame(frame):
    return frame.scaledToHeight(
        SPRITE_HEIGHT,
        Qt.TransformationMode.SmoothTransformation,
    )


class PetWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.frames = [scaled_frame(frame) for frame in load_frames()]
        self.frame_index = 0
        self.frame_ticks = 0
        self.current_frame = self.frames[0]

        self.screen_rect = self._screen_rect()
        self.x = float(self.screen_rect.center().x())
        self.y = float(self.screen_rect.center().y())
        self.vx = 0.0
        self.vy = 0.0
        self.state = State.IDLE
        self.state_timer = 0
        self.facing_right = True
        self.jump_vy = 0.0
        self.ground_y = self.y

        self._configure_window()
        self._resize_to_frame()
        self._pick_state()

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(round(1000 / FPS))

    def _configure_window(self):
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _screen_rect(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            return QRect(0, 0, 1440, 900)
        return screen.availableGeometry()

    def _resize_to_frame(self):
        max_width = max(frame.width() for frame in self.frames)
        max_height = max(frame.height() for frame in self.frames)
        self.setFixedSize(max_width, max_height)

    def _pick_state(self):
        r = random.random()
        if r < 0.45:
            self.state = State.WALK
            speed = random.uniform(0.8, 1.8)
            angle = random.uniform(-0.25, 0.25)
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * speed * math.cos(angle)
            self.vy = speed * math.sin(angle)
            self.state_timer = random.randint(90, 300)
        elif r < 0.65:
            self.state = State.IDLE
            self.vx = 0.0
            self.vy = 0.0
            self.state_timer = random.randint(60, 180)
        elif r < 0.82:
            self.state = State.RUN
            speed = random.uniform(3.0, 5.5)
            direction = 1 if random.random() > 0.5 else -1
            self.vx = direction * speed
            self.vy = random.uniform(-0.4, 0.4)
            self.state_timer = random.randint(45, 120)
        else:
            self.state = State.JUMP
            self.ground_y = self.y
            self.jump_vy = random.uniform(-9, -5)
            self.vx = random.uniform(-2.5, 2.5)
            self.vy = 0.0
            self.state_timer = 600

    def tick(self):
        self.frame_ticks += round(1000 / FPS)
        if self.frame_ticks >= ANIMATION_MS:
            self.frame_ticks = 0
            self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.current_frame = self.frames[self.frame_index]

        self._update_motion()
        self.move(round(self.x), round(self.y))
        self.update()

    def _update_motion(self):
        self.state_timer -= 1

        if self.state == State.JUMP:
            self.jump_vy += 0.45
            self.y += self.jump_vy
            self.x += self.vx
            if self.y >= self.ground_y:
                self.y = self.ground_y
                self._pick_state()
        else:
            self.x += self.vx
            self.y += self.vy

        if self.vx > 0.1:
            self.facing_right = True
        elif self.vx < -0.1:
            self.facing_right = False

        left = self.screen_rect.left()
        top = self.screen_rect.top()
        right = self.screen_rect.right() - self.width()
        bottom = self.screen_rect.bottom() - self.height()

        if self.x < left:
            self.x = left
            self.vx = abs(self.vx)
        elif self.x > right:
            self.x = right
            self.vx = -abs(self.vx)

        if self.y < top:
            self.y = top
            if self.state == State.JUMP:
                self.jump_vy = abs(self.jump_vy) * 0.4
            else:
                self.vy = abs(self.vy)
        elif self.y > bottom:
            self.y = bottom
            if self.state == State.JUMP:
                self.jump_vy = 0
            else:
                self.vy = -abs(self.vy)

        if self.state_timer <= 0:
            self._pick_state()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        frame = self.current_frame
        if not self.facing_right:
            frame = frame.transformed(QTransform().scale(-1, 1))

        x = (self.width() - frame.width()) // 2
        y = (self.height() - frame.height()) // 2
        painter.drawPixmap(QPoint(x, y), frame)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    pet = PetWindow()
    pet.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
