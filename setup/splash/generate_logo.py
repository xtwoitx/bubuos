#!/usr/bin/env python3
"""Generate BubuOS splash background (no mascot — animated at runtime)."""

import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

pygame.init()

script_dir = os.path.dirname(os.path.abspath(__file__))

# Colors
DARK_BG = (35, 25, 20)
MED_BROWN = (100, 70, 55)
WARM_CREAM = (255, 243, 220)
MID_GRAY = (150, 135, 125)

SCREEN_W, SCREEN_H = 640, 480

# Mascot area height (matched to main.py _SPLASH_ART_H)
ART_H = 240

pygame.display.set_mode((1, 1))

splash = pygame.Surface((SCREEN_W, SCREEN_H))
splash.fill(DARK_BG)

# Title "BubuOS" — positioned below the mascot area
font_large = pygame.font.SysFont("monospace", 28, bold=True)
font_small = pygame.font.SysFont("monospace", 13)

art_y = (SCREEN_H - ART_H) // 2 - 60
title_y = art_y + ART_H + 8

title = font_large.render("BubuOS", True, WARM_CREAM)
splash.blit(title, ((SCREEN_W - title.get_width()) // 2, title_y))

title_bottom = title_y + title.get_height()

# Progress bar outline
bar_w, bar_h = 200, 12
bar_x = (SCREEN_W - bar_w) // 2
bar_y = title_bottom + 16
pygame.draw.rect(splash, MED_BROWN, (bar_x, bar_y, bar_w, bar_h), 1)

# Loading text
loading = font_small.render("Loading...", True, MID_GRAY)
splash.blit(loading, ((SCREEN_W - loading.get_width()) // 2, bar_y + 18))

# Print bar position for main.py to use
print(f"BAR: x={bar_x} y={bar_y} w={bar_w} h={bar_h}")

# Save
pygame.image.save(splash, os.path.join(script_dir, "splash.png"))

pygame.quit()
print(f"Generated: splash.png ({SCREEN_W}x{SCREEN_H})")
