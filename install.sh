#!/bin/bash

# --- VOE Video Downloader - Linux Installer ---
# Designed for Ubuntu, Debian and compatible systems (e.g., IONOS VPS)

echo "============================================="
echo "   VOE Video Downloader - Linux Installer    "
echo "============================================="

# 1. System checks
echo "[*] Running system checks..."
if [ "$(uname)" != "Linux" ]; then
    echo "[!] Error: This installation script only supports Linux."
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo "[!] Error: Please run this installer with root privileges (sudo)."
    exit 1
fi

# Get the installation directory
INSTALL_DIR="$( cd "$( dirname "$(readlink -f "${BASH_SOURCE[0]}")" )" &> /dev/null && pwd )"
echo "[*] Installation directory resolved to: $INSTALL_DIR"

# 2. Package manager updates & dependency installation
if command -v apt-get &> /dev/null; then
    echo "[*] Debian/Ubuntu-based system detected. Updating packages..."
    apt-get update
    echo "[*] Installing ffmpeg, aria2, python3-pip, python3-venv, and git..."
    apt-get install -y ffmpeg aria2 python3-pip python3-venv git
else
    echo "[!] Warning: 'apt-get' package manager not found. Please verify that"
    echo "    ffmpeg, aria2, python3-pip, python3-venv, and git are manually installed."
fi

# 3. Virtual Environment setup
echo "[*] Setting up Python virtual environment (venv) in $INSTALL_DIR/venv..."
python3 -m venv "$INSTALL_DIR/venv"
if [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "[!] Error: Failed to create virtual environment."
    exit 1
fi

# Upgrade pip & install requirements
echo "[*] Upgrading pip and installing python requirements..."
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# 4. Logging setup
echo "[*] Configuring logging directory /var/log/vid_download..."
mkdir -p /var/log/vid_download
touch /var/log/vid_download/downloads.log
chmod 777 /var/log/vid_download
chmod 666 /var/log/vid_download/downloads.log

# 5. Global wrapper script & symlink
echo "[*] Creating wrapper script and global symlink..."
# Create the local wrapper script first
cat << EOF > "$INSTALL_DIR/vid-download"
#!/bin/bash
# Wrapper script for video downloader
SOURCE_DIR="$INSTALL_DIR"
exec "\$SOURCE_DIR/venv/bin/python" "\$SOURCE_DIR/download_video.py" "\$@"
EOF

chmod +x "$INSTALL_DIR/vid-download"
chmod +x "$INSTALL_DIR/download_video.py"

# Create the global symlink
ln -sf "$INSTALL_DIR/vid-download" /usr/local/bin/vid-download

# Make update.sh executable as well
if [ -f "$INSTALL_DIR/update.sh" ]; then
    chmod +x "$INSTALL_DIR/update.sh"
fi

# 6. systemd service installation
echo "[*] Configuring systemd service..."
if [ -f "$INSTALL_DIR/vid_download.service" ]; then
    cp "$INSTALL_DIR/vid_download.service" /etc/systemd/system/vid_download.service
    
    echo "[*] Creating spool directory and placeholder urls.txt..."
    mkdir -p /var/spool/vid_download/downloads
    touch /var/spool/vid_download/urls.txt
    chmod -R 777 /var/spool/vid_download
    chmod 666 /var/spool/vid_download/urls.txt
    
    echo "[*] Reloading systemd daemon, enabling and starting service..."
    systemctl daemon-reload
    systemctl enable vid_download.service
    systemctl start vid_download.service
    echo "[+] Service successfully installed and started."
else
    echo "[!] Error: vid_download.service file not found in $INSTALL_DIR."
    exit 1
fi

echo "============================================="
echo "[+] INSTALLATION COMPLETED SUCCESSFULLY!"
echo "============================================="
echo "You can now run the downloader globally via:"
echo "  vid-download \"DEINE_VIDEO_URL\" \"ZIELORDNER\""
echo ""
echo "Or use the daemon by adding URLs to:"
echo "  /var/spool/vid_download/urls.txt"
echo "============================================="
