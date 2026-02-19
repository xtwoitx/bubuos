"""BubuOS DOS-like theme: colors, fonts, layout constants."""

import os
import pygame


# --- Screen ---
SCREEN_WIDTH = 640
SCREEN_HEIGHT = 480
FPS = 30

# --- Bubu color palette (light theme — warm cream bg, brown text) ---
BLACK = (0, 0, 0)
DARK_BROWN = (60, 40, 30)
MED_BROWN = (100, 70, 55)
WARM_BROWN = (140, 100, 80)
WARM_CREAM = (255, 243, 220)
CREAM = (245, 242, 238)
WARM_GRAY = (160, 140, 125)
DARK_WARM_GRAY = (120, 100, 85)
LIGHT_PINK = (245, 185, 175)
SALMON = (240, 140, 130)
WARM_RED = (200, 70, 60)
SOFT_GREEN = (100, 170, 100)
WHITE = (255, 255, 255)
DARK_GRAY = (80, 70, 65)

# --- Semantic colors ---
BG_COLOR = WARM_CREAM
TEXT_COLOR = DARK_BROWN
TEXT_BRIGHT = BLACK
TEXT_DIM = WARM_GRAY
HIGHLIGHT_BG = SALMON
HIGHLIGHT_TEXT = WHITE
ACCENT = LIGHT_PINK
ERROR_COLOR = WARM_RED
SUCCESS_COLOR = SOFT_GREEN
BORDER_COLOR = WARM_BROWN
STATUSBAR_BG = MED_BROWN
STATUSBAR_TEXT = CREAM
MENU_BG = CREAM
MENU_TEXT = DARK_BROWN
MENU_HIGHLIGHT_BG = SALMON
MENU_HIGHLIGHT_TEXT = WHITE

# --- Layout ---
PADDING = 8
STATUSBAR_HEIGHT = 32
HELPBAR_HEIGHT = 32
CONTENT_TOP = STATUSBAR_HEIGHT + 2
CONTENT_BOTTOM = SCREEN_HEIGHT - HELPBAR_HEIGHT - 2
CONTENT_HEIGHT = CONTENT_BOTTOM - CONTENT_TOP

# --- Font ---
FONT_SIZE = 27
FONT_SMALL = 22
FONT_LARGE = 34

_font_cache = {}


def get_font(size=FONT_SIZE):
    """Get a monospace font at the given size. Uses system monospace as fallback."""
    if size in _font_cache:
        return _font_cache[size]

    font_path = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "PxPlus_IBM_VGA8.ttf")

    if os.path.exists(font_path):
        font = pygame.font.Font(font_path, size)
    else:
        font = pygame.font.SysFont("monospace", size, bold=True)

    font.set_bold(True)
    _font_cache[size] = font
    return font


def get_char_size(size=FONT_SIZE):
    """Get character dimensions for the current font."""
    font = get_font(size)
    return font.size("W")


def get_grid_cols(size=FONT_SIZE):
    """How many characters fit in one row."""
    cw, _ = get_char_size(size)
    return (SCREEN_WIDTH - PADDING * 2) // cw


def get_grid_rows(size=FONT_SIZE):
    """How many text rows fit in the content area."""
    _, ch = get_char_size(size)
    return CONTENT_HEIGHT // ch
