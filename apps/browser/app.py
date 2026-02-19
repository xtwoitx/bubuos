"""BubuOS Browser — launches surf (WebKit) with gamepad helper process."""

import os
import subprocess
import threading

from core.app import App
from core.input_handler import Action
from core import theme

# Mobile user-agent so sites serve lightweight pages
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Mobile Safari/537.36"
)

HELPER_SCRIPT = os.path.join(os.path.dirname(__file__), "gamepad_helper.py")


class BrowserApp(App):
    """Graphical web browser using surf + separate gamepad helper process."""

    name = "BubuBrowser"

    DEFAULT_HOME = "https://lite.duckduckgo.com/lite/"

    def __init__(self, system):
        super().__init__(system)
        self.browser_proc = None
        self.helper_proc = None
        self._url = self.DEFAULT_HOME

    def on_enter(self):
        def on_url(url):
            if url:
                self._url = url
                self._launch_browser(self._url)
            else:
                self.system.back()

        self.system.open_keyboard(on_url, initial_text=self._url, title="URL:")

    def _browser_running(self):
        return self.browser_proc and self.browser_proc.poll() is None

    def _launch_browser(self, url):
        if self._browser_running():
            return

        env = os.environ.copy()
        env["DISPLAY"] = ":0"

        try:
            self.browser_proc = subprocess.Popen(
                ["surf", "-F", "-u", MOBILE_UA, url],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return

        # Launch gamepad helper as separate process
        try:
            self.helper_proc = subprocess.Popen(
                ["python3", HELPER_SCRIPT, str(self.browser_proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

        # Monitor: when surf exits, clean up and go back
        def monitor():
            self.browser_proc.wait()
            self._cleanup_helper()
            self.system.back()

        threading.Thread(target=monitor, daemon=True).start()

    def _cleanup_helper(self):
        if self.helper_proc and self.helper_proc.poll() is None:
            self.helper_proc.terminate()
            try:
                self.helper_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.helper_proc.kill()

    def _stop_browser(self):
        if self._browser_running():
            self.browser_proc.terminate()
            try:
                self.browser_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.browser_proc.kill()
        self._cleanup_helper()

    def on_exit(self):
        self._stop_browser()

    def handle_input(self, action):
        if self._browser_running():
            return True

        if action == Action.CONFIRM:
            def on_url(url):
                if url:
                    self._url = url
                    self._launch_browser(self._url)
            self.system.open_keyboard(on_url, initial_text=self._url, title="URL:")
            return True

        elif action == Action.BACK:
            self.system.back()
            return True

        return False

    def draw(self):
        if self._browser_running():
            return

        r = self.system.renderer
        _, ch = theme.get_char_size()

        r.draw_statusbar("  Browser", "")

        y = theme.CONTENT_TOP + ch + 4

        r.draw_text("Press A to enter URL", theme.PADDING, y,
                    color=theme.TEXT_COLOR)
        y += ch * 2

        r.draw_text("Controls in browser:", theme.PADDING, y,
                    color=theme.ACCENT)
        y += ch + 4

        hints = [
            "D-pad    : Scroll page",
            "A        : Click / Enter",
            "B        : Go back",
            "X        : Enter URL",
            "L / R    : Page Up / Down",
            "Sel/Start: Exit browser",
        ]
        for hint in hints:
            r.draw_text(hint, theme.PADDING + 8, y, color=theme.TEXT_COLOR)
            y += ch

        r.draw_helpbar([("A", "Open URL"), ("B", "Back")])
