#!/usr/bin/env python3
"""Standalone gamepad-to-keyboard helper for the browser.

Reads /dev/input/js0 directly and sends xdotool commands.
Runs as a separate process so it works even when pygame has no focus.

Exit: sends SIGTERM to the surf PID passed as argument.
"""

import os
import struct
import subprocess
import sys
import signal

DISPLAY = ":0"

# GPi Case 2: 0=A, 1=B, 2=X, 3=Y, 4=L, 5=R, 6=Select, 7=Start
BUTTON_MAP = {
    0: "Return",        # A → Enter
    1: "alt+Left",      # B → back
    2: "ctrl+g",        # X → surf URL prompt
    3: "Escape",        # Y → stop
    4: "Prior",         # L → Page Up
    5: "Next",          # R → Page Down
}

EXIT_BUTTONS = {6, 7}   # Select or Start → kill browser


def send_key(key):
    try:
        subprocess.Popen(
            ["xdotool", "key", "--clearmodifiers", key],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={"DISPLAY": DISPLAY, "PATH": "/usr/bin:/usr/local/bin"},
        )
    except Exception:
        pass


def send_scroll(direction):
    """Send arrow key for scrolling."""
    key_map = {"up": "Up", "down": "Down", "left": "Left", "right": "Right"}
    key = key_map.get(direction)
    if key:
        send_key(key)


def main():
    if len(sys.argv) < 2:
        print("Usage: gamepad_helper.py <surf_pid>", file=sys.stderr)
        sys.exit(1)

    surf_pid = int(sys.argv[1])
    js_path = "/dev/input/js0"

    try:
        js = open(js_path, "rb")
    except (PermissionError, OSError, FileNotFoundError) as e:
        print(f"Cannot open {js_path}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        while True:
            # Check if surf is still alive
            try:
                os.kill(surf_pid, 0)
            except ProcessLookupError:
                break

            data = js.read(8)
            if not data or len(data) < 8:
                break

            _ts, value, ev_type, number = struct.unpack("IhBB", data)

            # Skip init events
            if ev_type & 0x80:
                continue

            # Button press
            if (ev_type & 0x01) and value == 1:
                if number in EXIT_BUTTONS:
                    # Kill surf
                    try:
                        os.kill(surf_pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    break

                key = BUTTON_MAP.get(number)
                if key:
                    send_key(key)

            # Axis / D-pad
            elif ev_type & 0x02:
                if number in (0, 6):  # X axis / Hat X
                    if value < -16000:
                        send_scroll("left")
                    elif value > 16000:
                        send_scroll("right")
                elif number in (1, 7):  # Y axis / Hat Y
                    if value < -16000:
                        send_scroll("up")
                    elif value > 16000:
                        send_scroll("down")

    except (OSError, ValueError, KeyboardInterrupt):
        pass
    finally:
        js.close()


if __name__ == "__main__":
    main()
