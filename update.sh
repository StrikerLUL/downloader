#!/bin/bash

# --- VOE Video Downloader - Linux Updater ---

echo "============================================="
echo "   VOE Video Downloader - Linux Updater      "
echo "============================================="

# 1. System checks
if [ "$(uname)" != "Linux" ]; then
    echo "[!] Error: This script is only supported on Linux."
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo "[!] Error: Please run this script with root privileges (sudo)."
    exit 1
fi

# Get source directory of the script
SOURCE_DIR="$( cd "$( dirname "$(readlink -f "${BASH_SOURCE[0]}")" )" &> /dev/null && pwd )"

echo "[*] Navigating to source directory: $SOURCE_DIR"
cd "$SOURCE_DIR" || exit 1

echo "[*] Pulling latest changes from git repository..."
git pull

# Verify venv exists
if [ ! -d "venv" ]; then
    echo "[*] Creating missing virtual environment..."
    python3 -m venv venv
fi

echo "[*] Upgrading pip and updating python dependencies..."
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt --upgrade

echo "[*] Restarting systemd service..."
if systemctl list-unit-files | grep -q "^vid_download.service"; then
    systemctl restart vid_download.service
    echo "[+] Systemd service restarted successfully."
else
    echo "[!] Warning: vid_download.service not found/active. Skipping restart."
fi

echo "============================================="
echo "[+] UPDATE COMPLETED SUCCESSFULLY!"
echo "============================================="
