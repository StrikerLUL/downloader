# 🚀 VOE & Serien-Hub Video Downloader CLI

Ein hochentwickelter, plattformunabhängiger Video-Downloader zur vollautomatischen Extraktion und zum Herunterladen von Videos aus **VOE-Playern** sowie Serien-Portalen wie **AniWorld.to, S.to, serienstream.to** und deren IP-Bypass-Spiegeln (z. B. `http://186.2.175.5`).

Dank der eingebauten **Methode 7 Quelltext-Entschlüsselung** extrahiert das Tool den direkten Streaming-Link (MP4/HLS) direkt aus dem verschlüsselten Code des Players – **völlig ohne Download-Button oder manuelle Interaktion mit Browser-Entwicklertools (F12)**.

---

## ✨ Features

*   **⚡ Methode 7 Entschlüsselung**: Umgeht Website-Schutzmaßnahmen durch vollständige softwareseitige Krypto-Nachbildung (ROT13 + Character Shift + Base64 + String Reversing).
*   **🌐 Universelle Serien-Hub-Unterstützung**: Erkennt automatisch Episodenseiten von AniWorld, s.to und SerienStream (inklusive aller direkten IP-Bypass-Domains wie `186.2.175.5`).
*   **🎨 Intelligente Sprach-Priorisierung**: Liest Sprachlabels aus und priorisiert Downloads automatisch nach Ihren Vorlieben (z. B. `Deutsch Dub` > `Deutsch Sub` > `Englisch`).
*   **↩️ JS-Redirect Auflösung**: Folgt rekursiv verschachtelten JavaScript-Weiterleitungen (`window.location.href`) auf Mirror-Domains.
*   **🐧 Linux & Windows Ready**: Vollständig kompatibel mit Windows-PCs und Linux-Servern (z. B. Ionos VPS, Ubuntu, Debian).
*   **📦 Venv & PEP 668 Schutz**: Inklusive eines automatischen Virtual-Environment-Setups für Linux-Systeme, um Konflikte mit der System-Paketverwaltung zu vermeiden.

---

## 🛠️ Installation auf Ihrem Ionos Linux Server (Ubuntu/Debian)

Die Installation auf einem Linux-Server wurde durch ein automatisiertes Skript maximal vereinfacht.

### 1. Repository klonen oder hochladen
Klonen Sie das Repository von GitHub (siehe Anleitung unten) oder laden Sie die Dateien auf Ihren Server hoch:
```bash
git clone https://github.com/DEIN_BENUTZERNAME/Vid_download.git
cd Vid_download
```

### 2. Installationsskript ausführen
Führen Sie das Skript aus, um Systempakete (`ffmpeg`, `python3-venv`, `pip3`), die virtuelle Python-Umgebung und alle Abhängigkeiten vollautomatisch zu installieren:
```bash
chmod +x install.sh
./install.sh
```

---

## 🚀 Benutzung (Linux)

Nach der Installation können Sie den Downloader über das erstellte Wrapper-Skript `run.sh` ausführen:

```bash
./run.sh "DEINE_VIDEO_URL" "ZIELORDNER"
```

### Beispiele:

*   **Direkte IP-Episode von SerienStream (z. B. The Rookie):**
    ```bash
    ./run.sh "http://186.2.175.5/serie/the-rookie/staffel-8/episode-13" "/home/user/downloads"
    ```

*   **Direkter AniWorld-Episoden-Link:**
    ```bash
    ./run.sh "https://aniworld.to/anime/stream/marriagetoxin/staffel-1/episode-1" "./downloads"
    ```

*   **Direkter VOE-Player Link:**
    ```bash
    ./run.sh "https://voe.sx/e/mozwgfjc7pgy" "."
    ```

---

## 🖥️ Benutzung (Windows)

Unter Windows können Sie das Programm direkt mit Python ausführen:

```powershell
# Abhängigkeiten installieren (einmalig)
pip install -r requirements.txt

# Skript ausführen
python download_video.py "DEINE_VIDEO_URL" "ZIELORDNER"
```

---

## 📂 Git & GitHub Guide: Vom PC auf den Linux-Server

Hier ist eine einfache Schritt-für-Schritt-Anleitung, um das Projekt über GitHub auf Ihren Ionos Linux-Server zu bringen.

### Teil A: Am Windows-PC (Projekt zu GitHub hochladen)

1.  **Repository auf GitHub erstellen**:
    *   Gehen Sie auf [github.com](https://github.com/) und erstellen Sie ein neues Repository.
    *   Nennen Sie es z. B. `Vid_download`.
    *   Wählen Sie **Private** (empfohlen) oder **Public** und klicken Sie auf **Create repository**.
    *   Kopieren Sie die Repository-URL (z. B. `https://github.com/DEIN_BENUTZERNAME/Vid_download.git`).

2.  **Git im lokalen Ordner initialisieren**:
    Öffnen Sie die PowerShell in Ihrem lokalen Ordner `c:\Users\cilli\OneDrive\Desktop\Vid_download` und führen Sie aus:
    ```powershell
    # Git initialisieren
    git init

    # Alle Dateien für das Commit vorbereiten
    git add .

    # Commit erstellen
    git commit -m "Initial commit - SerienStream IP & Linux support"

    # Hauptbranch festlegen
    git branch -M main

    # Remote-Repository (GitHub) verknüpfen
    git remote add origin https://github.com/DEIN_BENUTZERNAME/Vid_download.git

    # Dateien zu GitHub hochladen
    git push -u origin main
    ```

---

### Teil B: Auf dem Ionos Linux Server (Klonen & Ausführen)

1.  **Verbinden Sie sich mit Ihrem Linux-Server via SSH**:
    ```bash
    ssh user@deine-server-ip
    ```

2.  **Projekt von GitHub klonen**:
    ```bash
    git clone https://github.com/DEIN_BENUTZERNAME/Vid_download.git
    cd Vid_download
    ```
    *(Hinweis: Bei privaten Repositories werden Sie nach Ihrem GitHub-Benutzernamen und einem [Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) als Passwort gefragt).*

3.  **Installieren & Loslegen**:
    ```bash
    chmod +x install.sh
    ./install.sh
    
    # Download starten
    ./run.sh "Link to Serie/Movie" "/pfad/zu/deinen/downloads"
    ```

---

## 🛠️ Abhängigkeiten (in `requirements.txt`)
*   `requests`: Für HTTP-Anfragen.
*   `beautifulsoup4`: Zum Parsen des HTML-Quelltexts der Serien-Hubs.
*   `tqdm`: Für die visuelle Download-Fortschrittsanzeige.
*   `cloudscraper`: Zur automatischen Erkennung und Umgehung von Cloudflare-Schutzmechanismen.
*   `yt-dlp`: Leistungsstarker HLS-Streamer (.m3u8 Download).
