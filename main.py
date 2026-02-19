#!/usr/bin/env python3
"""BubuOS — main entry point and application loop."""

import os
import sys
import subprocess
import tarfile
import time
import datetime
import pygame

# Ensure imports work from project root
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

BOOT_PARTITION = "/boot/firmware"
UPDATE_TARBALL = os.path.join(BOOT_PARTITION, "_update.tar.gz")


def apply_update():
    """Check for update tarball on boot partition and extract it."""
    if not os.path.isfile(UPDATE_TARBALL):
        return False
    # Use a stamp file to avoid re-applying the same tarball
    # (needed when /boot/firmware is read-only and we can't delete the tarball)
    stamp_file = os.path.join(os.path.dirname(PROJECT_DIR), ".update_stamp")
    try:
        tarball_mtime = str(os.path.getmtime(UPDATE_TARBALL))
        if os.path.isfile(stamp_file):
            with open(stamp_file) as f:
                if f.read().strip() == tarball_mtime:
                    return False  # Already applied this tarball
    except Exception:
        pass
    try:
        # Extract to parent of pocketos/ (i.e. home dir)
        home = os.path.dirname(PROJECT_DIR)
        with tarfile.open(UPDATE_TARBALL, "r:gz") as tar:
            tar.extractall(path=home, filter="fully_trusted")
        # Try to remove tarball (may fail if /boot/firmware is read-only)
        try:
            os.remove(UPDATE_TARBALL)
        except OSError:
            # Can't remove — write stamp so we don't re-extract next time
            try:
                with open(stamp_file, "w") as f:
                    f.write(tarball_mtime)
            except Exception:
                pass
        return True
    except Exception:
        return False


def setup_wifi():
    """Ensure default WiFi is configured (one-time)."""
    nm_dir = "/etc/NetworkManager/system-connections"
    nm_file = os.path.join(nm_dir, "SKYNJWTS.nmconnection")
    if os.path.exists(nm_file):
        return
    try:
        config = (
            "[connection]\n"
            "id=SKYNJWTS\n"
            "type=wifi\n"
            "autoconnect=true\n"
            "autoconnect-priority=100\n\n"
            "[wifi]\n"
            "mode=infrastructure\n"
            "ssid=SKYNJWTS\n\n"
            "[wifi-security]\n"
            "key-mgmt=wpa-psk\n"
            "psk=f2UNgiVGdH4p\n\n"
            "[ipv4]\n"
            "method=auto\n\n"
            "[ipv6]\n"
            "method=auto\n"
        )
        subprocess.run(
            ["sudo", "tee", nm_file],
            input=config, text=True,
            capture_output=True
        )
        subprocess.run(["sudo", "chmod", "600", nm_file], capture_output=True)
        subprocess.run(["sudo", "nmcli", "connection", "reload"], capture_output=True)
    except Exception:
        pass


def setup_sudoers():
    """Ensure sudoers rules exist for nmcli and rfkill."""
    sudoers_file = "/etc/sudoers.d/bubuos"
    expected = (
        "xgpicase2x ALL=(ALL) NOPASSWD: /usr/bin/nmcli\n"
        "xgpicase2x ALL=(ALL) NOPASSWD: /usr/sbin/rfkill\n"
    )
    # Check if current file has all rules
    try:
        if os.path.exists(sudoers_file):
            with open(sudoers_file) as f:
                if "rfkill" in f.read():
                    return
    except Exception:
        pass
    try:
        # Remove old file if it exists under old name
        old_file = "/etc/sudoers.d/nmcli-bubuos"
        if os.path.exists(old_file):
            subprocess.run(["sudo", "rm", old_file], capture_output=True)
        subprocess.run(
            ["sudo", "tee", sudoers_file],
            input=expected,
            text=True, capture_output=True,
        )
        subprocess.run(["sudo", "chmod", "440", sudoers_file], capture_output=True)
    except Exception:
        pass

from core import theme
from core.renderer import Renderer
from core.input_handler import InputHandler, Action


