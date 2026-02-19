# BubuOS

A cute pocket operating system built with love for the [GPi Case 2](https://retroflag.com/gpi-case-2.html).

BubuOS is a custom DOS-like shell for Raspberry Pi CM4, written in Python + pygame. It runs on a 640x480 DPI LCD with 10-button gamepad input — no keyboard, no mouse, no touchscreen. Just a tiny console in your pocket.

![BubuOS Weather](screenshots/weather.png)

## Features

- **File Browser** — navigate folders, open files, delete with confirmation
- **Music Player** — plays MP3/FLAC/OGG with animated Bubu sprites and progress bar
- **Weather** — current weather and 5-day forecast with cute Bubu in seasonal outfit
- **Calendar** — month view with events organizer, to-do checkmarks
- **Snake** — classic snake game where Bubu eats burgers
- **Text Editor** — on-screen QWERTY keyboard for notes
- **Web Radio** — internet radio player
- **Image Viewer** — full-screen image viewer with folder navigation
- **Bluetooth Audio** — pair and connect BT speakers
- **WiFi Manager** — scan and connect to networks
- **System Info** — CPU, RAM, storage, network, temperature
- **Sound Effects** — procedurally generated music-box UI sounds
- **Screenshots** — capture the screen with a button press

## Screenshots

| Files | Apps | Weather |
|-------|------|---------|
| ![](screenshots/shell_folders.png) | ![](screenshots/shell_apps.png) | ![](screenshots/weather.png) |

| Music Player | Calendar | Snake |
|-------------|----------|-------|
| ![](screenshots/player.png) | ![](screenshots/calendar.png) | ![](screenshots/snake.png) |

## Hardware

- [GPi Case 2](https://retroflag.com/gpi-case-2.html) — the shell (screen + buttons + battery)
- [Raspberry Pi CM4 Lite](https://www.raspberrypi.com/products/compute-module-4/) — 2GB RAM, Wireless
- microSD card (any size, 8GB+ recommended)

## Stack

- Raspberry Pi OS Lite (Debian 13, no desktop)
- Python 3.13 + pygame 2.6 (SDL2)
- X11 via `xinit` (not kmsdrm — due to a vc4-fkms-v3d async page flip bug)
- PipeWire + WirePlumber for Bluetooth audio
- Systemd service for auto-start

## Install

1. Flash **Raspberry Pi OS Lite (64-bit)** to a microSD card
2. Copy the `pocketos/` directory to `/home/<user>/pocketos/`
3. Install dependencies:
   ```bash
   sudo apt install python3-pygame xserver-xorg-core xinit
   pip install -r requirements.txt
   ```
4. Install the systemd service:
   ```bash
   sudo cp setup/bubuos.service /etc/systemd/system/
   sudo systemctl enable bubuos
   sudo reboot
   ```

## The Story

Bubu and Dudu are two characters that helped me through a tough time. Building a tiny OS for them — giving them a home they can live in, play music, check the weather, and eat burgers — turned into a project that brought me back to life. This is that project.

## License

MIT
