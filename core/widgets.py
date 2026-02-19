"""BubuOS UI widgets — reusable components for building interfaces."""

from core import theme
from core.input_handler import Action


class ScrollList:
    """A scrollable list with keyboard navigation."""

    def __init__(self, items=None):
        self.items = items or []
        self.selected = 0
        self.scroll_offset = 0
        self.max_visible = 20

    def set_items(self, items):
        self.items = items
        self.selected = min(self.selected, max(0, len(items) - 1))
        self._adjust_scroll()

    def handle_input(self, action):
        """Handle navigation. Returns True if action was consumed."""
        if not self.items:
            return False

        if action == Action.UP:
            self.selected = max(0, self.selected - 1)
            self._adjust_scroll()
            return True
        elif action == Action.DOWN:
            self.selected = min(len(self.items) - 1, self.selected + 1)
            self._adjust_scroll()
            return True
        elif action == Action.PAGE_UP:
            self.selected = max(0, self.selected - self.max_visible)
            self._adjust_scroll()
            return True
        elif action == Action.PAGE_DOWN:
            self.selected = min(len(self.items) - 1,
                                self.selected + self.max_visible)
            self._adjust_scroll()
            return True
        return False

    def _adjust_scroll(self):
        if self.selected < self.scroll_offset:
            self.scroll_offset = self.selected
        elif self.selected >= self.scroll_offset + self.max_visible:
            self.scroll_offset = self.selected - self.max_visible + 1

    def get_selected_item(self):
        if self.items and 0 <= self.selected < len(self.items):
            return self.items[self.selected]
        return None

    def draw(self, renderer, y_start):
        """Draw the list. Returns the y position after the last item."""
        renderer.draw_list(
            self.items, self.selected, y_start,
            self.max_visible, self.scroll_offset
        )


class ContextMenu:
    """A popup context menu."""

    def __init__(self, options):
        """options: list of (label, callback) tuples."""
        self.options = options
        self.selected = 0
        self.active = False

    def open(self):
        self.selected = 0
        self.active = True

    def close(self):
        self.active = False

    def handle_input(self, action):
        if not self.active:
            return False

        if action == Action.UP:
            self.selected = max(0, self.selected - 1)
            return True
        elif action == Action.DOWN:
            self.selected = min(len(self.options) - 1, self.selected + 1)
            return True
        elif action == Action.CONFIRM:
            if self.options:
                _, callback = self.options[self.selected]
                self.close()
                if callback:
                    callback()
            return True
        elif action == Action.BACK:
            self.close()
            return True

        return True  # consume all input while menu is active

    def draw(self, renderer, x=None, y=None):
        if not self.active:
            return

        import pygame as _pg

        font = theme.get_font()
        _, ch = theme.get_char_size()

        labels = [opt[0] for opt in self.options]
        max_w = max(font.size(label)[0] for label in labels) + theme.PADDING * 4
        menu_h = len(labels) * ch + theme.PADDING

        if x is None:
            x = (theme.SCREEN_WIDTH - max_w) // 2
        if y is None:
            y = (theme.SCREEN_HEIGHT - menu_h) // 2

        renderer.draw_box(x, y, max_w, menu_h,
                          bg=theme.MENU_BG, border=theme.BORDER_COLOR)

        item_y = y + theme.PADDING // 2
        for i, label in enumerate(labels):
            if i == self.selected:
                _pg.draw.rect(renderer.screen, theme.MENU_HIGHLIGHT_BG,
                              (x + 1, item_y, max_w - 2, ch))
                renderer.draw_text(f" {label}", x + 4, item_y,
                                   color=theme.MENU_HIGHLIGHT_TEXT)
            else:
                renderer.draw_text(f" {label}", x + 4, item_y,
                                   color=theme.MENU_TEXT)
            item_y += ch


class ConfirmDialog:
    """A Yes/No confirmation dialog."""

    def __init__(self, title, message, on_confirm=None, on_cancel=None):
        self.title = title
        self.message = message
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.selected_button = 0  # 0=Yes, 1=No
        self.active = False

    def open(self):
        self.selected_button = 1  # Default to No (safer)
        self.active = True

    def close(self):
        self.active = False

    def handle_input(self, action):
        if not self.active:
            return False

        if action == Action.LEFT:
            self.selected_button = 0
            return True
        elif action == Action.RIGHT:
            self.selected_button = 1
            return True
        elif action == Action.CONFIRM:
            self.close()
            if self.selected_button == 0 and self.on_confirm:
                self.on_confirm()
            elif self.selected_button == 1 and self.on_cancel:
                self.on_cancel()
            return True
        elif action == Action.BACK:
            self.close()
            if self.on_cancel:
                self.on_cancel()
            return True

        return True

    def draw(self, renderer):
        if not self.active:
            return

        lines = [self.message] if isinstance(self.message, str) else self.message
        renderer.draw_dialog(
            self.title, lines,
            buttons=["Yes", "No"],
            selected_button=self.selected_button
        )
