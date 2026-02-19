"""BubuOS Snake Game."""

import os
import random
import pygame

from core.app import App
from core.input_handler import Action
from core import theme

DIR_UP = (0, -1)
DIR_DOWN = (0, 1)
DIR_LEFT = (-1, 0)
DIR_RIGHT = (1, 0)

STATE_PLAYING = 0
STATE_PAUSED = 1
STATE_GAME_OVER = 2

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "assets")


class SnakeApp(App):
    """Classic snake game."""

    name = "Snake"

    CELL = 32
    SCORE_H = 28
    GRID_Y = theme.CONTENT_TOP + 28  # below score line
    GRID_W = theme.SCREEN_WIDTH // 32   # 20
    GRID_H = (theme.CONTENT_BOTTOM - GRID_Y) // 32  # 12

    SNAKE_COLOR = theme.SALMON
    GRID_BG = (245, 233, 200)

    INITIAL_SPEED = 6  # frames between moves (30 FPS → 5 moves/sec)
    MIN_SPEED = 2
    SPEED_EVERY = 50  # speed up every N points

    def __init__(self, system):
        super().__init__(system)
        # Load sprites to fit inside cells with 1px margin
        self._head_img = self._load_sprite("bubu_icon.png")
        self._food_img = self._load_sprite("burger.png")
        self._reset()

    def _load_sprite(self, name):
        path = os.path.join(ASSETS_DIR, name)
        try:
            img = pygame.image.load(path).convert_alpha()
            s = self.CELL - 2
            # Scale preserving aspect ratio, fit within s×s
            w, h = img.get_width(), img.get_height()
            scale = min(s / w, s / h)
            nw, nh = int(w * scale), int(h * scale)
            img = pygame.transform.smoothscale(img, (nw, nh))
            # Center on s×s transparent surface
            surf = pygame.Surface((s, s), pygame.SRCALPHA)
            surf.blit(img, ((s - nw) // 2, (s - nh) // 2))
            return surf
        except Exception:
            return None

    def _reset(self):
        cx, cy = self.GRID_W // 2, self.GRID_H // 2
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.dir = DIR_RIGHT
        self.next_dir = DIR_RIGHT
        self.food = None
        self._place_food()
        self.score = 0
        self.state = STATE_PLAYING
        self.timer = 0
        self.speed = self.INITIAL_SPEED

    def _place_food(self):
        occupied = set(self.snake)
        free = [(x, y) for x in range(self.GRID_W)
                for y in range(self.GRID_H) if (x, y) not in occupied]
        if free:
            self.food = random.choice(free)
        else:
            self.state = STATE_GAME_OVER

    def handle_input(self, action):
        if self.state == STATE_GAME_OVER:
            if action == Action.CONFIRM:
                self._reset()
            elif action == Action.BACK:
                self.system.back()
            return True

        if self.state == STATE_PAUSED:
            if action in (Action.SYSTEM, Action.CONFIRM):
                self.state = STATE_PLAYING
            elif action == Action.BACK:
                self.system.back()
            return True

        # Playing
        if action == Action.UP and self.dir != DIR_DOWN:
            self.next_dir = DIR_UP
        elif action == Action.DOWN and self.dir != DIR_UP:
            self.next_dir = DIR_DOWN
        elif action == Action.LEFT and self.dir != DIR_RIGHT:
            self.next_dir = DIR_LEFT
        elif action == Action.RIGHT and self.dir != DIR_LEFT:
            self.next_dir = DIR_RIGHT
        elif action == Action.SYSTEM:
            self.state = STATE_PAUSED
        elif action == Action.BACK:
            self.system.back()
        return True

    def update(self, dt):
        if self.state != STATE_PLAYING:
            return

        self.timer += 1
        if self.timer < self.speed:
            return
        self.timer = 0

        self.dir = self.next_dir
        hx, hy = self.snake[0]
        dx, dy = self.dir
        head = (hx + dx, hy + dy)

        # Wall collision
        nx, ny = head
        if nx < 0 or nx >= self.GRID_W or ny < 0 or ny >= self.GRID_H:
            self.state = STATE_GAME_OVER
            self.system.sfx.play("error")
            return

        # Self collision
        if head in self.snake:
            self.state = STATE_GAME_OVER
            self.system.sfx.play("error")
            return

        self.snake.insert(0, head)

        if head == self.food:
            self.score += 10
            self.system.sfx.play("eat")
            self._place_food()
            if self.score % self.SPEED_EVERY == 0:
                self.speed = max(self.MIN_SPEED, self.speed - 1)
        else:
            self.snake.pop()

    def draw(self):
        r = self.system.renderer
        scr = r.screen

        # Status bar with score
        r.draw_statusbar(f"  Snake  Score: {self.score}", "")

        # Grid background
        gw = self.GRID_W * self.CELL
        gh = self.GRID_H * self.CELL
        r.draw_box(0, self.GRID_Y, gw, gh, bg=self.GRID_BG)
        pygame.draw.rect(scr, theme.MED_BROWN,
                         (0, self.GRID_Y, gw, gh), 1)

        # Food (burger)
        if self.food:
            fx, fy = self.food
            px = fx * self.CELL + 1
            py = self.GRID_Y + fy * self.CELL + 1
            if self._food_img:
                scr.blit(self._food_img, (px, py))
            else:
                pygame.draw.rect(scr, theme.SOFT_GREEN,
                                 (px, py, self.CELL - 2, self.CELL - 2))

        # Snake body
        for i, (sx, sy) in enumerate(self.snake):
            px = sx * self.CELL + 1
            py = self.GRID_Y + sy * self.CELL + 1
            if i == 0 and self._head_img:
                scr.blit(self._head_img, (px, py))
            else:
                pygame.draw.rect(scr, self.SNAKE_COLOR,
                                 (px, py, self.CELL - 2, self.CELL - 2))

        # Overlays
        if self.state == STATE_PAUSED:
            self._draw_overlay("PAUSED", "Start to resume")
        elif self.state == STATE_GAME_OVER:
            self._draw_overlay("GAME OVER",
                               f"Score: {self.score}  A:retry B:exit")

        # Help bar
        if self.state == STATE_PLAYING:
            r.draw_helpbar([("D-Pad", "Move"), ("Start", "Pause"),
                            ("B", "Exit")])
        elif self.state == STATE_PAUSED:
            r.draw_helpbar([("Start", "Resume"), ("B", "Exit")])
        else:
            r.draw_helpbar([("A", "Retry"), ("B", "Exit")])

    def _draw_overlay(self, title, subtitle):
        """Draw centered overlay box."""
        r = self.system.renderer
        font = theme.get_font(theme.FONT_SIZE)
        font_sm = theme.get_font(theme.FONT_SMALL)
        tw = font.size(title)[0]
        sw = font_sm.size(subtitle)[0]
        bw = max(tw, sw) + 40
        bh = 70
        bx = (theme.SCREEN_WIDTH - bw) // 2
        by = (theme.SCREEN_HEIGHT - bh) // 2
        r.draw_box(bx, by, bw, bh, bg=theme.STATUSBAR_BG)
        pygame.draw.rect(r.screen, theme.ACCENT, (bx, by, bw, bh), 2)
        r.draw_text(title, (theme.SCREEN_WIDTH - tw) // 2, by + 10,
                     color=theme.WARM_CREAM)
        r.draw_text(subtitle, (theme.SCREEN_WIDTH - sw) // 2, by + 42,
                     color=theme.ACCENT, size=theme.FONT_SMALL)
