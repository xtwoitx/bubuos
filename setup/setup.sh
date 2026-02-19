#!/bin/bash
# BubuOS Setup Script for Raspberry Pi CM4 Lite + GPi Case 2
# Run as root: sudo bash setup.sh

set -e

echo "========================================="
echo "  BubuOS Setup for GPi Case 2 + CM4"
echo "========================================="

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "Error: Run as root (sudo bash setup.sh)"
    exit 1
fi

USER_HOME="/home/pi"
BUBUOS_DIR="$USER_HOME/bubuos"
DATA_DIR="$USER_HOME/data"

# --- 1. System update ---
echo ""
echo "[1/8] Updating system..."
apt update && apt upgrade -y

# --- 2. Install dependencies ---
echo ""
echo "[2/8] Installing dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-pygame \
    libsdl2-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libsdl2-image-dev \
    mpv \
    network-manager \
    bluez \
    bluez-tools \
    git

# Switch from dhcpcd to NetworkManager for WiFi management
systemctl disable dhcpcd 2>/dev/null || true
systemctl enable NetworkManager
systemctl start NetworkManager

# --- 3. Disable swap ---
echo ""
echo "[3/8] Disabling swap..."
swapoff -a
systemctl disable dphys-swapfile 2>/dev/null || true
apt remove -y dphys-swapfile 2>/dev/null || true

# --- 4. Optimize filesystem ---
echo ""
echo "[4/8] Optimizing filesystem (noatime, tmpfs logs)..."

# Add noatime to root partition
if ! grep -q "noatime" /etc/fstab; then
    sed -i 's|defaults|defaults,noatime|g' /etc/fstab
fi

# Logs to tmpfs (save microSD writes)
if ! grep -q "tmpfs.*\/var\/log" /etc/fstab; then
    echo "tmpfs /var/log tmpfs defaults,noatime,nosuid,nodev,noexec,mode=0755,size=64M 0 0" >> /etc/fstab
fi
if ! grep -q "tmpfs.*\/tmp" /etc/fstab; then
    echo "tmpfs /tmp tmpfs defaults,noatime,nosuid,nodev,size=256M 0 0" >> /etc/fstab
fi

# --- 5. GPi Case 2 driver (safe shutdown + button mapping) ---
echo ""
echo "[5/8] Installing GPi Case 2 drivers..."

# GPi Case 2 uses a device tree overlay for display and buttons
# The buttons are mapped as a USB gamepad by the case's built-in controller
# We need the safe shutdown script from Retroflag
if [ ! -d "$USER_HOME/GPi_Case2_patch" ]; then
    cd "$USER_HOME"
    git clone https://github.com/RetroFlag/GPi_Case2_patch.git 2>/dev/null || true
    if [ -f "$USER_HOME/GPi_Case2_patch/install.sh" ]; then
        bash "$USER_HOME/GPi_Case2_patch/install.sh"
    fi
fi

# --- 6. Boot config for GPi Case 2 display ---
echo ""
echo "[6/8] Configuring boot settings..."

BOOT_CONFIG="/boot/firmware/config.txt"
if [ ! -f "$BOOT_CONFIG" ]; then
    BOOT_CONFIG="/boot/config.txt"
fi

# Ensure display settings for GPi Case 2
if ! grep -q "# BubuOS GPi Case 2" "$BOOT_CONFIG"; then
    cat >> "$BOOT_CONFIG" << 'BOOTEOF'

# BubuOS GPi Case 2 settings
dtoverlay=vc4-kms-v3d
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=640 480 60 1 0 0 0
hdmi_drive=2
disable_overscan=1
gpu_mem=128
BOOTEOF
fi

# --- 7. Create data directory and systemd service ---
echo ""
echo "[7/8] Setting up BubuOS service..."

mkdir -p "$DATA_DIR"/{documents,music,video,pictures}
chown -R pi:pi "$DATA_DIR"

# Install systemd service
cp "$BUBUOS_DIR/setup/bubuos.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable bubuos.service

# --- 8. Set console autologin for pi user ---
echo ""
echo "[8/8] Configuring autologin..."

mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin pi --noclear %I $TERM
EOF

echo ""
echo "========================================="
echo "  BubuOS setup complete!"
echo "  Data directory: $DATA_DIR"
echo "  Reboot to start: sudo reboot"
echo "========================================="
