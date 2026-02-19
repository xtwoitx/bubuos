"""BubuOS WiFi Settings — scan, connect, disconnect via NetworkManager."""

import subprocess
from core.app import App
from core.input_handler import Action
from core import theme
from core.widgets import ScrollList


class WiFiApp(App):
    """WiFi network manager using nmcli."""

    name = "WiFi"
    help_items = [
        ("A", "Connect"), ("B", "Back"), ("X", "Scan"), ("Y", "Disconnect"),
    ]

    def __init__(self, system):
        super().__init__(system)
        self.networks = []  # list of dicts: ssid, signal, security, active
        self.net_list = ScrollList()
        self.status_text = "Loading..."
        self.current_ssid = None

    def on_enter(self):
        self._scan()

    def _run_nmcli(self, args):
        """Run an nmcli command and return stdout+stderr."""
        try:
            result = subprocess.run(
                ["sudo", "nmcli"] + args,
                capture_output=True, text=True, timeout=25
            )
            output = result.stdout.strip()
            if not output and result.stderr:
                output = result.stderr.strip()
            return output
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    def _scan(self):
        """Scan for WiFi networks."""
        self.status_text = "Scanning..."

        # Trigger a rescan
        self._run_nmcli(["dev", "wifi", "rescan"])

        # List networks
        output = self._run_nmcli([
            "-t", "-f", "ACTIVE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list"
        ])

        self.networks = []
        self.current_ssid = None
        self._connected_index = -1
        seen_ssids = set()

        for line in output.split("\n"):
            if not line:
                continue
            # nmcli -t escapes : as \: in values, split on unescaped :
            import re
            parts = re.split(r'(?<!\\):', line)
            if len(parts) < 4:
                continue

            active = parts[0] == "yes"
            ssid = parts[1].replace("\\:", ":")
            signal = parts[2]
            security = parts[3]

            if not ssid or ssid in seen_ssids:
                continue
            seen_ssids.add(ssid)

            if active:
                self.current_ssid = ssid

            self.networks.append({
                "ssid": ssid,
                "signal": signal,
                "security": security,
                "active": active,
            })

        # Sort: active first, then by signal strength
        self.networks.sort(key=lambda n: (not n["active"], -int(n["signal"] or 0)))

        # Build display list; track connected index
        display = []
        for i, net in enumerate(self.networks):
            lock = "L" if net["security"] and net["security"] != "--" else " "
            if net["active"]:
                self._connected_index = i
                display.append(f"* {lock} {net['signal']:>3}% {net['ssid']}")
            else:
                display.append(f"  {lock} {net['signal']:>3}% {net['ssid']}")

        self.net_list.set_items(display)
        self.status_text = f"Found {len(self.networks)} networks"
        if self.current_ssid:
            self.status_text += f" | Connected: {self.current_ssid}"

    def _connect(self, ssid, password=None):
        """Connect to a WiFi network."""
        self.status_text = f"Connecting to {ssid}..."

        if password:
            # Delete old profile to avoid stale password
            self._run_nmcli(["connection", "delete", ssid])
            result = self._run_nmcli([
                "--wait", "15",
                "dev", "wifi", "connect", ssid, "password", password
            ])
        else:
            # Try connecting with saved credentials first
            result = self._run_nmcli([
                "--wait", "15",
                "dev", "wifi", "connect", ssid
            ])

        if "successfully" in result.lower():
            self.status_text = f"Connected to {ssid}"
            self.current_ssid = ssid
        else:
            self.status_text = f"Failed: {result[:50]}"

        self._scan()

    def _disconnect(self):
        """Disconnect from current WiFi."""
        self._run_nmcli(["dev", "disconnect", "wlan0"])
        self.current_ssid = None
        self.status_text = "Disconnected"
        self._scan()

    def handle_input(self, action):
        if self.net_list.handle_input(action):
            return True

        if action == Action.CONFIRM:  # A — connect to selected
            if self.networks:
                net = self.networks[self.net_list.selected]
                ssid = net["ssid"]
                has_security = net["security"] and net["security"] != "--"

                if has_security:
                    def on_password(password):
                        if password:
                            self._connect(ssid, password)

                    self.system.open_keyboard(
                        on_password,
                        title=f"Password for {ssid}:"
                    )
                else:
                    self._connect(ssid)
            return True

        elif action == Action.BACK:  # B — go back
            self.system.back()
            return True

        elif action == Action.MENU:  # X — rescan
            self._scan()
            return True

        elif action == Action.DELETE:  # Y — disconnect
            self._disconnect()
            return True

        return False

    def draw(self):
        r = self.system.renderer
        import pygame as _pg

        # Status bar
        r.draw_statusbar("  WiFi Settings", "")

        _, ch = theme.get_char_size()
        y = theme.CONTENT_TOP + 4

        # Status line
        r.draw_text(self.status_text, theme.PADDING, y,
                     color=theme.ACCENT, size=theme.FONT_SMALL)
        y += ch + 4

        # Draw network list manually for connected highlighting
        items = self.net_list.items
        sel = self.net_list.selected
        offset = self.net_list.scroll_offset
        max_vis = (theme.CONTENT_BOTTOM - y) // ch
        self.net_list.max_visible = max_vis

        vis_end = min(len(items), offset + max_vis)
        for i in range(offset, vis_end):
            is_selected = (i == sel)
            is_connected = (i == self._connected_index)

            if is_selected:
                fg = theme.HIGHLIGHT_TEXT
                bg = theme.HIGHLIGHT_BG
            elif is_connected:
                fg = theme.SOFT_GREEN
                bg = theme.BG_COLOR
            else:
                fg = theme.TEXT_COLOR
                bg = theme.BG_COLOR

            r.draw_row(items[i], y, fg=fg, bg=bg)
            y += ch

            # Separator after connected network
            if is_connected and i + 1 < len(items):
                r.draw_text("-" * 40, theme.PADDING, y, color=theme.WARM_GRAY)
                y += ch

        # Help bar
        r.draw_helpbar(self.help_items)
