"""BubuOS Media Player — library, playlists, folders, now-playing.

Uses mpv for audio playback (supports mp3, ogg, flac, wav, aac, wma, m4a).
"""

import os
import json
import random
import socket
import subprocess
import time

import pygame

from core.app import App
from core.input_handler import Action
from core import theme
from core.widgets import ScrollList, ContextMenu, ConfirmDialog
from apps.mediaplayer.playlists import (
    list_playlists, load_playlist, save_playlist, delete_playlist,
)


AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".aac", ".wma", ".m4a"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".webm", ".mov"}
MEDIA_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

VIEW_LIBRARY = 0
VIEW_TRACKS = 1
VIEW_PLAYLIST = 2
VIEW_NOW_PLAYING = 3

MPV_SOCKET = "/tmp/bubuos-mpv-sock"

# Entry types in library list
_TYPE_ALL_MUSIC = "all"
_TYPE_PLAYLIST = "pl"
_TYPE_FOLDER = "dir"
_TYPE_SEP = "sep"


class MediaPlayerApp(App):
    """Media player with library, playlists, folders, and now-playing."""

    name = "BubuPlayer"

    def __init__(self, system, file_path=None):
        super().__init__(system)
        self._music_dir = os.path.join(system.data_dir, "music")
        self._playlists_dir = os.path.join(system.data_dir, "playlists")

        # Playback state
        self.playlist = []          # current working track list (paths)
        self.playlist_display = []  # display names for track_list
        self.current_index = -1
        self.playing = False
        self.paused = False
        self.shuffle = False
        self._opened_from_file = file_path is not None

        # Views
        self.view = VIEW_LIBRARY
        self._return_view = VIEW_LIBRARY  # where B returns from NOW_PLAYING

        # Library
        self._library_entries = []  # [(type, label, data), ...]
        self._library_list = ScrollList()

        # Tracks (folder / all music)
        self._tracks_label = ""
        self._track_list = ScrollList()

        # Playlist detail
        self._pl_name = ""
        self._pl_path = ""
        self._pl_tracks = []
        self._pl_list = ScrollList()

        # Overlays
        self._context_menu = None
        self._confirm_dialog = None

        # mpv process and IPC
        self._mpv_proc = None
        self._mpv_sock = None
        self._video_proc = None
        self._cached_pos = 0
        self._cached_dur = 0
        self._pos_query_time = 0
        self._last_query_tick = 0

        # Bubu animation
        self._anim_frames = None
        self._anim_frame_idx = 0
        self._anim_tick = 0
        self._anim_dir = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "drumm_anim"
        ))
        self._bubu_img = None
        self._art_path = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "..", "assets", "bubu_music.png"
        ))

        # If opened from file manager with a specific file
        if file_path:
            self._load_tracks_from_dir(os.path.dirname(file_path))
            for i, p in enumerate(self.playlist):
                if p == file_path:
                    self.current_index = i
                    self._track_list.selected = i
                    break
            if self.current_index >= 0:
                self._play(self.current_index)
        else:
            self._load_library()

    # ----------------------------------------------------------------
    # Library
    # ----------------------------------------------------------------

    def _load_library(self):
        """Build the library list: All Music + playlists + folders."""
        entries = []

        # Count all music files
        music_count = self._count_music_files(self._music_dir)
        entries.append((_TYPE_ALL_MUSIC, "All Music", None, music_count))

        # Playlists
        pls = list_playlists(self._playlists_dir)
        if pls:
            entries.append((_TYPE_SEP, "--- Playlists ---", None, None))
            for name, path in pls:
                tracks = load_playlist(path)
                entries.append((_TYPE_PLAYLIST, f"[PL] {name}", path, len(tracks)))

        # Subfolders in music dir
        folders = self._get_subfolders(self._music_dir)
        if folders:
            entries.append((_TYPE_SEP, "--- Folders ---", None, None))
            for fname, fpath in folders:
                cnt = self._count_music_files(fpath)
                entries.append((_TYPE_FOLDER, f"[FLD] {fname}", fpath, cnt))

        self._library_entries = entries
        display = [e[1] for e in entries]
        self._library_list.set_items(display)
        # Skip separator if selected
        self._skip_separators(self._library_list, 1)

    def _count_music_files(self, directory):
        try:
            return sum(1 for f in os.listdir(directory)
                       if os.path.splitext(f)[1].lower() in MEDIA_EXTENSIONS
                       and not f.startswith("."))
        except OSError:
            return 0

    def _get_subfolders(self, directory):
        try:
            result = []
            for name in sorted(os.listdir(directory)):
                if name.startswith("."):
                    continue
                full = os.path.join(directory, name)
                if os.path.isdir(full):
                    result.append((name, full))
            return result
        except OSError:
            return []

    def _skip_separators(self, scroll_list, direction):
        """Move selection past separator entries."""
        while (0 <= scroll_list.selected < len(self._library_entries)
               and self._library_entries[scroll_list.selected][0] == _TYPE_SEP):
            scroll_list.selected += direction
        scroll_list.selected = max(0, min(scroll_list.selected,
                                          len(self._library_entries) - 1))

    # ----------------------------------------------------------------
    # Track loading
    # ----------------------------------------------------------------

    def _load_tracks_from_dir(self, directory):
        """Load media files from a directory into the working playlist."""
        self.playlist = []
        self.playlist_display = []
        try:
            files = sorted(os.listdir(directory))
        except OSError:
            files = []
        for name in files:
            if name.startswith("."):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in MEDIA_EXTENSIONS:
                full = os.path.join(directory, name)
                self.playlist.append(full)
                icon = "[VID]" if ext in VIDEO_EXTENSIONS else "[AUD]"
                self.playlist_display.append(f"{icon} {name}")
        self._track_list.set_items(self.playlist_display)

    def _load_playlist_detail(self, name, path):
        """Load a saved playlist for viewing/editing."""
        self._pl_name = name
        self._pl_path = path
        self._pl_tracks = load_playlist(path)
        display = []
        for track_path in self._pl_tracks:
            fname = os.path.basename(track_path)
            ext = os.path.splitext(fname)[1].lower()
            icon = "[VID]" if ext in VIDEO_EXTENSIONS else "[AUD]"
            display.append(f"{icon} {fname}")
        self._pl_list.set_items(display)

    def _play_from_playlist_detail(self, index):
        """Start playback from the saved playlist view."""
        # Filter out missing files
        valid = [(i, p) for i, p in enumerate(self._pl_tracks) if os.path.isfile(p)]
        if not valid:
            return
        self.playlist = [p for _, p in valid]
        self.playlist_display = []
        for p in self.playlist:
            fname = os.path.basename(p)
            ext = os.path.splitext(fname)[1].lower()
            icon = "[VID]" if ext in VIDEO_EXTENSIONS else "[AUD]"
            self.playlist_display.append(f"{icon} {fname}")
        # Find position in filtered list
        play_idx = 0
        if index < len(self._pl_tracks):
            target = self._pl_tracks[index]
            for i, p in enumerate(self.playlist):
                if p == target:
                    play_idx = i
                    break
        self._return_view = VIEW_PLAYLIST
        self._play(play_idx)

    # ----------------------------------------------------------------
    # Bubu artwork
    # ----------------------------------------------------------------

    def _get_bubu_frame(self, renderer):
        if self._anim_frames is None:
            self._anim_frames = renderer.load_anim(self._anim_dir, target_h=230)
        if self._anim_frames:
            frame = self._anim_frames[self._anim_frame_idx % len(self._anim_frames)]
            if self.playing and not self.paused:
                self._anim_tick += 1
                if self._anim_tick >= 3:
                    self._anim_tick = 0
                    self._anim_frame_idx += 1
            return frame
        if self._bubu_img is None:
            img = renderer.load_image(self._art_path)
            if img:
                aw, ah = img.get_width(), img.get_height()
                target_h = 230
                scale = target_h / ah
                self._bubu_img = pygame.transform.smoothscale(
                    img, (int(aw * scale), target_h))
        return self._bubu_img

    # ----------------------------------------------------------------
    # mpv IPC (unchanged)
    # ----------------------------------------------------------------

    def _mpv_connect(self):
        for _ in range(20):
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

    # ----------------------------------------------------------------
    # Playback control
    # ----------------------------------------------------------------

    def _play(self, index):
        if index < 0 or index >= len(self.playlist):
            return
        self._stop()
        self.current_index = index
        path = self.playlist[index]
        ext = os.path.splitext(path)[1].lower()

        if ext in VIDEO_EXTENSIONS:
            try:
                self._video_proc = subprocess.Popen(
                    ["mpv", "--fs", "--no-terminal", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self.playing = True
            except FileNotFoundError:
                pass
            return

        try:
            os.unlink(MPV_SOCKET)
        except OSError:
            pass

        self._mpv_proc = subprocess.Popen(
            ["mpv", "--no-video", "--no-terminal",
             "--ao=alsa",
             f"--input-ipc-server={MPV_SOCKET}", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        if self._mpv_connect():
            self.playing = True
            self.paused = False
            self._cached_pos = 0
            self._cached_dur = 0
            self._pos_query_time = time.time()
            self._last_query_tick = 0
            self.view = VIEW_NOW_PLAYING
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
                self._mpv_proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._mpv_proc.kill()
            self._mpv_proc = None
        if self._video_proc:
            self._video_proc.terminate()
            self._video_proc = None
        self.playing = False
        self.paused = False
        self._cached_pos = 0
        self._cached_dur = 0

    def _toggle_pause(self):
        if not self.playing:
            return
        self._mpv_send("cycle", "pause")
        self.paused = not self.paused
        if self.paused:
            self._cached_pos = self._get_elapsed()
            self._pos_query_time = time.time()

    def _current_name(self):
        if 0 <= self.current_index < len(self.playlist):
            return os.path.basename(self.playlist[self.current_index])
        return ""

    def _get_elapsed(self):
        now = time.time()
        if self._mpv_sock and now - self._last_query_tick > 0.5:
            pos = self._mpv_get("time-pos")
            if pos is not None:
                self._cached_pos = float(pos)
                self._pos_query_time = now
            self._last_query_tick = now
        if self.paused:
            return self._cached_pos
        return self._cached_pos + (now - self._pos_query_time)

    def _get_duration(self):
        if self._cached_dur > 0:
            return self._cached_dur
        if self._mpv_sock:
            dur = self._mpv_get("duration")
            if dur is not None:
                self._cached_dur = float(dur)
        return self._cached_dur

    def _next_index(self, direction):
        """Return next track index (or None if at end). direction: 1 or -1."""
        if not self.playlist:
            return None
        if self.shuffle:
            if len(self.playlist) == 1:
                return 0
            candidates = [i for i in range(len(self.playlist)) if i != self.current_index]
            return random.choice(candidates)
        nxt = self.current_index + direction
        if 0 <= nxt < len(self.playlist):
            return nxt
        return None

    def on_exit(self):
        self._stop()

    def update(self, dt):
        # Check if audio track ended → auto-advance
        if self.playing and self._mpv_proc:
            if self._mpv_proc.poll() is not None:
                self._mpv_sock = None
                self._mpv_proc = None
                nxt = self._next_index(1)
                if nxt is not None:
                    self._play(nxt)
                else:
                    self.playing = False
                    self.paused = False
                    self.view = self._return_view

        if self._video_proc and self._video_proc.poll() is not None:
            self._video_proc = None
            self.playing = False

    # ----------------------------------------------------------------
    # Input dispatch
    # ----------------------------------------------------------------

    def handle_input(self, action):
        # Overlays first
        if self._confirm_dialog and self._confirm_dialog.active:
            return self._confirm_dialog.handle_input(action)
        if self._context_menu and self._context_menu.active:
            return self._context_menu.handle_input(action)

        if self.view == VIEW_LIBRARY:
            return self._handle_library(action)
        elif self.view == VIEW_TRACKS:
            return self._handle_tracks(action)
        elif self.view == VIEW_PLAYLIST:
            return self._handle_playlist_detail(action)
        elif self.view == VIEW_NOW_PLAYING:
            return self._handle_now_playing(action)
        return False

    # --- Library input ---

    def _handle_library(self, action):
        if action in (Action.UP, Action.DOWN, Action.PAGE_UP, Action.PAGE_DOWN):
            old = self._library_list.selected
            self._library_list.handle_input(action)
            # Skip separators
            if self._library_list.selected < len(self._library_entries):
                if self._library_entries[self._library_list.selected][0] == _TYPE_SEP:
                    direction = 1 if action in (Action.DOWN, Action.PAGE_DOWN) else -1
                    self._library_list.selected += direction
                    self._library_list.selected = max(
                        0, min(self._library_list.selected,
                               len(self._library_entries) - 1))
                    # If still on separator, revert
                    if self._library_entries[self._library_list.selected][0] == _TYPE_SEP:
                        self._library_list.selected = old
                    self._library_list._adjust_scroll()
            return True

        if action == Action.CONFIRM:
            self._open_library_item()
            return True
        elif action == Action.BACK:
            self._stop()
            self.system.back()
            return True
        elif action == Action.MENU:  # X → go to now playing
            if self.playing:
                self._return_view = VIEW_LIBRARY
                self.view = VIEW_NOW_PLAYING
            return True
        elif action == Action.DELETE:  # Y → delete playlist
            self._delete_library_item()
            return True
        elif action == Action.SYSTEM:  # Start → new playlist
            self._create_new_playlist()
            return True
        return False

    def _open_library_item(self):
        idx = self._library_list.selected
        if idx >= len(self._library_entries):
            return
        kind, _, data, _ = self._library_entries[idx]
        if kind == _TYPE_ALL_MUSIC:
            self._load_tracks_from_dir(self._music_dir)
            self._tracks_label = "All Music"
            self.view = VIEW_TRACKS
        elif kind == _TYPE_FOLDER:
            self._load_tracks_from_dir(data)
            self._tracks_label = os.path.basename(data)
            self.view = VIEW_TRACKS
        elif kind == _TYPE_PLAYLIST:
            name = os.path.splitext(os.path.basename(data))[0]
            self._load_playlist_detail(name, data)
            self.view = VIEW_PLAYLIST

    def _delete_library_item(self):
        idx = self._library_list.selected
        if idx >= len(self._library_entries):
            return
        kind, _, data, _ = self._library_entries[idx]
        if kind != _TYPE_PLAYLIST:
            return
        name = os.path.splitext(os.path.basename(data))[0]
        self._confirm_dialog = ConfirmDialog(
            "Delete Playlist",
            f"Delete '{name}'?",
            on_confirm=lambda: self._do_delete_playlist(data),
        )
        self._confirm_dialog.open()

    def _do_delete_playlist(self, path):
        delete_playlist(path)
        self._load_library()

    def _create_new_playlist(self):
        self.system.open_keyboard(self._on_new_playlist_name,
                                  title="Playlist name:")

    def _on_new_playlist_name(self, name):
        if name and name.strip():
            path = os.path.join(self._playlists_dir, f"{name.strip()}.json")
            save_playlist(path, [])
            self._load_library()

    # --- Tracks input (folder / all music) ---

    def _handle_tracks(self, action):
        if self._track_list.handle_input(action):
            return True

        if action == Action.CONFIRM:
            if self.playlist:
                self._return_view = VIEW_TRACKS
                self._play(self._track_list.selected)
            return True
        elif action == Action.BACK:
            self._load_library()
            self.view = VIEW_LIBRARY
            return True
        elif action == Action.MENU:  # X → add to playlist
            self._show_add_to_playlist_menu()
            return True
        return False

    def _show_add_to_playlist_menu(self):
        idx = self._track_list.selected
        if idx < 0 or idx >= len(self.playlist):
            return
        track_path = self.playlist[idx]
        pls = list_playlists(self._playlists_dir)
        options = []
        for name, pl_path in pls:
            options.append((name, lambda p=pl_path, t=track_path: self._add_track_to(p, t)))
        options.append(("+ New playlist", lambda t=track_path: self._add_track_new(t)))
        self._context_menu = ContextMenu(options)
        self._context_menu.open()

    def _add_track_to(self, pl_path, track_path):
        tracks = load_playlist(pl_path)
        if track_path not in tracks:
            tracks.append(track_path)
            save_playlist(pl_path, tracks)

    def _add_track_new(self, track_path):
        self.system.open_keyboard(
            lambda name, t=track_path: self._on_new_pl_with_track(name, t),
            title="Playlist name:")

    def _on_new_pl_with_track(self, name, track_path):
        if name and name.strip():
            path = os.path.join(self._playlists_dir, f"{name.strip()}.json")
            save_playlist(path, [track_path])

    # --- Playlist detail input ---

    def _handle_playlist_detail(self, action):
        if self._pl_list.handle_input(action):
            return True

        if action == Action.CONFIRM:
            if self._pl_tracks:
                self._play_from_playlist_detail(self._pl_list.selected)
            return True
        elif action == Action.BACK:
            self._load_library()
            self.view = VIEW_LIBRARY
            return True
        elif action == Action.MENU:  # X → rename playlist
            self.system.open_keyboard(
                self._on_rename_playlist,
                initial_text=self._pl_name,
                title="Rename playlist:")
            return True
        elif action == Action.DELETE:  # Y → remove track
            self._remove_track_from_playlist()
            return True
        elif action == Action.SYSTEM:  # Start → now playing
            if self.playing:
                self._return_view = VIEW_PLAYLIST
                self.view = VIEW_NOW_PLAYING
            return True
        return False

    def _on_rename_playlist(self, new_name):
        if not new_name or not new_name.strip():
            return
        new_name = new_name.strip()
        new_path = os.path.join(self._playlists_dir, f"{new_name}.json")
        if new_path != self._pl_path:
            tracks = load_playlist(self._pl_path)
            save_playlist(new_path, tracks)
            delete_playlist(self._pl_path)
            self._pl_name = new_name
            self._pl_path = new_path

    def _remove_track_from_playlist(self):
        idx = self._pl_list.selected
        if idx < 0 or idx >= len(self._pl_tracks):
            return
        fname = os.path.basename(self._pl_tracks[idx])
        self._confirm_dialog = ConfirmDialog(
            "Remove Track",
            f"Remove '{fname}'?",
            on_confirm=lambda: self._do_remove_track(idx),
        )
        self._confirm_dialog.open()

    def _do_remove_track(self, idx):
        if idx < len(self._pl_tracks):
            self._pl_tracks.pop(idx)
            save_playlist(self._pl_path, self._pl_tracks)
            self._load_playlist_detail(self._pl_name, self._pl_path)

    # --- Now Playing input (mostly unchanged) ---

    def _handle_now_playing(self, action):
        if action == Action.CONFIRM:
            self._toggle_pause()
            return True
        elif action == Action.BACK:
            if self._opened_from_file:
                self._stop()
                self.system.back()
            else:
                self.view = self._return_view
            return True
        elif action == Action.MENU:
            self._stop()
            if self._opened_from_file:
                self.system.back()
            else:
                self.view = self._return_view
            return True
        elif action == Action.DELETE:  # Y → toggle shuffle
            self.shuffle = not self.shuffle
            return True
        elif action == Action.PAGE_UP:
            nxt = self._next_index(-1)
            if nxt is not None:
                self._play(nxt)
            return True
        elif action == Action.PAGE_DOWN:
            nxt = self._next_index(1)
            if nxt is not None:
                self._play(nxt)
            return True
        elif action == Action.LEFT:
            self._mpv_send("seek", -10)
            self._cached_pos = max(0, self._cached_pos - 10)
            self._pos_query_time = time.time()
            return True
        elif action == Action.RIGHT:
            self._mpv_send("seek", 10)
            self._cached_pos += 10
            self._pos_query_time = time.time()
            return True
        return False

    # ----------------------------------------------------------------
    # Drawing
    # ----------------------------------------------------------------

    def draw(self):
        r = self.system.renderer
        if self.view == VIEW_LIBRARY:
            self._draw_library(r)
        elif self.view == VIEW_TRACKS:
            self._draw_tracks(r)
        elif self.view == VIEW_PLAYLIST:
            self._draw_playlist_detail(r)
        elif self.view == VIEW_NOW_PLAYING:
            self._draw_now_playing(r)

        # Overlays on top
        if self._context_menu and self._context_menu.active:
            self._context_menu.draw(r)
        if self._confirm_dialog and self._confirm_dialog.active:
            self._confirm_dialog.draw(r)

    def _draw_library(self, r):
        _, ch = theme.get_char_size()

        status = ""
        if self.playing:
            status = self._current_name()
        r.draw_statusbar("  Media Player", status)

        y = theme.CONTENT_TOP + 4
        self._library_list.max_visible = (theme.CONTENT_BOTTOM - y) // ch

        vis_start = self._library_list.scroll_offset
        vis_end = min(len(self._library_entries),
                      vis_start + self._library_list.max_visible)

        font = theme.get_font()
        draw_y = y
        for i in range(vis_start, vis_end):
            kind, label, _, count = self._library_entries[i]
            if kind == _TYPE_SEP:
                r.draw_text(label, theme.PADDING, draw_y,
                            color=theme.TEXT_DIM, size=theme.FONT_SMALL)
            elif i == self._library_list.selected:
                r.draw_row(label, draw_y,
                           fg=theme.HIGHLIGHT_TEXT, bg=theme.HIGHLIGHT_BG)
                if count is not None:
                    ct = str(count)
                    cw = font.size(ct)[0]
                    r.draw_text(ct, theme.SCREEN_WIDTH - theme.PADDING - cw,
                                draw_y, color=theme.HIGHLIGHT_TEXT)
            else:
                r.draw_row(label, draw_y, fg=theme.TEXT_COLOR)
                if count is not None:
                    ct = str(count)
                    cw = font.size(ct)[0]
                    r.draw_text(ct, theme.SCREEN_WIDTH - theme.PADDING - cw,
                                draw_y, color=theme.TEXT_DIM)
            draw_y += ch

        help_items = [("A", "Open"), ("B", "Back"), ("Str", "New PL")]
        if self.playing:
            help_items.insert(2, ("X", "Now"))
        r.draw_helpbar(help_items)

    def _draw_tracks(self, r):
        _, ch = theme.get_char_size()

        status = self._tracks_label
        if self.playing:
            status = self._current_name()
        r.draw_statusbar("  Media Player", status)

        y = theme.CONTENT_TOP + 4
        info = f"{len(self.playlist)} tracks"
        r.draw_text(info, theme.PADDING, y, color=theme.ACCENT)
        y += ch + 4

        if not self.playlist:
            r.draw_text("No media files.", theme.PADDING, y,
                        color=theme.TEXT_DIM)
        else:
            self._track_list.max_visible = (theme.CONTENT_BOTTOM - y) // ch
            vis_start = self._track_list.scroll_offset
            vis_end = min(len(self.playlist_display),
                          vis_start + self._track_list.max_visible)
            draw_y = y
            for i in range(vis_start, vis_end):
                text = self.playlist_display[i]
                if i == self._track_list.selected:
                    r.draw_row(text, draw_y,
                               fg=theme.HIGHLIGHT_TEXT, bg=theme.HIGHLIGHT_BG)
                elif i == self.current_index:
                    r.draw_row(text, draw_y,
                               fg=theme.SOFT_GREEN, bg=theme.BG_COLOR)
                else:
                    r.draw_row(text, draw_y, fg=theme.TEXT_COLOR)
                draw_y += ch

        r.draw_helpbar([("A", "Play"), ("B", "Back"), ("X", "+Playlist")])

    def _draw_playlist_detail(self, r):
        _, ch = theme.get_char_size()

        r.draw_statusbar("  Media Player", self._pl_name)

        y = theme.CONTENT_TOP + 4
        info = f"{len(self._pl_tracks)} tracks"
        r.draw_text(info, theme.PADDING, y, color=theme.ACCENT)
        y += ch + 4

        if not self._pl_tracks:
            r.draw_text("Playlist is empty.", theme.PADDING, y,
                        color=theme.TEXT_DIM)
            r.draw_text("Add tracks from All Music.", theme.PADDING, y + ch,
                        color=theme.TEXT_DIM, size=theme.FONT_SMALL)
        else:
            self._pl_list.max_visible = (theme.CONTENT_BOTTOM - y) // ch
            vis_start = self._pl_list.scroll_offset
            vis_end = min(len(self._pl_tracks),
                          vis_start + self._pl_list.max_visible)
            draw_y = y
            for i in range(vis_start, vis_end):
                display = self._pl_list.items[i] if i < len(self._pl_list.items) else ""
                if i == self._pl_list.selected:
                    r.draw_row(display, draw_y,
                               fg=theme.HIGHLIGHT_TEXT, bg=theme.HIGHLIGHT_BG)
                elif i == self.current_index:
                    r.draw_row(display, draw_y,
                               fg=theme.SOFT_GREEN, bg=theme.BG_COLOR)
                else:
                    r.draw_row(display, draw_y, fg=theme.TEXT_COLOR)
                draw_y += ch

        r.draw_helpbar([
            ("A", "Play"), ("B", "Back"), ("X", "Rename"), ("Y", "Del"),
        ])

    def _draw_now_playing(self, r):
        _, ch = theme.get_char_size()
        font = theme.get_font()
        font_small = theme.get_font(theme.FONT_SMALL)

        r.draw_statusbar("  Now Playing", "")

        art = self._get_bubu_frame(r)
        art_y = theme.CONTENT_TOP + 4
        if art:
            art_x = (theme.SCREEN_WIDTH - art.get_width()) // 2
            r.screen.blit(art, (art_x, art_y))
            art_bottom = art_y + art.get_height() + 6
        else:
            r.draw_text("~  B u b u  ~", theme.SCREEN_WIDTH // 2 - 60,
                        theme.CONTENT_TOP + 60, color=theme.ACCENT)
            art_bottom = theme.CONTENT_TOP + 120

        y = art_bottom
        name = self._current_name()
        display_name = os.path.splitext(name)[0] if name else "No track"

        if self.paused:
            icon = "[II] "
        elif self.playing:
            icon = "[>] "
        else:
            icon = "[x] "

        full_text = icon + display_name
        max_chars = theme.get_grid_cols() - 2
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars - 3] + "..."

        name_w = font.size(full_text)[0]
        name_x = (theme.SCREEN_WIDTH - name_w) // 2
        r.draw_text(full_text, name_x, y, color=theme.TEXT_COLOR)
        y += ch + 2

        track_info = f"{self.current_index + 1} / {len(self.playlist)}"
        info_w = font_small.size(track_info)[0]
        info_x = (theme.SCREEN_WIDTH - info_w) // 2
        r.draw_text(track_info, info_x, y, color=theme.TEXT_DIM,
                    size=theme.FONT_SMALL)
        y += ch + 4

        elapsed = self._get_elapsed()
        duration = self._get_duration()

        bar_margin = 40
        bar_x = bar_margin
        bar_w = theme.SCREEN_WIDTH - bar_margin * 2
        bar_h = 8
        bar_y = y + 4

        pygame.draw.rect(r.screen, theme.WARM_BROWN,
                         (bar_x, bar_y, bar_w, bar_h), 1)

        if duration > 0:
            fill_pct = min(1.0, elapsed / duration)
        elif elapsed > 0:
            fill_pct = min(1.0, elapsed / max(elapsed + 30, 180))
        else:
            fill_pct = 0

        fill_w = int(bar_w * fill_pct)
        if fill_w > 0:
            pygame.draw.rect(r.screen, theme.SALMON,
                             (bar_x + 1, bar_y + 1, fill_w - 2, bar_h - 2))

        y = bar_y + bar_h + 4

        elapsed_str = self._format_time(elapsed)
        if duration > 0:
            remaining_str = f"-{self._format_time(max(0, duration - elapsed))}"
        else:
            remaining_str = "--:--"

        r.draw_text(elapsed_str, bar_x, y, color=theme.TEXT_DIM,
                    size=theme.FONT_SMALL)
        rem_w = font_small.size(remaining_str)[0]
        r.draw_text(remaining_str, bar_x + bar_w - rem_w, y,
                    color=theme.TEXT_DIM, size=theme.FONT_SMALL)

        shfl = "Shfl ON" if self.shuffle else "Shfl"
        r.draw_helpbar([
            ("A", "Pause"), ("B", "List"), ("Y", shfl),
            ("L", "Prev"), ("R", "Next"),
        ])

    @staticmethod
    def _format_time(seconds):
        s = int(max(0, seconds))
        return f"{s // 60:02d}:{s % 60:02d}"
