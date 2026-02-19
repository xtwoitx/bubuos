#!/usr/bin/env python3
"""BubuOS boot splash — Bubu face with progress bar.

Runs as a systemd service via kmsdrm. Stays visible until BubuOS kills it
via ExecStartPre, ensuring no black gap between splash and shell.
"""

import os
import time
import signal

os.environ.setdefault("SDL_VIDEODRIVER", "x11")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

SALMON = (240, 140, 130)
SCREEN_W, SCREEN_H = 640, 480
MAX_WAIT = 60
# Progress bar position (must match generate_logo.py output)
BAR_X, BAR_Y, BAR_W, BAR_H = 220, 336, 200, 12


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.mouse.set_visible(False)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    splash_path = os.path.join(script_dir, "splash.png")

    splash_img = None
    if os.path.exists(splash_path):
        splash_img = pygame.image.load(splash_path).convert()

    fill_duration = 15.0
    start_time = time.time()
    running = True

    def handle_signal(sig, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    clock = pygame.time.Clock()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        elapsed = time.time() - start_time
        if elapsed > MAX_WAIT:
            break

        # Draw splash image (contains Bubu, title, bar outline, Loading...)
        if splash_img:
            screen.blit(splash_img, (0, 0))

        # Animate progress bar fill
        progress = min(1.0, elapsed / fill_duration)
        fill_w = int((BAR_W - 2) * progress)
        if fill_w > 0:
            pygame.draw.rect(screen, SALMON,
                             (BAR_X + 1, BAR_Y + 1, fill_w, BAR_H - 2))

        pygame.display.update()
        clock.tick(10)

    pygame.quit()


if __name__ == "__main__":
    main()
