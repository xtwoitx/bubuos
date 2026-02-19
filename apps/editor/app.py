"""BubuOS Text Editor — simple text file editor with on-screen keyboard."""

import os
from core.app import App
from core.input_handler import Action
from core import theme


class EditorApp(App):
    """A simple text editor for .txt files."""

    name = "BubuText"
    help_items = [
        ("A", "Type"), ("B", "Back"), ("X", "Menu"),
        ("Y", "Del"), ("D", "Move"),
    ]

    def __init__(self, system, file_path=None):
        super().__init__(system)
        self.file_path = file_path
        self.lines = [""]
        self.cursor_row = 0
        self.cursor_col = 0
        self.scroll_offset = 0
        self.modified = False

        # Menu state
        self._menu_active = False
        self._menu_selected = 0
        self._menu_items = [
            ("Save", self._save),
            ("Save As...", self._save_as),
            ("Exit", self._exit),
        ]

        if file_path and os.path.exists(file_path):
            self._load_file(file_path)

    def _load_file(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.lines = content.split("\n")
            if not self.lines:
                self.lines = [""]
        except OSError:
            self.lines = [""]
        self.cursor_row = 0
        self.cursor_col = 0
        self.scroll_offset = 0
        self.modified = False

    def _save(self):
        if not self.file_path:
            self._save_as()
            return
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.lines))
            self.modified = False
        except OSError:
            pass

    def _save_as(self):
        def on_name(name):
            if name:
                self.file_path = os.path.join(self.system.data_dir, name)
                self._save()

        initial = os.path.basename(self.file_path) if self.file_path else "untitled.txt"
        self.system.open_keyboard(on_name, initial_text=initial, title="Save as:")

    def _exit(self):
        self.system.back()

    def handle_input(self, action):
        # Menu mode
        if self._menu_active:
            return self._handle_menu(action)

        if action == Action.UP:
            self.cursor_row = max(0, self.cursor_row - 1)
            self._clamp_col()
            self._adjust_scroll()
        elif action == Action.DOWN:
            self.cursor_row = min(len(self.lines) - 1, self.cursor_row + 1)
            self._clamp_col()
            self._adjust_scroll()
        elif action == Action.LEFT:
            if self.cursor_col > 0:
                self.cursor_col -= 1
            elif self.cursor_row > 0:
                self.cursor_row -= 1
                self.cursor_col = len(self.lines[self.cursor_row])
                self._adjust_scroll()
        elif action == Action.RIGHT:
            line = self.lines[self.cursor_row]
            if self.cursor_col < len(line):
                self.cursor_col += 1
            elif self.cursor_row < len(self.lines) - 1:
                self.cursor_row += 1
                self.cursor_col = 0
                self._adjust_scroll()

        elif action == Action.CONFIRM:  # A — open keyboard to type
            self._open_typing_keyboard()

        elif action == Action.BACK:  # B — back (close editor)
            self.system.back()

        elif action == Action.MENU:  # X — open menu
            self._menu_active = True
            self._menu_selected = 0

        elif action == Action.DELETE:  # Y — delete char at cursor
            self._delete_char()

        elif action == Action.PAGE_UP:  # L — page up
            _, ch = theme.get_char_size()
            visible = (theme.CONTENT_BOTTOM - theme.CONTENT_TOP - 30) // ch
            self.cursor_row = max(0, self.cursor_row - visible)
            self._clamp_col()
            self._adjust_scroll()

        elif action == Action.PAGE_DOWN:  # R — page down
            _, ch = theme.get_char_size()
            visible = (theme.CONTENT_BOTTOM - theme.CONTENT_TOP - 30) // ch
            self.cursor_row = min(len(self.lines) - 1, self.cursor_row + visible)
            self._clamp_col()
            self._adjust_scroll()

        elif action == Action.SYSTEM:  # Start — quick save
            self._save()

        return True

    def _handle_menu(self, action):
        if action == Action.UP:
            self._menu_selected = max(0, self._menu_selected - 1)
        elif action == Action.DOWN:
            self._menu_selected = min(len(self._menu_items) - 1, self._menu_selected + 1)
        elif action == Action.CONFIRM:
            _, callback = self._menu_items[self._menu_selected]
            self._menu_active = False
            callback()
        elif action in (Action.BACK, Action.MENU):
            self._menu_active = False
        return True

    def _open_typing_keyboard(self):
        """Open the on-screen keyboard. Typed text is inserted at cursor position."""
        def on_text(text):
            if not text:
                return
            # Insert text at cursor
            line = self.lines[self.cursor_row]
            before = line[:self.cursor_col]
            after = line[self.cursor_col:]

            # Handle multi-line paste (if text contains newlines)
            new_lines = text.split("\n")
            if len(new_lines) == 1:
                self.lines[self.cursor_row] = before + text + after
                self.cursor_col += len(text)
            else:
                self.lines[self.cursor_row] = before + new_lines[0]
                for i, nl in enumerate(new_lines[1:], 1):
                    if i == len(new_lines) - 1:
                        self.lines.insert(self.cursor_row + i, nl + after)
                    else:
                        self.lines.insert(self.cursor_row + i, nl)
                self.cursor_row += len(new_lines) - 1
                self.cursor_col = len(new_lines[-1])

            self.modified = True

        # Pre-fill with current character for context
        self.system.open_keyboard(on_text, title="Type text:")

    def _delete_char(self):
        line = self.lines[self.cursor_row]
        if self.cursor_col > 0:
            self.lines[self.cursor_row] = line[:self.cursor_col - 1] + line[self.cursor_col:]
            self.cursor_col -= 1
            self.modified = True
        elif self.cursor_row > 0:
            # Merge with previous line
            prev_len = len(self.lines[self.cursor_row - 1])
            self.lines[self.cursor_row - 1] += line
            self.lines.pop(self.cursor_row)
            self.cursor_row -= 1
            self.cursor_col = prev_len
            self.modified = True
            self._adjust_scroll()

    def _clamp_col(self):
        line = self.lines[self.cursor_row]
        self.cursor_col = min(self.cursor_col, len(line))

    def _adjust_scroll(self):
        _, ch = theme.get_char_size()
        visible = (theme.CONTENT_BOTTOM - theme.CONTENT_TOP - 30) // ch
        if self.cursor_row < self.scroll_offset:
            self.scroll_offset = self.cursor_row
        elif self.cursor_row >= self.scroll_offset + visible:
            self.scroll_offset = self.cursor_row - visible + 1

    def draw(self):
        r = self.system.renderer

        # Status bar
        fname = os.path.basename(self.file_path) if self.file_path else "New File"
        mod = "*" if self.modified else ""
        r.draw_statusbar(
            f"  {fname}{mod}",
            f"Ln {self.cursor_row + 1}  Col {self.cursor_col + 1}  "
        )

        # Text content
        font = theme.get_font()
        _, ch = theme.get_char_size()
        y = theme.CONTENT_TOP + 4
        visible = (theme.CONTENT_BOTTOM - y) // ch

        for i in range(self.scroll_offset, min(len(self.lines), self.scroll_offset + visible)):
            line = self.lines[i]

            # Line number
            ln_text = f"{i + 1:4d} "
            r.draw_text(ln_text, 2, y, color=theme.DARK_GRAY, size=theme.FONT_SIZE)
            ln_width = font.size(ln_text)[0]

            # Line content
            if i == self.cursor_row:
                # Draw line with cursor
                before = line[:self.cursor_col]
                after = line[self.cursor_col:]

                x = ln_width + 4
                if before:
                    r.draw_text(before, x, y, color=theme.TEXT_COLOR)
                    x += font.size(before)[0]

                # Cursor
                cursor_char = after[0] if after else " "
                r.draw_text(cursor_char, x, y, color=theme.BG_COLOR, bg=theme.TEXT_COLOR)
                x += font.size(cursor_char)[0]

                if len(after) > 1:
                    r.draw_text(after[1:], x, y, color=theme.TEXT_COLOR)
            else:
                r.draw_text(line, ln_width + 4, y, color=theme.TEXT_COLOR)

            y += ch

        # Help bar
        r.draw_helpbar(self.help_items)

        # Menu overlay
        if self._menu_active:
            self._draw_menu(r)

    def _draw_menu(self, r):
        import pygame as _pg

        font = theme.get_font()
        _, ch = theme.get_char_size()

        labels = [item[0] for item in self._menu_items]
        max_w = max(font.size(l)[0] for l in labels) + theme.PADDING * 4
        menu_h = len(labels) * ch + theme.PADDING
        x = (theme.SCREEN_WIDTH - max_w) // 2
        y = (theme.SCREEN_HEIGHT - menu_h) // 2

        r.draw_box(x, y, max_w, menu_h, bg=theme.MENU_BG, border=theme.BORDER_COLOR)

        item_y = y + theme.PADDING // 2
        for i, label in enumerate(labels):
            if i == self._menu_selected:
                _pg.draw.rect(r.screen, theme.MENU_HIGHLIGHT_BG,
                              (x + 1, item_y, max_w - 2, ch))
                r.draw_text(f"  {label}", x + 4, item_y,
                            color=theme.MENU_HIGHLIGHT_TEXT)
            else:
                r.draw_text(f"  {label}", x + 4, item_y, color=theme.MENU_TEXT)
            item_y += ch
