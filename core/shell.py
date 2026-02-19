"""BubuOS Shell — main screen with file browser and app launcher."""

import os
import shutil
import subprocess
import datetime
import time
import threading
from core.app import App
from core.input_handler import Action
from core import theme
from core.widgets import ScrollList, ContextMenu


class Shell(App):
    """The main BubuOS shell — three tabs: Files, Apps, Settings."""

    name = "BubuOS"

    # Tabs
    TAB_FILES = 0
    TAB_APPS = 1
    TAB_SETTINGS = 2
    TAB_NAMES = ["Folders", "Apps", "Settings"]

    def __init__(self, system):
        super().__init__(system)
        self.current_tab = self.TAB_FILES
        self._active_dialog = None

        # Icon path for status bar
        self._icon_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "assets", "bubu_icon.png"
        )

        # Status cache (avoid subprocess every frame)
        self._wifi_cache = None
        self._wifi_cache_time = 0
        self._bt_cache = None
        self._bt_cache_time = 0
        self._STATUS_INTERVAL = 5  # seconds between status checks
        self._files_refresh_time = 0
        self._FILES_REFRESH_INTERVAL = 3  # seconds between file count refreshes

        # Calendar event indicator
        self._cal_pending = False
        self._cal_cache_time = 0
        self._cal_blink = True
        self._cal_blink_time = 0

        # File browser state
        self.current_dir = system.data_dir
        self.file_list = ScrollList()
        self.file_entries = []  # list of (display_name, full_path, is_dir)

        # App launcher state
        self.app_list = ScrollList()
        self.app_entries = []  # list of (display_name, app_class)

        # Settings list state
        self.settings_list = ScrollList()
        self.settings_entries = []

        # Context menu
        self.context_menu = ContextMenu([])

        self._load_files()
        self._load_apps()
        self._load_settings()

    def on_enter(self):
        self._load_files()

    def update(self, dt):
        now = time.time()

        # Blink toggle (0.7s on, 0.7s off)
        if now - self._cal_blink_time >= 0.7:
            self._cal_blink_time = now
            self._cal_blink = not self._cal_blink

        # Refresh calendar pending status every 10s
        if now - self._cal_cache_time >= 10:
            self._cal_cache_time = now
            try:
                from apps.calendar.app import has_pending_today
                events_path = os.path.join(
                    self.system.data_dir, "calendar", "events.json")
                self._cal_pending = has_pending_today(events_path)
            except Exception:
                self._cal_pending = False

        if self.current_tab != self.TAB_FILES:
            return
        if now - self._files_refresh_time < self._FILES_REFRESH_INTERVAL:
            return
        self._files_refresh_time = now
        self._refresh_counts()

    def _load_files(self):
        """Scan current directory and populate the file list."""
        self.file_entries = []

        if self.current_dir != self.system.data_dir:
            self.file_entries.append(("[..] Parent directory", os.path.dirname(self.current_dir), True, None))

        try:
            entries = sorted(os.listdir(self.current_dir))
        except PermissionError:
            entries = []

        dirs = []
        files = []
        for name in entries:
            if name.startswith("."):
                continue
            full = os.path.join(self.current_dir, name)
            if os.path.isdir(full):
                if self.current_dir == self.system.data_dir and name in ("playlists", "calendar"):
                    continue
                try:
                    cnt = len([f for f in os.listdir(full) if not f.startswith(".")])
                except OSError:
                    cnt = 0
                dirs.append((f"[FLD] {name}", full, True, cnt))
            else:
                ext = os.path.splitext(name)[1].lower()
                icon = self._file_icon(ext)
                files.append((f"{icon} {name}", full, False, None))

        self.file_entries.extend(dirs)
        self.file_entries.extend(files)

        # Show Trash at the end when at root data directory
        if self.current_dir == self.system.data_dir:
            trash_dir = self._get_trash_dir()
            try:
                trash_count = len(os.listdir(trash_dir))
            except OSError:
                trash_count = 0
            self.file_entries.append((f"[TRS] Trash", trash_dir, True, trash_count))

        display = [e[0] for e in self.file_entries]
        self.file_list.set_items(display)

    def _refresh_counts(self):
        """Update folder counts in-place without resetting selection."""
        changed = False
        for i, (label, path, is_dir, count) in enumerate(self.file_entries):
            if not is_dir or count is None:
                continue
            try:
                new_cnt = len([f for f in os.listdir(path) if not f.startswith(".")])
            except OSError:
                new_cnt = 0
            if new_cnt != count:
                self.file_entries[i] = (label, path, is_dir, new_cnt)
                changed = True
        if changed:
            # Also check if new files/folders appeared
            self._load_files()

    def _file_icon(self, ext):
        icons = {
            ".txt": "[TXT]",
            ".md": "[TXT]",
            ".py": "[PY ]",
            ".mp3": "[MUS]",
            ".wav": "[MUS]",
            ".ogg": "[MUS]",
            ".flac": "[MUS]",
            ".mp4": "[VID]",
            ".avi": "[VID]",
            ".mkv": "[VID]",
            ".png": "[IMG]",
            ".jpg": "[IMG]",
            ".jpeg": "[IMG]",
            ".bmp": "[IMG]",
        }
        return icons.get(ext, "[   ]")

    def _load_apps(self):
        """Register available applications."""
        self.app_entries = [
            ("BubuText", "editor"),
            ("BubuPlayer", "mediaplayer"),
            ("BubuRadio", "radio"),
            ("BubuWeather", "weather"),
            ("BubuBrowser", "browser"),
            ("Calendar", "calendar"),
            ("Snake", "snake"),
        ]
        self.app_list.set_items([e[0] for e in self.app_entries])

    def _load_settings(self):
        """Register settings entries."""
        snd = "ON" if self.system.sfx.enabled else "OFF"
        self.settings_entries = [
            ("WiFi", "wifi"),
            ("Bluetooth", "bluetooth"),
            (f"Sound: {snd}", "sound_toggle"),
            ("System", "about"),
        ]
        self.settings_list.set_items([e[0] for e in self.settings_entries])

    def _open_file(self, path):
        """Open a file with the appropriate app based on extension."""
        ext = os.path.splitext(path)[1].lower()

        if ext in (".txt", ".md", ".py", ".cfg", ".ini", ".json", ".log"):
            from apps.editor.app import EditorApp
            editor = EditorApp(self.system, path)
            self.system.open_app(editor)
        elif ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif"):
            from apps.imageviewer.app import ImageViewerApp
            viewer = ImageViewerApp(self.system, path)
            self.system.open_app(viewer)
        elif ext in (".mp3", ".wav", ".ogg", ".flac", ".mp4", ".avi", ".mkv"):
            from apps.mediaplayer.app import MediaPlayerApp
            player = MediaPlayerApp(self.system, path)
            self.system.open_app(player)

    def _launch_app(self, app_key):
        """Launch a registered application."""
        if app_key == "editor":
            from apps.editor.app import EditorApp
            editor = EditorApp(self.system)
            self.system.open_app(editor)
        elif app_key == "mediaplayer":
            from apps.mediaplayer.app import MediaPlayerApp
            player = MediaPlayerApp(self.system)
            self.system.open_app(player)
        elif app_key == "browser":
            from apps.browser.app import BrowserApp
            browser = BrowserApp(self.system)
            self.system.open_app(browser)
        elif app_key == "wifi":
            from apps.wifi.app import WiFiApp
            wifi = WiFiApp(self.system)
            self.system.open_app(wifi)
        elif app_key == "bluetooth":
            from apps.bluetooth.app import BluetoothApp
            bt = BluetoothApp(self.system)
            self.system.open_app(bt)
        elif app_key == "radio":
            from apps.radio.app import RadioApp
            radio = RadioApp(self.system)
            self.system.open_app(radio)
        elif app_key == "weather":
            from apps.weather.app import WeatherApp
            self.system.open_app(WeatherApp(self.system))
        elif app_key == "calendar":
            from apps.calendar.app import CalendarApp
            self.system.open_app(CalendarApp(self.system))
        elif app_key == "snake":
            from apps.snake.app import SnakeApp
            snake = SnakeApp(self.system)
            self.system.open_app(snake)
        elif app_key == "about":
            from apps.about.app import AboutApp
            about = AboutApp(self.system)
            self.system.open_app(about)

    def _get_wifi_status(self):
        """Get current WiFi connection status (cached)."""
        now = time.time()
        if now - self._wifi_cache_time < self._STATUS_INTERVAL:
            return self._wifi_cache
        self._wifi_cache_time = now
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
                capture_output=True, text=True, timeout=2
            )
            for line in result.stdout.strip().split("\n"):
                if line.startswith("yes:"):
                    self._wifi_cache = line.split(":", 1)[1]
                    return self._wifi_cache
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        self._wifi_cache = None
        return None

    def _get_bt_status(self):
        """Check if any Bluetooth device is connected (cached). Returns device name or None."""
        now = time.time()
        if now - self._bt_cache_time < self._STATUS_INTERVAL:
            return self._bt_cache
        self._bt_cache_time = now
        try:
            result = subprocess.run(
                ["bluetoothctl", "devices", "Connected"],
                capture_output=True, text=True, timeout=2,
            )
            for line in result.stdout.strip().split("\n"):
                if line.startswith("Device "):
                    parts = line.split(" ", 2)
                    if len(parts) >= 3:
                        self._bt_cache = parts[2]
                        return self._bt_cache
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        self._bt_cache = None
        return None

    def handle_input(self, action):
        # Confirm dialog takes highest priority
        if hasattr(self, "_active_dialog") and self._active_dialog and self._active_dialog.active:
            return self._active_dialog.handle_input(action)

        # Context menu takes priority
        if self.context_menu.active:
            return self.context_menu.handle_input(action)

        # Tab switching with D-pad Left/Right
        if action == Action.LEFT:
            self.current_tab = (self.current_tab - 1) % len(self.TAB_NAMES)
            return True
        elif action == Action.RIGHT:
            self.current_tab = (self.current_tab + 1) % len(self.TAB_NAMES)
            return True

        # Select → open Calendar from any tab
        if action == Action.SWITCH_LAYOUT:
            from apps.calendar.app import CalendarApp
            self.system.open_app(CalendarApp(self.system))
            return True

        if self.current_tab == self.TAB_FILES:
            return self._handle_files_input(action)
        elif self.current_tab == self.TAB_APPS:
            return self._handle_apps_input(action)
        else:
            return self._handle_settings_input(action)

    def _handle_files_input(self, action):
        if self.file_list.handle_input(action):
            return True

        if action == Action.CONFIRM:
            if self.file_entries:
                _, path, is_dir, _ = self.file_entries[self.file_list.selected]
                if is_dir:
                    self.current_dir = path
                    self._load_files()
                else:
                    self._open_file(path)
            return True

        elif action == Action.BACK:
            if self.current_dir != self.system.data_dir:
                self.current_dir = os.path.dirname(self.current_dir)
                self._load_files()
            return True

        elif action == Action.MENU:  # X — context menu
            self._open_context_menu()
            return True

        elif action == Action.DELETE:  # Y — delete
            self._delete_selected()
            return True

        return False

    def _handle_apps_input(self, action):
        if self.app_list.handle_input(action):
            return True

        if action == Action.CONFIRM:
            if self.app_entries:
                _, app_key = self.app_entries[self.app_list.selected]
                self._launch_app(app_key)
            return True

        return False

    def _handle_settings_input(self, action):
        if self.settings_list.handle_input(action):
            return True

        if action == Action.CONFIRM:
            if self.settings_entries:
                _, app_key = self.settings_entries[self.settings_list.selected]
                if app_key == "sound_toggle":
                    self.system.sfx.toggle()
                    self._load_settings()
                else:
                    self._launch_app(app_key)
            return True

        return False

    def _open_context_menu(self):
        trash_dir = self._get_trash_dir()
        in_trash = self.current_dir == trash_dir

        if in_trash:
            options = [
                ("Empty Trash", self._empty_trash),
            ]
        else:
            options = [
                ("New Folder", lambda: self._create_new("folder")),
                ("New File", lambda: self._create_new("file")),
            ]

            # Add rename/move if item selected (not parent dir entry)
            if self.file_entries and self.file_list.selected > 0:
                options.append(("Rename", self._rename_selected))
                options.append(("Move", self._move_selected))

        self.context_menu = ContextMenu(options)
        self.context_menu.open()

    def _empty_trash(self):
        trash_dir = self._get_trash_dir()
        from core.widgets import ConfirmDialog

        def on_confirm():
            try:
                shutil.rmtree(trash_dir)
                os.makedirs(trash_dir, exist_ok=True)
            except OSError:
                pass
            self._load_files()

        self._confirm_dialog = ConfirmDialog(
            "Empty Trash?", "Delete all items permanently?",
            on_confirm=on_confirm
        )
        self._confirm_dialog.open()
        self._active_dialog = self._confirm_dialog

    def _create_new(self, kind):
        def on_name(name):
            if not name:
                return
            path = os.path.join(self.current_dir, name)
            try:
                if kind == "folder":
                    os.makedirs(path, exist_ok=True)
                else:
                    with open(path, "w") as f:
                        pass
            except OSError:
                pass
            self._load_files()

        prompt = "Folder name:" if kind == "folder" else "File name:"
        self.system.open_keyboard(on_name, title=prompt)

    def _rename_selected(self):
        if not self.file_entries or self.file_list.selected < 0:
            return
        _, old_path, _, _ = self.file_entries[self.file_list.selected]
        old_name = os.path.basename(old_path)

        def on_name(new_name):
            if not new_name or new_name == old_name:
                return
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            try:
                os.rename(old_path, new_path)
            except OSError:
                pass
            self._load_files()

        self.system.open_keyboard(on_name, initial_text=old_name, title="Rename:")

    def _move_selected(self):
        if not self.file_entries or self.file_list.selected < 0:
            return
        _, old_path, _, _ = self.file_entries[self.file_list.selected]

        def on_path(new_dir):
            if not new_dir:
                return
            new_path = os.path.join(new_dir, os.path.basename(old_path))
            try:
                os.rename(old_path, new_path)
            except OSError:
                pass
            self._load_files()

        self.system.open_keyboard(
            on_path,
            initial_text=os.path.dirname(old_path),
            title="Move to:"
        )

    def _get_trash_dir(self):
        """Get the trash directory, creating it if needed."""
        trash = os.path.join(self.system.data_dir, ".trash")
        os.makedirs(trash, exist_ok=True)
        return trash

    def _delete_selected(self):
        if not self.file_entries or self.file_list.selected < 0:
            return

        display_name, path, is_dir, _ = self.file_entries[self.file_list.selected]
        if path == os.path.dirname(self.current_dir):
            return  # can't delete parent dir entry

        basename = os.path.basename(path)

        # Check if we're viewing the trash — permanent delete
        trash_dir = self._get_trash_dir()
        in_trash = self.current_dir == trash_dir

        from core.widgets import ConfirmDialog

        def on_confirm():
            try:
                if in_trash:
                    # Permanent delete from trash
                    if is_dir:
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                else:
                    # Move to trash
                    dest = os.path.join(trash_dir, basename)
                    # Avoid name collisions in trash
                    if os.path.exists(dest):
                        import time
                        ts = int(time.time())
                        name, ext = os.path.splitext(basename)
                        dest = os.path.join(trash_dir, f"{name}_{ts}{ext}")
                    shutil.move(path, dest)
            except OSError:
                pass
            self._load_files()

        if in_trash:
            title = "Delete forever?"
            msg = f"Permanently delete {basename}?"
        else:
            title = "Move to Trash?"
            msg = f"Trash {basename}?"

        self._confirm_dialog = ConfirmDialog(
            title, msg, on_confirm=on_confirm
        )
        self._confirm_dialog.open()
        self._active_dialog = self._confirm_dialog

    def draw(self):
        r = self.system.renderer

        # Status bar — icon + title on left, wifi indicator + time on right
        now = datetime.datetime.now().strftime("%H:%M")
        wifi_ssid = self._get_wifi_status()
        bt_device = self._get_bt_status()

        # Draw status bar background
        r.draw_box(0, 0, theme.SCREEN_WIDTH, theme.STATUSBAR_HEIGHT,
                   bg=theme.STATUSBAR_BG)

        # Left side: icon + "BubuOS"
        sb_y = 4
        x = theme.PADDING
        icon = r.load_image(self._icon_path)
        if icon:
            icon_y = (theme.STATUSBAR_HEIGHT - icon.get_height()) // 2
            r.screen.blit(icon, (x, icon_y))
            x += icon.get_width() + 4
        r.draw_text("BubuOS", x, sb_y, color=theme.STATUSBAR_TEXT)

        # Right side: indicators + date + time
        font = theme.get_font(theme.FONT_SIZE)
        time_w = font.size(now)[0]
        time_x = theme.SCREEN_WIDTH - time_w - theme.PADDING
        r.draw_text(now, time_x, sb_y, color=theme.STATUSBAR_TEXT)

        # Date (e.g. "Thu 19")
        date_str = datetime.datetime.now().strftime("%a %d")
        date_x = time_x - font.size(date_str + "  ")[0]
        r.draw_text(date_str, date_x, sb_y, color=theme.TEXT_DIM)

        # BT indicator
        bt_color = theme.SOFT_GREEN if bt_device else theme.WARM_GRAY
        bt_label = "BT"
        bt_x = date_x - font.size(bt_label + "  ")[0]
        r.draw_text(bt_label, bt_x, sb_y, color=bt_color)

        # WiFi indicator
        wifi_color = theme.SOFT_GREEN if wifi_ssid else theme.WARM_GRAY
        wifi_label = "WiFi"
        wifi_x = bt_x - font.size(wifi_label + "  ")[0]
        r.draw_text(wifi_label, wifi_x, sb_y, color=wifi_color)

        # Sound indicator
        snd_color = theme.SOFT_GREEN if self.system.sfx.enabled else theme.WARM_GRAY
        snd_label = "SND"
        snd_x = wifi_x - font.size(snd_label + "  ")[0]
        r.draw_text(snd_label, snd_x, sb_y, color=snd_color)

        # Tab bar
        _, ch = theme.get_char_size()
        tab_y = theme.CONTENT_TOP
        tab_x = theme.PADDING

        for i, tab_name in enumerate(self.TAB_NAMES):
            if i == self.current_tab:
                r.draw_text(f"[{tab_name}]", tab_x, tab_y,
                            color=theme.ACCENT)
            else:
                r.draw_text(f" {tab_name} ", tab_x, tab_y,
                            color=theme.TEXT_DIM)
            tab_x += font.size(f"[{tab_name}]")[0] + 8

        # Content
        content_y = tab_y + ch + 4

        if self.current_tab == self.TAB_FILES:
            # Directory path
            display_path = self.current_dir.replace(self.system.data_dir, "~")
            r.draw_text(display_path, theme.PADDING, content_y,
                        color=theme.ACCENT, size=theme.FONT_SMALL)
            content_y += ch + 2

            # File list
            self.file_list.max_visible = (theme.CONTENT_BOTTOM - content_y) // ch
            vis_start = self.file_list.scroll_offset
            vis_end = min(len(self.file_entries),
                          vis_start + self.file_list.max_visible)
            draw_y = content_y
            for i in range(vis_start, vis_end):
                label, _, _, count = self.file_entries[i]
                if i == self.file_list.selected:
                    r.draw_row(label, draw_y,
                               fg=theme.HIGHLIGHT_TEXT, bg=theme.HIGHLIGHT_BG)
                    if count is not None:
                        ct = f"({count})"
                        cw = font.size(ct)[0]
                        r.draw_text(ct, theme.SCREEN_WIDTH - theme.PADDING - cw,
                                    draw_y, color=theme.HIGHLIGHT_TEXT)
                else:
                    r.draw_row(label, draw_y, fg=theme.TEXT_COLOR)
                    if count is not None:
                        ct = f"({count})"
                        cw = font.size(ct)[0]
                        r.draw_text(ct, theme.SCREEN_WIDTH - theme.PADDING - cw,
                                    draw_y, color=theme.TEXT_DIM)
                draw_y += ch
        elif self.current_tab == self.TAB_APPS:
            self.app_list.max_visible = (theme.CONTENT_BOTTOM - content_y) // ch
            self.app_list.draw(r, content_y)
        else:
            self.settings_list.max_visible = (theme.CONTENT_BOTTOM - content_y) // ch
            self.settings_list.draw(r, content_y)

        # Help bar (blink Cal label when events pending)
        cal_label = "Cal!" if self._cal_pending and self._cal_blink else "Cal"
        if self.current_tab == self.TAB_FILES:
            r.draw_helpbar([
                ("A", "Open"), ("B", "Back"), ("X", "Menu"),
                ("Y", "Del"), ("=", "Scrn"), ("Sel", cal_label),
            ])
        else:
            r.draw_helpbar([
                ("A", "Open"), ("=", "Scrn"), ("Sel", cal_label),
            ])

        # Context menu overlay
        self.context_menu.draw(r)

        # Confirm dialog overlay
        if hasattr(self, "_active_dialog") and self._active_dialog and self._active_dialog.active:
            self._active_dialog.draw(r)
