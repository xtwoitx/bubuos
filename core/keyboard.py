"""BubuOS on-screen keyboard — grid-based input like Nintendo Switch."""

import pygame
from core.app import App
from core.input_handler import Action
from core import theme


# --- Keyboard layouts ---

LAYOUT_EN_LOWER = [
    list("1234567890"),
    list("qwertyuiop"),
    list("asdfghjkl;"),
    list("zxcvbnm,./"),
    list("-_@#$%&!?+"),
    list("=*:'\"<>()~"),
]

LAYOUT_EN_UPPER = [
    list("1234567890"),
    list("QWERTYUIOP"),
    list("ASDFGHJKL:"),
    list("ZXCVBNM<>?"),
    list("-_@#$%&!?+"),
    list("=*:'\"{}()~"),
]

# Interslavic Latin (Medžuslovjansky) — QWERTY with special chars
LAYOUT_IS_LOWER = [
    list("1234567890"),
    list("qwertyuiop"),
    list("asdfghjklě"),
    list("zxcvbnm,./"),
    list("čšžňŕľďćđų"),
    list("ȯė.,!?-@()"),
]

LAYOUT_IS_UPPER = [
    list("1234567890"),
    list("QWERTYUIOP"),
    list("ASDFGHJKLĚ"),
    list("ZXCVBNM<>?"),
    list("ČŠŽŇŔĽĎĆĐŲ"),
    list("ȮĖ.,!?-@()"),
]

LAYOUTS = {
    "en": {"lower": LAYOUT_EN_LOWER, "upper": LAYOUT_EN_UPPER, "label": "EN"},
    "is": {"lower": LAYOUT_IS_LOWER, "upper": LAYOUT_IS_UPPER, "label": "IS"},
}

LAYOUT_ORDER = ["en", "is"]