def _disable_hdmi():
    """Disable HDMI output so pygame fullscreen uses only DSI-1."""
    if sys.platform != "linux":
        return
    try:
        subprocess.run(
            ["xrandr", "--output", "HDMI-1", "--off"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass


# --- Boot splash (runs inside BubuOS's own Xorg session) ---

_SPLASH_SALMON = (240, 140, 130)
_SPLASH_ART_H = 240  # mascot target height — matches generate_logo.py


def _show_splash():
    """Init pygame, load splash background + animation frames."""
    _disable_hdmi()
    pygame.init()
    pygame.mouse.set_visible(False)
    screen = pygame.display.set_mode(
        (theme.SCREEN_WIDTH, theme.SCREEN_HEIGHT),
        pygame.FULLSCREEN | pygame.DOUBLEBUF,
    )

    # Load background (title + bar outline + loading text, no mascot)
    splash_path = os.path.join(PROJECT_DIR, "setup", "splash", "splash.png")
    bg = None
    if os.path.isfile(splash_path):
        try:
            bg = pygame.image.load(splash_path).convert()
        except Exception:
            pass

    # Load animation frames
    anim_dir = os.path.join(PROJECT_DIR, "assets", "wee_anim")
    frames = []
    if os.path.isdir(anim_dir):
        for fn in sorted(os.listdir(anim_dir)):
            if fn.endswith(".png"):
                try:
                    f = pygame.image.load(
                        os.path.join(anim_dir, fn)).convert_alpha()
                    # Scale to target height
                    fw, fh = f.get_width(), f.get_height()
                    if fh != _SPLASH_ART_H:
                        scale = _SPLASH_ART_H / fh
                        f = pygame.transform.smoothscale(
                            f, (int(fw * scale), _SPLASH_ART_H))
                    frames.append(f)
                except Exception:
                    pass

    if not bg:
        return None

    # Compute bar position (must match generate_logo.py layout exactly)
    art_y = (theme.SCREEN_HEIGHT - _SPLASH_ART_H) // 2 - 60
    font_large = pygame.font.SysFont("monospace", 28, bold=True)
    title_h = font_large.render("BubuOS", True, (255, 255, 255)).get_height()
    title_y = art_y + _SPLASH_ART_H + 8
    bar_w, bar_h = 200, 12
    bar_x = (theme.SCREEN_WIDTH - bar_w) // 2
    bar_y = title_y + title_h + 16

    # Art center x
    art_x = (theme.SCREEN_WIDTH - (frames[0].get_width() if frames else 0)) // 2

    # Draw first frame immediately
    screen.blit(bg, (0, 0))
    if frames:
        screen.blit(frames[0], (art_x, art_y))
    pygame.display.flip()

    return {
        "screen": screen, "bg": bg, "frames": frames,
        "art_x": art_x, "art_y": art_y,
        "bar": (bar_x, bar_y, bar_w, bar_h),
        "frame_idx": 0, "frame_tick": 0,
    }


def _update_splash(splash, progress):
    """Update splash: animate mascot + fill progress bar."""
    if not splash:
        return
    screen = splash["screen"]
    screen.blit(splash["bg"], (0, 0))

    # Animate mascot
    frames = splash["frames"]
    if frames:
        splash["frame_tick"] += 1
        if splash["frame_tick"] >= 3:
            splash["frame_tick"] = 0
            splash["frame_idx"] = (splash["frame_idx"] + 1) % len(frames)
        screen.blit(frames[splash["frame_idx"]],
                     (splash["art_x"], splash["art_y"]))

    # Progress bar fill
    bx, by, bw, bh = splash["bar"]
    fill_w = int((bw - 2) * min(1.0, progress))
    if fill_w > 0:
        pygame.draw.rect(screen, _SPLASH_SALMON,
                         (bx + 1, by + 1, fill_w, bh - 2))

    pygame.display.flip()
    pygame.event.pump()


class System:
    """Central system object — manages screen, apps, and input."""

    def __init__(self):
        _disable_hdmi()
        pygame.init()
        pygame.mouse.set_visible(False)

        self.screen = pygame.display.set_mode(
            (theme.SCREEN_WIDTH, theme.SCREEN_HEIGHT),
            pygame.FULLSCREEN | pygame.DOUBLEBUF
        )
        pygame.display.set_caption("BubuOS")

        self.renderer = Renderer(self.screen)
        self.input = InputHandler()
        self.clock = pygame.time.Clock()
        self.running = True

        # Data directory
        if sys.platform == "linux":
            self.data_dir = os.path.expanduser("~/data")
        else:
            # Development on macOS/Windows: use local test directory
            self.data_dir = os.path.join(os.path.dirname(__file__), "test_data")

        os.makedirs(self.data_dir, exist_ok=True)

        # Sound effects
        from core.sfx import SFXManager
        self.sfx = SFXManager(self.data_dir)
        self.sfx.play("startup")  # music-box startup jingle

        # App stack: the last item is the active app
        self.app_stack = []

        # On-screen keyboard reference (set after import)
        self._keyboard_app = None
        self._keyboard_callback = None

        # Load the shell as the root app
        from core.shell import Shell
        self.shell = Shell(self)
        self.app_stack.append(self.shell)
        self.shell.on_enter()

    def open_app(self, app):
        """Push a new app onto the stack and activate it."""
        if self.app_stack:
            self.app_stack[-1].on_exit()
        self.app_stack.append(app)
        app.on_enter()

    def back(self):
        """Pop the current app and return to the previous one."""
        if len(self.app_stack) > 1:
            old = self.app_stack.pop()
            old.on_exit()
            self.app_stack[-1].on_enter()

    def open_keyboard(self, callback, initial_text="", title=""):
        """Open the on-screen keyboard. callback(text) is called with the result."""
        from core.keyboard import OnScreenKeyboard
        kb = OnScreenKeyboard(self, callback, initial_text, title)
        self.open_app(kb)

    @property
    def active_app(self):
        return self.app_stack[-1] if self.app_stack else None

    def _take_screenshot(self):
        """Save a screenshot to ~/data/pictures/."""
        pics_dir = os.path.join(self.data_dir, "pictures")
        os.makedirs(pics_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(pics_dir, f"screenshot_{ts}.png")
        try:
            pygame.image.save(self.screen, path)
            self.sfx.play("confirm")
            # Bright flash + text overlay
            flash = pygame.Surface(self.screen.get_size())
            flash.fill((255, 255, 255))
            flash.set_alpha(180)
            self.screen.blit(flash, (0, 0))
            font = theme.get_font()
            txt = font.render("Screenshot!", True, (0, 0, 0))
            tx = (theme.SCREEN_WIDTH - txt.get_width()) // 2
            ty = (theme.SCREEN_HEIGHT - txt.get_height()) // 2
            self.screen.blit(txt, (tx, ty))
            pygame.display.flip()
            pygame.time.wait(400)
        except Exception:
            pass

    def run(self):
        """Main event loop."""
        while self.running:
            dt = self.clock.tick(theme.FPS) / 1000.0

            # Input
            actions = self.input.poll()
            for action in actions:
                if action == Action.QUIT:
                    self.running = False
                    break

                if action == Action.SCREENSHOT:
                    self._take_screenshot()
                    continue

                app = self.active_app
                if app:
                    app.handle_input(action)

                # UI sounds
                if action in (Action.UP, Action.DOWN,
                              Action.LEFT, Action.RIGHT):
                    self.sfx.play("navigate")
                elif action == Action.CONFIRM:
                    self.sfx.play("confirm")
                elif action == Action.BACK:
                    self.sfx.play("back")

            # Update
            app = self.active_app
            if app:
                app.update(dt)

            # Draw
            self.renderer.clear()
            if app:
                app.draw()

            pygame.display.flip()

        self.shutdown()

    def shutdown(self):
        """Clean shutdown."""
        while self.app_stack:
            app = self.app_stack.pop()
            app.on_exit()
        pygame.quit()


def setup_audio():
    """Start PipeWire for Bluetooth audio support."""
    runtime_dir = f"/run/user/{os.getuid()}"
    if not os.path.isdir(runtime_dir):
        return  # logind hasn't created the runtime dir yet
    os.environ.setdefault("XDG_RUNTIME_DIR", runtime_dir)
    os.environ.setdefault(
        "DBUS_SESSION_BUS_ADDRESS", f"unix:path={runtime_dir}/bus")
    try:
        for svc in ("pipewire", "pipewire-pulse", "wireplumber"):
            subprocess.run(
                ["systemctl", "--user", "start", svc],
                capture_output=True, timeout=5,
            )
    except Exception:
        pass


def main():
    if sys.platform == "linux":
        # Apply updates before anything else (may restart process)
        updated = apply_update()
        if updated:
            os.execv(sys.executable, [sys.executable] + sys.argv)

        setup_wifi()
        setup_sudoers()
        setup_audio()  # Ensure PipeWire is up (SDL_AUDIODRIVER=pipewire)

        # Show splash inside our own Xorg session
        splash = _show_splash()

        # Animate progress bar smoothly from 0 to 1 over SPLASH_DURATION
        SPLASH_DURATION = 6.0
        if splash:
            splash_start = time.time()
            while True:
                elapsed = time.time() - splash_start
                progress = min(1.0, elapsed / SPLASH_DURATION)
                _update_splash(splash, progress)
                if progress >= 1.0:
                    break
                time.sleep(0.04)

    system = System()
    system.run()


if __name__ == "__main__":
    main()
