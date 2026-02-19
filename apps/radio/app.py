"""BubuOS Internet Radio — stream radio stations via mpv."""

import os
import json
import socket
import subprocess
import time

import pygame

from core.app import App
from core.input_handler import Action
from core import theme

# fmt: off
STATIONS = [
    ("Lofi Hip Hop",        "https://play.streamafrica.net/lofiradio"),
    ("Groove Salad",        "https://ice3.somafm.com/groovesalad-256-mp3"),
    ("Drone Zone",          "https://ice3.somafm.com/dronezone-256-mp3"),
    ("Jazz24",              "https://live.amperwave.net/direct/ppm-jazz24mp3-ibc1"),
    ("Classic FM",          "http://media-ice.musicradio.com/ClassicFMMP3"),
    ("NTS Radio",           "https://stream-relay-geo.ntslive.net/stream"),
    ("BBC Radio 1",         "http://as-hls-ww-live.akamaized.net/pool_01505109/live/ww/bbc_radio_one/bbc_radio_one.isml/bbc_radio_one-audio%3d96000.norewind.m3u8"),
    ("KEXP",                "https://kexp-mp3-128.streamguys1.com/kexp128.mp3"),
]
# fmt: on

MPV_SOCKET = "/tmp/bubuos-radio-sock"


class RadioApp(App):
    """Internet radio player — single-screen UI."""

    name = "BubuRadio"

    def __init__(self, system):
        super().__init__(system)
        self.stations = list(STATIONS)
        self.current_index = 0
        self.playing = False
        self.paused = False

        self._mpv_proc = None
        self._mpv_sock = None

        # Cached metadata from stream
        self._meta_title = ""
        self._meta_query_time = 0

        # Bubu animation
        self._anim_frames = None
        self._anim_frame_idx = 0
        self._anim_tick = 0
        self._anim_dir = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "boombox_anim"
        ))
        # Fallback static image
        self._bubu_img = None
        self._art_path = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "bubu_music.png"
        ))

    # --- Artwork ---

    def _get_bubu_frame(self, renderer):
        """Get current animation frame, or fallback to static image."""
        if self._anim_frames is None:
            self._anim_frames = renderer.load_anim(self._anim_dir, target_h=200)
        if self._anim_frames:
            frame = self._anim_frames[self._anim_frame_idx % len(self._anim_frames)]
            if self.playing and not self.paused:
                self._anim_tick += 1
                if self._anim_tick >= 9:
                    self._anim_tick = 0
                    self._anim_frame_idx += 1
            return frame
        # Fallback to static
        if self._bubu_img is None:
            img = renderer.load_image(self._art_path)
            if img:
                aw, ah = img.get_width(), img.get_height()
                target_h = 200
                if ah != target_h:
                    scale = target_h / ah
                    img = pygame.transform.smoothscale(
                        img, (int(aw * scale), target_h))
                self._bubu_img = img
        return self._bubu_img

    # --- mpv IPC ---

    def _mpv_connect(self):
        for _ in range(30):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(MPV_SOCKET)
                s.setblocking(False)
                self._mpv_sock = s
                return True
            except (ConnectionRefusedError, FileNotFoundError, OSError):
                time.sleep(0.05)
        return False

    def _mpv_send(self, *args):
        if not self._mpv_sock:
            return
        cmd = json.dumps({"command": list(args)}) + "\n"
        try:
            self._mpv_sock.sendall(cmd.encode())
        except OSError:
            self._mpv_sock = None

    def _mpv_get(self, prop):
        if not self._mpv_sock:
            return None
        try:
            while True:
                self._mpv_sock.recv(4096)
        except (BlockingIOError, OSError):
            pass

        rid = int(time.time() * 10000) % 99999
        cmd = json.dumps(
            {"command": ["get_property", prop], "request_id": rid}) + "\n"
        try:
            self._mpv_sock.sendall(cmd.encode())
            self._mpv_sock.setblocking(True)
            self._mpv_sock.settimeout(0.08)
            buf = b""
            deadline = time.time() + 0.08
            while time.time() < deadline:
                try:
                    chunk = self._mpv_sock.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    for line in buf.split(b"\n"):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if (obj.get("request_id") == rid
                                    and obj.get("error") == "success"):
                                self._mpv_sock.setblocking(False)
                                return obj.get("data")
                        except (json.JSONDecodeError, ValueError):
                            pass
                except socket.timeout:
                    break
        except OSError:
            pass
        try:
            self._mpv_sock.setblocking(False)
        except OSError:
            pass
        return None

    # --- Playback ---

    def _play(self, index):
        if index < 0 or index >= len(self.stations):
            return

        self._stop()
        self.current_index = index
        name, url = self.stations[index]

        try:
            os.unlink(MPV_SOCKET)
        except OSError:
            pass

        self._mpv_proc = subprocess.Popen(
            ["mpv", "--no-video", "--no-terminal",
             "--ao=alsa",
             f"--input-ipc-server={MPV_SOCKET}", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        if self._mpv_connect():
            self.playing = True
            self.paused = False
            self._meta_title = ""
            self._meta_query_time = 0
        else:
            self._stop()

    def _stop(self):
        if self._mpv_sock:
            try:
                self._mpv_sock.close()
            except OSError:
                pass
            self._mpv_sock = None
        if self._mpv_proc:
            self._mpv_proc.terminate()
            try:
                self._mpv_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._mpv_proc.kill()
            self._mpv_proc = None
        self.playing = False
        self.paused = False
        self._meta_title = ""

    def _toggle_pause(self):
        if not self.playing:
            return
        self._mpv_send("cycle", "pause")
        self.paused = not self.paused

    def _switch_station(self, delta):
        """Switch to next/prev station with wrap-around."""
        new_idx = (self.current_index + delta) % len(self.stations)
        self._play(new_idx)

    def on_exit(self):
        self._stop()

    def update(self, dt):
        # Check if mpv died
        if self.playing and self._mpv_proc:
            if self._mpv_proc.poll() is not None:
                self._mpv_sock = None
                self._mpv_proc = None
                self.playing = False
                self.paused = False
                self._meta_title = ""

        # Poll metadata every 3 seconds
        if self.playing and self._mpv_sock:
            now = time.time()
            if now - self._meta_query_time > 3:
                title = self._mpv_get("media-title")
                if title and isinstance(title, str):
                    if not title.startswith("http"):
                        self._meta_title = title
                self._meta_query_time = now

    # --- Input ---

    def handle_input(self, action):
        if action == Action.CONFIRM:
            if self.playing:
                self._toggle_pause()
            else:
                self._play(self.current_index)
            return True
        elif action in (Action.LEFT, Action.PAGE_UP):
            self._switch_station(-1)
            return True
        elif action in (Action.RIGHT, Action.PAGE_DOWN):
            self._switch_station(1)
            return True
        elif action == Action.BACK:
            self._stop()
            self.system.back()
            return True
        return False

    # --- Drawing ---

    def draw(self):
        r = self.system.renderer
        _, ch = theme.get_char_size()
        font = theme.get_font()
        font_small = theme.get_font(theme.FONT_SMALL)

        r.draw_statusbar("  BubuRadio", "")

        # Bubu animation
        art = self._get_bubu_frame(r)
        art_y = theme.CONTENT_TOP + 4
        if art:
            art_x = (theme.SCREEN_WIDTH - art.get_width()) // 2
            r.screen.blit(art, (art_x, art_y))
            art_bottom = art_y + art.get_height() + 6
        else:
            r.draw_text("~  R a d i o  ~", theme.SCREEN_WIDTH // 2 - 70,
                        theme.CONTENT_TOP + 60, color=theme.ACCENT)
            art_bottom = theme.CONTENT_TOP + 120

        y = art_bottom

        # Station name
        station_name = self.stations[self.current_index][0]
        max_chars = theme.get_grid_cols() - 2

        if self.paused:
            icon = "[II] "
        elif self.playing:
            icon = "[>] "
        else:
            icon = ""

        full_text = icon + station_name
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars - 3] + "..."

        name_w = font.size(full_text)[0]
        name_x = (theme.SCREEN_WIDTH - name_w) // 2
        r.draw_text(full_text, name_x, y, color=theme.TEXT_COLOR)
        y += ch + 2

        # LIVE / PAUSED badge (only when playing)
        if self.playing:
            live_text = "LIVE" if not self.paused else "PAUSED"
            live_w = font_small.size(live_text)[0]
            badge_x = (theme.SCREEN_WIDTH - live_w) // 2 - 8
            badge_w = live_w + 16
            badge_color = theme.SALMON if not self.paused else theme.WARM_BROWN
            pygame.draw.rect(r.screen, badge_color,
                             (badge_x, y, badge_w, ch))
            r.draw_text(live_text, badge_x + 8, y + 1,
                        color=theme.WHITE, size=theme.FONT_SMALL)
            y += ch + 8

        # Stream metadata
        if self._meta_title:
            meta = self._meta_title
            if len(meta) > max_chars:
                meta = meta[:max_chars - 3] + "..."
            meta_w = font_small.size(meta)[0]
            meta_x = (theme.SCREEN_WIDTH - meta_w) // 2
            r.draw_text(meta, meta_x, y,
                        color=theme.TEXT_DIM, size=theme.FONT_SMALL)
            y += ch + 2

        # Station counter
        track_info = f"< {self.current_index + 1} / {len(self.stations)} >"
        info_w = font_small.size(track_info)[0]
        info_x = (theme.SCREEN_WIDTH - info_w) // 2
        r.draw_text(track_info, info_x, y,
                    color=theme.TEXT_DIM, size=theme.FONT_SMALL)

        if self.playing:
            r.draw_helpbar([
                ("A", "Pause"), ("B", "Exit"), ("L", "Prev"), ("R", "Next"),
            ])
        else:
            r.draw_helpbar([
                ("A", "Play"), ("B", "Exit"), ("L", "Prev"), ("R", "Next"),
            ])
