"""BubuOS About — system information screen."""

import os
import platform
import subprocess

from core.app import App
from core.input_handler import Action
from core import theme


class AboutApp(App):
    """Displays system information."""

    name = "System"

    def __init__(self, system):
        super().__init__(system)
        self.lines = []
        self.scroll = 0
        self._max_visible = 14
        self._gather_info()

    def on_enter(self):
        self._gather_info()

    def _run(self, cmd):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3, shell=True
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _read_file(self, path):
        try:
            with open(path) as f:
                return f.read().strip()
        except Exception:
            return ""

    def _gather_info(self):
        lines = []

        lines.append("--- System ---")
        lines.append("Name:     BubuOS")
        lines.append(f"Kernel:   {platform.release()}")
        lines.append(f"Arch:     {platform.machine()}")
        lines.append(f"Python:   {platform.python_version()}")
        hostname = platform.node()
        if hostname:
            lines.append(f"Hostname: {hostname}")
        lines.append("")

        lines.append("--- Hardware ---")
        cpuinfo = self._read_file("/proc/cpuinfo")
        cpu_model = ""
        cpu_cores = 0
        for line in cpuinfo.split("\n"):
            if line.startswith("model name") or line.startswith("Model"):
                cpu_model = line.split(":", 1)[1].strip()
            if line.startswith("processor"):
                cpu_cores += 1
        if cpu_model:
            lines.append(f"CPU:      {cpu_model}")
        if cpu_cores:
            lines.append(f"Cores:    {cpu_cores}")

        temp = self._run("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null")
        if temp:
            try:
                lines.append(f"CPU Temp: {int(temp) / 1000.0:.1f} C")
            except ValueError:
                pass

        meminfo = self._read_file("/proc/meminfo")
        for line in meminfo.split("\n"):
            if line.startswith("MemTotal:"):
                lines.append(f"RAM:      {int(line.split()[1]) // 1024} MB")
            elif line.startswith("MemAvailable:"):
                lines.append(f"RAM Free: {int(line.split()[1]) // 1024} MB")
        lines.append("")

        lines.append("--- Storage ---")
        df_out = self._run("df -h / 2>/dev/null | tail -1")
        if df_out:
            p = df_out.split()
            if len(p) >= 5:
                lines.append(f"Root:     {p[1]} total, {p[2]} used")
                lines.append(f"Free:     {p[3]} ({p[4]} used)")
        lines.append("")

        lines.append("--- Network ---")
        ip = self._run("hostname -I 2>/dev/null")
        if ip:
            for addr in ip.split():
                lines.append(f"IP:       {addr}")
        wifi = self._run("nmcli -t -f ACTIVE,SSID dev wifi 2>/dev/null | grep '^yes'")
        if wifi:
            ssid = wifi.split(":", 1)[1] if ":" in wifi else ""
            lines.append(f"WiFi:     {ssid}")
        mac = self._run("cat /sys/class/net/wlan0/address 2>/dev/null")
        if mac:
            lines.append(f"MAC:      {mac}")
        lines.append("")

        lines.append("--- Uptime ---")
        uptime = self._read_file("/proc/uptime")
        if uptime:
            secs = float(uptime.split()[0])
            d, h, m = int(secs // 86400), int((secs % 86400) // 3600), int((secs % 3600) // 60)
            lines.append(f"Uptime:   {f'{d}d ' if d else ''}{h}h {m}m")

        self.lines = lines
        self.scroll = 0

    def _max_scroll(self):
        return max(0, len(self.lines) - self._max_visible)

    def handle_input(self, action):
        if action == Action.UP:
            self.scroll = max(0, self.scroll - 1)
            return True
        elif action == Action.DOWN:
            self.scroll = min(self._max_scroll(), self.scroll + 1)
            return True
        elif action == Action.PAGE_UP:
            self.scroll = max(0, self.scroll - self._max_visible)
            return True
        elif action == Action.PAGE_DOWN:
            self.scroll = min(self._max_scroll(), self.scroll + self._max_visible)
            return True
        elif action == Action.BACK:
            self.system.back()
            return True
        elif action == Action.CONFIRM:
            self._gather_info()
            return True
        return False

    def draw(self):
        r = self.system.renderer
        _, ch = theme.get_char_size()

        r.draw_statusbar("  System", "")

        y = theme.CONTENT_TOP + 4
        self._max_visible = (theme.CONTENT_BOTTOM - y) // ch
        vis_end = min(len(self.lines), self.scroll + self._max_visible)

        for i in range(self.scroll, vis_end):
            line = self.lines[i]
            if line.startswith("---") and line.endswith("---"):
                color = theme.ACCENT
            elif ":" in line:
                color = theme.TEXT_COLOR
            else:
                color = theme.TEXT_DIM
            r.draw_text(line, theme.PADDING, y, color=color)
            y += ch

        r.draw_helpbar([("A", "Refresh"), ("B", "Back")])
