"""BubuOS rendering engine — text, boxes, borders in DOS style."""

import os
import glob
import pygame
from core import theme


class Renderer:
    """Handles all drawing operations on the screen."""

    def __init__(self, screen):
        self.screen = screen
        self._image_cache = {}
        self._anim_cache = {}

    def load_anim(self, anim_dir, target_h=None):
        """Load animation frames from a directory of numbered PNGs.

        Returns list of pygame Surfaces (cached after first load).
        """
        key = (anim_dir, target_h)
        if key not in self._anim_cache:
            pattern = os.path.join(anim_dir, "frame_*.png")
            paths = sorted(glob.glob(pattern))
            frames = []
            for p in paths:
                img = pygame.image.load(p).convert_alpha()
                if target_h and img.get_height() != target_h:
                    scale = target_h / img.get_height()
                    img = pygame.transform.smoothscale(
                        img, (int(img.get_width() * scale), target_h))
                frames.append(img)
            self._anim_cache[key] = frames
        return self._anim_cache[key]

    def load_image(self, path):
        """Load and cache an image with alpha support."""
        if path not in self._image_cache:
            if os.path.exists(path):
                self._image_cache[path] = pygame.image.load(path).convert_alpha()
            else:
                return None
        return self._image_cache[path]

    def clear(self, color=None):
        """Fill the entire screen with a color."""
        self.screen.fill(color or theme.BG_COLOR)

    def draw_text(self, text, x, y, color=None, size=None, bg=None):
        """Draw a single line of text. Returns the rendered rect."""
        font = theme.get_font(size or theme.FONT_SIZE)
        color = color or theme.TEXT_COLOR

        if bg:
            surface = font.render(text, True, color, bg)
        else:
            surface = font.render(text, True, color)

        rect = self.screen.blit(surface, (x, y))
        return rect

    def draw_text_centered(self, text, y, color=None, size=None, bg=None):
        """Draw text centered horizontally."""
        font = theme.get_font(size or theme.FONT_SIZE)
        surface = font.render(text, True, color or theme.TEXT_COLOR)
        x = (theme.SCREEN_WIDTH - surface.get_width()) // 2
        if bg:
            surface = font.render(text, True, color or theme.TEXT_COLOR, bg)
        self.screen.blit(surface, (x, y))

    def draw_row(self, text, y, fg=None, bg=None, size=None):
        """Draw a full-width text row with background."""
        fg = fg or theme.TEXT_COLOR
        bg = bg or theme.BG_COLOR
        font = theme.get_font(size or theme.FONT_SIZE)
        _, ch = theme.get_char_size(size or theme.FONT_SIZE)

        pygame.draw.rect(self.screen, bg, (0, y, theme.SCREEN_WIDTH, ch))
        surface = font.render(text, True, fg)
        self.screen.blit(surface, (theme.PADDING, y))

    def draw_box(self, x, y, w, h, bg=None, border=None):
        """Draw a filled rectangle with optional border."""
        bg = bg or theme.BG_COLOR
        pygame.draw.rect(self.screen, bg, (x, y, w, h))
        if border:
            pygame.draw.rect(self.screen, border, (x, y, w, h), 1)

    def draw_border(self, x, y, w, h, color=None):
        """Draw a single-pixel border rectangle."""
        color = color or theme.BORDER_COLOR
        pygame.draw.rect(self.screen, color, (x, y, w, h), 1)

    def draw_statusbar(self, left_text, right_text="", icon_path=None):
        """Draw the top status bar with optional icon."""
        self.draw_box(0, 0, theme.SCREEN_WIDTH, theme.STATUSBAR_HEIGHT,
                      bg=theme.STATUSBAR_BG)

        x = theme.PADDING
        if icon_path:
            icon = self.load_image(icon_path)
            if icon:
                icon_y = (theme.STATUSBAR_HEIGHT - icon.get_height()) // 2
                self.screen.blit(icon, (x, icon_y))
                x += icon.get_width() + 4

        self.draw_text(left_text, x, 4,
                       color=theme.STATUSBAR_TEXT, size=theme.FONT_SIZE)
        if right_text:
            font = theme.get_font(theme.FONT_SIZE)
            tw = font.size(right_text)[0]
            self.draw_text(right_text, theme.SCREEN_WIDTH - tw - theme.PADDING, 4,
                           color=theme.STATUSBAR_TEXT, size=theme.FONT_SIZE)

    def draw_helpbar(self, items):
        """Draw the bottom help bar. items is a list of (key, description) tuples."""
        y = theme.SCREEN_HEIGHT - theme.HELPBAR_HEIGHT
        self.draw_box(0, y, theme.SCREEN_WIDTH, theme.HELPBAR_HEIGHT,
                      bg=theme.STATUSBAR_BG)
        x = theme.PADDING
        font = theme.get_font(theme.FONT_SMALL)
        for key, desc in items:
            key_surface = font.render(key, True, theme.ACCENT)
            self.screen.blit(key_surface, (x, y + 3))
            x += key_surface.get_width()

            desc_surface = font.render(f":{desc}", True, theme.STATUSBAR_TEXT)
            self.screen.blit(desc_surface, (x, y + 3))
            x += desc_surface.get_width() + 12

    def draw_list(self, items, selected_index, y_start, max_visible,
                  scroll_offset=0, fg=None, sel_fg=None, sel_bg=None, size=None):
        """Draw a scrollable list of text items with selection highlight.

        Returns (visible_start, visible_end) range.
        """
        fg = fg or theme.TEXT_COLOR
        sel_fg = sel_fg or theme.HIGHLIGHT_TEXT
        sel_bg = sel_bg or theme.HIGHLIGHT_BG
        _, ch = theme.get_char_size(size or theme.FONT_SIZE)

        visible_start = scroll_offset
        visible_end = min(len(items), scroll_offset + max_visible)

        y = y_start
        for i in range(visible_start, visible_end):
            if i == selected_index:
                self.draw_row(items[i], y, fg=sel_fg, bg=sel_bg, size=size)
            else:
                self.draw_row(items[i], y, fg=fg, size=size)
            y += ch

        return visible_start, visible_end

    def draw_dialog(self, title, lines, buttons=None, selected_button=0):
        """Draw a centered dialog box with title, text, and buttons."""
        font = theme.get_font(theme.FONT_SIZE)
        _, ch = theme.get_char_size()

        # Calculate dialog size
        max_text_width = max(font.size(line)[0] for line in [title] + lines) if lines else font.size(title)[0]
        dialog_w = max_text_width + theme.PADDING * 4
        dialog_h = (len(lines) + 3) * ch + theme.PADDING * 2
        if buttons:
            dialog_h += ch + theme.PADDING

        dialog_w = min(dialog_w, theme.SCREEN_WIDTH - 40)
        x = (theme.SCREEN_WIDTH - dialog_w) // 2
        y = (theme.SCREEN_HEIGHT - dialog_h) // 2

        # Draw box
        self.draw_box(x, y, dialog_w, dialog_h, bg=theme.MENU_BG, border=theme.WHITE)

        # Title
        self.draw_text(title, x + theme.PADDING, y + theme.PADDING,
                       color=theme.ACCENT, size=theme.FONT_SIZE)

        # Separator
        sep_y = y + theme.PADDING + ch + 4
        pygame.draw.line(self.screen, theme.BORDER_COLOR,
                         (x + 4, sep_y), (x + dialog_w - 4, sep_y))

        # Content lines
        content_y = sep_y + 6
        for line in lines:
            self.draw_text(line, x + theme.PADDING, content_y,
                           color=theme.MENU_TEXT, size=theme.FONT_SIZE)
            content_y += ch

        # Buttons
        if buttons:
            btn_y = content_y + theme.PADDING
            btn_x = x + theme.PADDING
            for i, btn_text in enumerate(buttons):
                if i == selected_button:
                    self.draw_text(f" {btn_text} ", btn_x, btn_y,
                                   color=theme.MENU_HIGHLIGHT_TEXT,
                                   bg=theme.MENU_HIGHLIGHT_BG)
                else:
                    self.draw_text(f" {btn_text} ", btn_x, btn_y,
                                   color=theme.MENU_TEXT)
                btn_x += font.size(f" {btn_text} ")[0] + 12
