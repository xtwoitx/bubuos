"""BubuOS Image Viewer — view pictures with navigation."""

import os

import pygame

from core.app import App
from core.input_handler import Action
from core import theme

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}


class ImageViewerApp(App):
    """Full-screen image viewer with folder navigation."""

    name = "Image Viewer"

    def __init__(self, system, path=None):
        super().__init__(system)
        self.images = []
        self.index = 0
        self._surface = None
        self._filename = ""

        if path and os.path.isfile(path):
            folder = os.path.dirname(path)
            self._scan_folder(folder)
            # Set index to opened file
            for i, p in enumerate(self.images):
                if os.path.abspath(p) == os.path.abspath(path):
                    self.index = i
                    break
            self._load_current()

    def _scan_folder(self, folder):
        """Find all images in the folder."""
        try:
            entries = sorted(os.listdir(folder))
        except OSError:
            entries = []
        self.images = []
        for name in entries:
            ext = os.path.splitext(name)[1].lower()
            if ext in _IMAGE_EXTS:
                self.images.append(os.path.join(folder, name))

    def _load_current(self):
        """Load the current image and scale to fit screen."""
        self._surface = None
        if not self.images:
            return
        path = self.images[self.index]
        self._filename = os.path.basename(path)
        try:
            img = pygame.image.load(path)
            # Scale to fit within content area
            max_w = theme.SCREEN_WIDTH
            max_h = theme.SCREEN_HEIGHT - theme.STATUSBAR_HEIGHT - theme.HELPBAR_HEIGHT
            iw, ih = img.get_width(), img.get_height()
            scale = min(max_w / iw, max_h / ih, 1.0)
            if scale < 1.0:
                nw = int(iw * scale)
                nh = int(ih * scale)
                img = pygame.transform.smoothscale(img, (nw, nh))
            self._surface = img.convert()
        except Exception:
            self._surface = None

    def handle_input(self, action):
        if action == Action.LEFT or action == Action.PAGE_UP:
            if self.images:
                self.index = (self.index - 1) % len(self.images)
                self._load_current()
            return True
        elif action == Action.RIGHT or action == Action.PAGE_DOWN:
            if self.images:
                self.index = (self.index + 1) % len(self.images)
                self._load_current()
            return True
        elif action == Action.BACK:
            self.system.back()
            return True
        return False

    def draw(self):
        r = self.system.renderer
        count = f"{self.index + 1}/{len(self.images)}" if self.images else ""
        r.draw_statusbar(f"  {self._filename}", count)

        if self._surface:
            # Center image in content area
            cx = (theme.SCREEN_WIDTH - self._surface.get_width()) // 2
            cy = (theme.STATUSBAR_HEIGHT
                  + (theme.SCREEN_HEIGHT - theme.STATUSBAR_HEIGHT
                     - theme.HELPBAR_HEIGHT
                     - self._surface.get_height()) // 2)
            r.screen.blit(self._surface, (cx, cy))
        else:
            r.draw_text("Cannot load image", theme.PADDING,
                         theme.CONTENT_TOP + 8, color=theme.WARM_GRAY)

        r.draw_helpbar([
            ("< >", "Prev/Next"), ("B", "Back"),
        ])
