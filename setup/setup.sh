#!/bin/bash
# BubuOS Setup Script for Raspberry Pi CM4 Lite + GPi Case 2
# Run as root: sudo bash setup.sh <username>

set -e

echo "========================================="
echo "  BubuOS Setup for GPi Case 2 + CM4"
echo "========================================="

# Check root
if [ "$EUID" -ne 0 ]; then
    echo "Error: Run as root (sudo bash setup.sh <username>)"
    exit 1
fi

# Get target user
TARGET_USER="${1:-pi}"
USER_HOME="/home/$TARGET_USER"
BUBUOS_DIR="$USER_HOME/bubuos"
DATA_DIR="$USER_HOME/data"

if [ ! -d "$USER_HOME" ]; then
    echo "Error: Home directory $USER_HOME does not exist"
    exit 1
fi

echo "Installing for user: $TARGET_USER"

# --- 1. System update ---
echo ""
echo "[1/9] Updating system..."
apt update && apt upgrade -y

# --- 2. Install dependencies ---
echo ""
echo "[2/9] Installing dependencies..."
apt install -y \
    python3 \
    python3-pip \
    python3-pygame \
    xserver-xorg-core \
    xinit \
    libsdl2-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libsdl2-image-dev \
    network-manager \
    bluez \
    bluez-tools \
    pipewire \
    pipewire-pulse \
    wireplumber \
    libspa-0.2-bluetooth \
    git

# Switch from dhcpcd to NetworkManager for WiFi management
systemctl disable dhcpcd 2>/dev/null || true
systemctl enable NetworkManager
systemctl start NetworkManager

# --- 3. Disable swap ---
echo ""
echo "[3/9] Disabling swap..."
swapoff -a
systemctl disable dphys-swapfile 2>/dev/null || true
apt remove -y dphys-swapfile 2>/dev/null || true

# --- 4. Optimize filesystem ---
echo ""
echo "[4/9] Optimizing filesystem (noatime, tmpfs logs)..."

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
echo "[5/9] Installing GPi Case 2 drivers..."

if [ ! -d "$USER_HOME/GPi_Case2_patch" ]; then
    cd "$USER_HOME"
    git clone https://github.com/RetroFlag/GPi_Case2_patch.git 2>/dev/null || true
    if [ -f "$USER_HOME/GPi_Case2_patch/install.sh" ]; then
        bash "$USER_HOME/GPi_Case2_patch/install.sh"
    fi
fi

# --- 6. Boot config for GPi Case 2 DPI display ---
echo ""
echo "[6/9] Configuring boot settings..."

BOOT_CONFIG="/boot/firmware/config.txt"
if [ ! -f "$BOOT_CONFIG" ]; then
    BOOT_CONFIG="/boot/config.txt"
fi

# GPi Case 2 uses vc4-fkms-v3d (NOT vc4-kms-v3d — full KMS doesn't support DPI LCD)
if ! grep -q "# BubuOS GPi Case 2" "$BOOT_CONFIG"; then
    cat >> "$BOOT_CONFIG" << 'BOOTEOF'

# BubuOS GPi Case 2 settings
dtoverlay=vc4-fkms-v3d
disable_overscan=1
gpu_mem=128
BOOTEOF
fi

# --- 7. Configure X11 permissions ---
echo ""
echo "[7/9] Configuring X11..."

# Allow non-root users to start X server
cat > /etc/X11/Xwrapper.config << 'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

# --- 8. Create data directory and systemd service ---
echo ""
echo "[8/9] Setting up BubuOS service..."

mkdir -p "$DATA_DIR"/{documents,music,video,pictures}
chown -R "$TARGET_USER:$TARGET_USER" "$DATA_DIR"

# Generate service file from template
sed "s/YOUR_USER/$TARGET_USER/g" "$BUBUOS_DIR/setup/bubuos.service" \
    > /etc/systemd/system/bubuos.service
systemctl daemon-reload
systemctl enable bubuos.service

# --- 9. Sudoers for WiFi and Bluetooth management ---
echo ""
echo "[9/9] Configuring permissions..."

cat > /etc/sudoers.d/bubuos << EOF
$TARGET_USER ALL=(ALL) NOPASSWD: /usr/bin/nmcli
$TARGET_USER ALL=(ALL) NOPASSWD: /usr/sbin/rfkill
EOF
chmod 440 /etc/sudoers.d/bubuos

echo ""
echo "========================================="
echo "  BubuOS setup complete!"
echo "  User:           $TARGET_USER"
echo "  Data directory:  $DATA_DIR"
echo "  Reboot to start: sudo reboot"
echo "========================================="
