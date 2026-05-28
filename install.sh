#!/bin/bash

# --- VOE Video Downloader - Linux Installer ---
# Konzipiert für Ubuntu, Debian und kompatible Systeme (z.B. Ionos VPS)

echo "============================================="
echo "   VOE Video Downloader - Linux Installer    "
echo "============================================="

# 1. Update Paket-Listen & Systemvoraussetzungen prüfen
echo -e "\n[*] Überprüfe Systemkomponenten..."
if ! command -v python3 &> /dev/null; then
    echo "[!] Python 3 ist nicht installiert. Bitte installieren Sie es zuerst (z.B. sudo apt install python3)"
    exit 1
fi

# Paketverwaltung prüfen
if command -v apt-get &> /dev/null; then
    echo "[*] Debian/Ubuntu-basiertes System erkannt."
    echo "[*] Installiere ffmpeg, python3-pip und python3-venv..."
    sudo apt-get update && sudo apt-get install -y ffmpeg python3-pip python3-venv
else
    echo "[!] Warnung: Paketmanager 'apt' nicht gefunden. Bitte stellen Sie sicher, dass 'ffmpeg', 'pip3' und 'venv' installiert sind."
fi

# 2. Virtuelle Umgebung einrichten (verhindert PEP 668 Probleme auf Linux)
echo -e "\n[*] Richte virtuelle Python-Umgebung (venv) ein..."
python3 -m venv venv
if [ ! -d "venv" ]; then
    echo "[!] Fehler beim Erstellen der virtuellen Umgebung."
    exit 1
fi

# Aktivieren & Updaten
source venv/bin/activate
pip install --upgrade pip

# 3. Python-Abhängigkeiten installieren
echo -e "\n[*] Installiere benötigte Python-Bibliotheken..."
pip install -r requirements.txt

# 4. Ausführungsberechtigungen & Komfort-Wrapper
echo -e "\n[*] Erstelle Start-Skript..."
cat << 'EOF' > run.sh
#!/bin/bash
# Startet den Downloader in der virtuellen Umgebung
SOURCE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
source "$SOURCE_DIR/venv/bin/activate"
python "$SOURCE_DIR/download_video.py" "$@"
EOF

chmod +x run.sh

echo -e "\n============================================="
echo -e "[+] INSTALLATION ERFOLGREICH!"
echo -e "============================================="
echo -e "So führst du den Downloader aus:"
echo -e "  ./run.sh \"DEINE_VIDEO_URL\" \"ZIELORDNER\""
echo -e "\nBeispiel:"
echo -e "  ./run.sh \"http://186.2.175.5/serie/the-rookie/staffel-8/episode-13\" \"/home/user/downloads\""
echo -e "============================================="
