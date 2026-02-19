"""BubuOS Bluetooth Settings — scan, pair, connect via bluetoothctl."""

import subprocess
import threading
import time
from core.app import App
from core.input_handler import Action
from core import theme
from core.widgets import ScrollList


class BluetoothApp(App):
    """Bluetooth device manager using bluetoothctl."""

    name = "Bluetooth"
    help_items = [
        ("A", "Connect"), ("B", "Back"), ("X", "Scan"), ("Y", "Remove"),
    ]

    def __init__(self, system):
        super().__init__(system)
        self.devices = []
        self.dev_list = ScrollList()
        self.status_text = "Loading..."
        self.bt_powered = False
        self._connected_index = -1
        self._scanning = False
        self._busy = False  # block input during connect/pair

    def on_enter(self):
        self._check_power()
        if self.bt_powered:
            self._refresh()
        else:
            self.devices = []
            self._rebuild_display()
            self.status_text = "Bluetooth OFF"

    def _btctl(self, *args, timeout=10):
        """Run bluetoothctl with arguments (non-interactive)."""
        try:
            result = subprocess.run(
                ["bluetoothctl"] + list(args),
                capture_output=True, text=True, timeout=timeout,
            )
            return result.stdout + result.stderr
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    def _check_power(self):
        """Check BT power state without changing it."""
        output = self._btctl("show")
        self.bt_powered = "Powered: yes" in output

    def _get_pw_env(self):
        """Get environment dict with PipeWire/WirePlumber vars."""
        import os
        env = os.environ.copy()
        runtime_dir = f"/run/user/{os.getuid()}"
        env.setdefault("XDG_RUNTIME_DIR", runtime_dir)
        env.setdefault("DBUS_SESSION_BUS_ADDRESS",
                       f"unix:path={runtime_dir}/bus")
        return env

    def _ensure_power(self):
        """Unblock rfkill, power on adapter."""
        subprocess.run(
            ["sudo", "rfkill", "unblock", "bluetooth"],
            capture_output=True, timeout=5,
        )
        output = self._btctl("show")
        if "Powered: yes" not in output:
            self._btctl("power", "on")
            time.sleep(0.5)
            output = self._btctl("show")
        self.bt_powered = "Powered: yes" in output

    def _toggle_power(self):
        """Toggle Bluetooth power on/off."""
        if self.bt_powered:
            self._btctl("power", "off")
            subprocess.run(
                ["sudo", "rfkill", "block", "bluetooth"],
                capture_output=True, timeout=5,
            )
            self.bt_powered = False
            self.devices = []
            self._rebuild_display()
            self.status_text = "Bluetooth OFF"
        else:
            self._ensure_power()
            if self.bt_powered:
                self._refresh()
            else:
                self.status_text = "Cannot power on Bluetooth"

    def _refresh(self):
        """Refresh the list of paired devices."""
        if not self.bt_powered:
            self.status_text = "Bluetooth OFF"
            self.devices = []
            self._rebuild_display()
            return

        output = self._btctl("devices", "Paired")
        self.devices = []
        self._connected_index = -1

        for line in output.split("\n"):
            line = line.strip()
            if not line.startswith("Device "):
                continue
            parts = line.split(" ", 2)
            if len(parts) < 3:
                continue
            address = parts[1]
            name = parts[2]

            info = self._btctl("info", address)
            connected = "Connected: yes" in info

            self.devices.append({
                "address": address,
                "name": name,
                "paired": True,
                "connected": connected,
            })

        self._rebuild_display()
        n_conn = sum(1 for d in self.devices if d["connected"])
        self.status_text = f"{len(self.devices)} paired, {n_conn} connected"

    def _rebuild_display(self):
        """Rebuild the display list from self.devices.

        First item is always the power toggle row.
        Device indices are offset by 1 from dev_list indices.
        """
        self._connected_index = -1
        display = []

        # Power toggle row
        if self.bt_powered:
            display.append("Bluetooth: ON")
        else:
            display.append("Bluetooth: OFF")

        for i, dev in enumerate(self.devices):
            idx = i + 1  # offset for power toggle row
            if dev["connected"]:
                self._connected_index = idx
                display.append(f"* {dev['name']}")
            elif dev["paired"]:
                display.append(f"P {dev['name']}")
            else:
                display.append(f"  {dev['name']}")
        self.dev_list.set_items(display)

    def _scan_and_list(self):
        """Start async scan for new devices."""
        if self._scanning:
            return

        self._ensure_power()
        if not self.bt_powered:
            self.status_text = "Cannot power on Bluetooth"
            return

        self._scanning = True
        self.status_text = "Scanning..."
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        """Background scan thread using interactive bluetoothctl."""
        import re
        try:
            p = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            p.stdin.write("power on\n")
            p.stdin.write("scan on\n")
            p.stdin.flush()
            time.sleep(10)
            p.stdin.write("scan off\n")
            p.stdin.flush()
            time.sleep(1)
            p.stdin.write("devices\n")
            p.stdin.flush()
            time.sleep(0.5)
            p.stdin.write("quit\n")
            p.stdin.flush()
            out, _ = p.communicate(timeout=3)

            seen = {d["address"] for d in self.devices}
            new_count = 0

            for line in out.split("\n"):
                clean = re.sub(r'\x1b\[[0-9;]*m', '', line).strip()
                if not clean.startswith("Device "):
                    continue
                parts = clean.split(" ", 2)
                if len(parts) < 3:
                    continue
                address = parts[1]
                name = parts[2]
                if address in seen:
                    continue
                # Use MAC-style name as-is if no real name resolved
                if name == address or name.replace("-", ":") == address:
                    name = address
                seen.add(address)
                new_count += 1
                self.devices.append({
                    "address": address,
                    "name": name,
                    "paired": False,
                    "connected": False,
                })

            self._rebuild_display()
            self.status_text = f"Found {new_count} new | {len(self.devices)} total"
        except Exception:
            self.status_text = "Scan error"
        finally:
            self._scanning = False

    def _connect_device(self, dev):
        """Pair, trust, and connect in background thread."""
        if self._busy:
            return
        self._busy = True
        self.status_text = f"Connecting {dev['name']}..."
        threading.Thread(
            target=self._connect_worker, args=(dev,), daemon=True).start()

    def _connect_worker(self, dev):
        """Background connect thread using interactive bluetoothctl."""
        import re
        try:
            addr = dev["address"]
            p = subprocess.Popen(
                ["bluetoothctl"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )

            if not dev["paired"]:
                self.status_text = f"Pairing {dev['name']}..."
                p.stdin.write(f"pair {addr}\n")
                p.stdin.flush()
                time.sleep(4)

            p.stdin.write(f"trust {addr}\n")
            p.stdin.flush()
            time.sleep(1)

            self.status_text = f"Connecting {dev['name']}..."
            p.stdin.write(f"connect {addr}\n")
            p.stdin.flush()
            time.sleep(5)

            p.stdin.write(f"info {addr}\n")
            p.stdin.flush()
            time.sleep(0.5)
            p.stdin.write("quit\n")
            p.stdin.flush()
            out, _ = p.communicate(timeout=3)

            clean_out = re.sub(r'\x1b\[[0-9;]*m', '', out)
            if "Connected: yes" in clean_out:
                self.status_text = f"Connected: {dev['name']}"
                self._setup_audio_sink(dev)
            else:
                self.status_text = "Connect failed"

            self._refresh()
        except Exception:
            self.status_text = "Connect error"
        finally:
            self._busy = False

    def _setup_audio_sink(self, dev):
        """Wait for WirePlumber to detect the BT device and set it as default sink."""
        env = self._get_pw_env()
        # Poll wpctl for up to 10s waiting for the BT sink to appear
        for _ in range(10):
            time.sleep(1)
            try:
                result = subprocess.run(
                    ["wpctl", "status"],
                    capture_output=True, text=True, timeout=5, env=env,
                )
            except Exception:
                continue
            for line in result.stdout.split("\n"):
                if dev["name"] in line and "vol:" in line:
                    parts = line.strip().lstrip("*").strip().split(".", 1)
                    if parts[0].strip().isdigit():
                        sink_id = parts[0].strip()
                        try:
                            subprocess.run(
                                ["wpctl", "set-default", sink_id],
                                capture_output=True, timeout=5, env=env,
                            )
                        except Exception:
                            pass
                        self.status_text = f"Audio: {dev['name']}"
                        return
        self.status_text = f"Connected (no audio sink)"

    def _disconnect_device(self, dev):
        """Disconnect a connected device."""
        self.status_text = f"Disconnecting..."
        self._btctl("disconnect", dev["address"])
        self.status_text = f"Disconnected: {dev['name']}"
        self._refresh()

    def _remove_device(self, dev):
        """Remove/unpair a device."""
        self._btctl("remove", dev["address"])
        self.status_text = f"Removed: {dev['name']}"
        self._refresh()

    def handle_input(self, action):
        if self._scanning or self._busy:
            if action == Action.BACK:
                self.system.back()
                return True
            return True  # block other input while busy

        if self.dev_list.handle_input(action):
            return True

        if action == Action.CONFIRM:
            if self.dev_list.selected == 0:
                # Power toggle row
                self._toggle_power()
            elif self.devices:
                dev_idx = self.dev_list.selected - 1
                dev = self.devices[dev_idx]
                if dev["connected"]:
                    self._disconnect_device(dev)
                else:
                    self._connect_device(dev)
            return True

        elif action == Action.BACK:
            self.system.back()
            return True

        elif action == Action.MENU:
            if not self.bt_powered:
                self._toggle_power()  # X turns on if off
            else:
                self._scan_and_list()
            return True

        elif action == Action.DELETE:
            if self.dev_list.selected > 0 and self.devices:
                dev_idx = self.dev_list.selected - 1
                dev = self.devices[dev_idx]
                self._remove_device(dev)
            return True

        return False

    def draw(self):
        r = self.system.renderer

        power = "ON" if self.bt_powered else "OFF"
        r.draw_statusbar("  Bluetooth", f"  {power}  ")

        _, ch = theme.get_char_size()
        y = theme.CONTENT_TOP + 4

        # Status with scanning animation
        status = self.status_text
        if self._scanning:
            dots = "." * (int(time.time() * 2) % 4)
            status = f"Scanning{dots}"
        elif self._busy:
            dots = "." * (int(time.time() * 2) % 4)
            status = self.status_text.rstrip(".") + dots

        r.draw_text(status, theme.PADDING, y,
                    color=theme.ACCENT, size=theme.FONT_SMALL)
        y += ch + 4

        items = self.dev_list.items
        sel = self.dev_list.selected
        offset = self.dev_list.scroll_offset
        max_vis = (theme.CONTENT_BOTTOM - y) // ch
        self.dev_list.max_visible = max_vis

        vis_end = min(len(items), offset + max_vis)
        for i in range(offset, vis_end):
            is_selected = (i == sel)
            is_power_row = (i == 0)
            is_connected = (i == self._connected_index)

            if is_selected:
                fg = theme.HIGHLIGHT_TEXT
                bg = theme.HIGHLIGHT_BG
            elif is_power_row:
                fg = theme.SOFT_GREEN if self.bt_powered else theme.WARM_GRAY
                bg = theme.BG_COLOR
            elif is_connected:
                fg = theme.SOFT_GREEN
                bg = theme.BG_COLOR
            else:
                fg = theme.TEXT_COLOR
                bg = theme.BG_COLOR

            r.draw_row(items[i], y, fg=fg, bg=bg)
            y += ch

            # Separator after power row
            if is_power_row and len(items) > 1:
                r.draw_text("-" * 40, theme.PADDING, y,
                            color=theme.WARM_GRAY)
                y += ch

            if is_connected and i + 1 < len(items):
                r.draw_text("-" * 40, theme.PADDING, y,
                            color=theme.WARM_GRAY)
                y += ch

        # Hint when powered on but no devices
        if self.bt_powered and not self.devices:
            r.draw_text("No devices. Press X to scan.", theme.PADDING, y,
                        color=theme.TEXT_DIM)

        legend_y = theme.CONTENT_BOTTOM - ch
        r.draw_text("*=Connected  P=Paired  A:Toggle  Y:Remove",
                    theme.PADDING, legend_y,
                    color=theme.TEXT_DIM, size=theme.FONT_SMALL)

        r.draw_helpbar(self.help_items)