class OnScreenKeyboard(App):
    """Grid-based on-screen keyboard with multiple layouts."""

    name = "Keyboard"

    help_items = [
        ("A", "Type"),
        ("B", "Bksp"),
        ("X", "Space"),
        ("Y", "Caps"),
        ("Sel", "Lang"),
        ("Str", "Done"),
    ]

    def __init__(self, system, callback, initial_text="", title=""):
        super().__init__(system)
        self.callback = callback
        self.text = list(initial_text)
        self.cursor_pos = len(self.text)
        self.title = title or "Input"

        # Grid navigation
        self.grid_row = 0
        self.grid_col = 0

        # Layout state
        self.layout_index = 0  # index into LAYOUT_ORDER
        self.uppercase = False

        # Visual
        self.cell_w = 48
        self.cell_h = 32
        self.grid_x = 0  # computed in _compute_layout
        self.grid_y = 0
        self._compute_layout()

    def _compute_layout(self):
        grid = self._current_grid()
        cols = max(len(row) for row in grid)
        rows = len(grid)
        total_w = cols * self.cell_w
        total_h = rows * self.cell_h
        self.grid_x = (theme.SCREEN_WIDTH - total_w) // 2
        self.grid_y = theme.SCREEN_HEIGHT - total_h - theme.HELPBAR_HEIGHT - 8

    def _current_layout_key(self):
        return LAYOUT_ORDER[self.layout_index]

    def _current_layout(self):
        return LAYOUTS[self._current_layout_key()]

    def _current_grid(self):
        layout = self._current_layout()
        return layout["upper"] if self.uppercase else layout["lower"]

    def _current_char(self):
        grid = self._current_grid()
        if 0 <= self.grid_row < len(grid):
            row = grid[self.grid_row]
            if 0 <= self.grid_col < len(row):
                return row[self.grid_col]
        return None

    def handle_input(self, action):
        grid = self._current_grid()

        if action == Action.UP:
            self.grid_row = max(0, self.grid_row - 1)
            self._clamp_col()
        elif action == Action.DOWN:
            self.grid_row = min(len(grid) - 1, self.grid_row + 1)
            self._clamp_col()
        elif action == Action.LEFT:
            row = grid[self.grid_row]
            self.grid_col = max(0, self.grid_col - 1)
        elif action == Action.RIGHT:
            row = grid[self.grid_row]
            self.grid_col = min(len(row) - 1, self.grid_col + 1)

        elif action == Action.CONFIRM:  # A — type character
            ch = self._current_char()
            if ch:
                self.text.insert(self.cursor_pos, ch)
                self.cursor_pos += 1

        elif action == Action.BACK:  # B — backspace
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
                self.text.pop(self.cursor_pos)

        elif action == Action.MENU:  # X — space
            self.text.insert(self.cursor_pos, " ")
            self.cursor_pos += 1

        elif action == Action.DELETE:  # Y — toggle case
            self.uppercase = not self.uppercase
            self._compute_layout()

        elif action == Action.SWITCH_LAYOUT:  # Select — switch language
            self.layout_index = (self.layout_index + 1) % len(LAYOUT_ORDER)
            self._compute_layout()
            self._clamp_col()

        elif action == Action.SYSTEM:  # Start — confirm and close
            result = "".join(self.text)
            if self.callback:
                self.callback(result)
            self.system.back()

        elif action == Action.PAGE_UP:  # L — move text cursor left
            self.cursor_pos = max(0, self.cursor_pos - 1)

        elif action == Action.PAGE_DOWN:  # R — move text cursor right
            self.cursor_pos = min(len(self.text), self.cursor_pos + 1)

        return True

    def _clamp_col(self):
        grid = self._current_grid()
        row = grid[self.grid_row]
        self.grid_col = min(self.grid_col, len(row) - 1)

    def draw(self):
        r = self.system.renderer

        # Status bar
        layout_label = self._current_layout()["label"]
        case_label = "ABC" if self.uppercase else "abc"
        r.draw_statusbar(
            f"  {self.title}",
            f"{layout_label} {case_label}  "
        )

        # Text display area
        _, ch = theme.get_char_size()
        text_y = theme.CONTENT_TOP + 8
        text_str = "".join(self.text)

        # Show the text with cursor
        font = theme.get_font()

        # Background for text area
        r.draw_box(theme.PADDING, text_y - 2,
                   theme.SCREEN_WIDTH - theme.PADDING * 2, ch + 4,
                   bg=theme.BLACK, border=theme.BORDER_COLOR)

        # Text before cursor
        before = text_str[:self.cursor_pos]
        after = text_str[self.cursor_pos:]

        x = theme.PADDING + 4
        if before:
            r.draw_text(before, x, text_y, color=theme.WHITE)
            x += font.size(before)[0]

        # Cursor (blinking block)
        cursor_char = after[0] if after else " "
        r.draw_text(cursor_char, x, text_y, color=theme.BLACK, bg=theme.WHITE)
        x += font.size(cursor_char)[0]

        # Text after cursor
        if len(after) > 1:
            r.draw_text(after[1:], x, text_y, color=theme.WHITE)

        # Character grid
        grid = self._current_grid()
        for row_i, row in enumerate(grid):
            for col_i, char in enumerate(row):
                cx = self.grid_x + col_i * self.cell_w
                cy = self.grid_y + row_i * self.cell_h

                is_selected = (row_i == self.grid_row and col_i == self.grid_col)

                if is_selected:
                    r.draw_box(cx, cy, self.cell_w, self.cell_h,
                               bg=theme.HIGHLIGHT_BG)
                    r.draw_text(char, cx + (self.cell_w - font.size(char)[0]) // 2,
                                cy + (self.cell_h - ch) // 2,
                                color=theme.HIGHLIGHT_TEXT)
                else:
                    r.draw_border(cx, cy, self.cell_w, self.cell_h,
                                  color=theme.DARK_GRAY)
                    r.draw_text(char, cx + (self.cell_w - font.size(char)[0]) // 2,
                                cy + (self.cell_h - ch) // 2,
                                color=theme.TEXT_COLOR)

        # Help bar
        r.draw_helpbar(self.help_items)
