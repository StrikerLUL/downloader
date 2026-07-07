import requests
# MOCK SERVER ROUTING FOR OFFLINE E2E TESTING
import os
if os.environ.get("DOWNLOADER_MOCK_SERVER"):
    import urllib.parse
    mock_url = os.environ["DOWNLOADER_MOCK_SERVER"]
    parsed_mock = urllib.parse.urlparse(mock_url)
    
    import requests
    original_send = requests.Session.send
    
    def patched_send(self, request, **kwargs):
        parsed_req = urllib.parse.urlparse(request.url)
        # Rewrite URL to point to local mock server, preserving path/query
        new_url = urllib.parse.urlunparse((
            parsed_mock.scheme,
            parsed_mock.netloc,
            parsed_req.path,
            parsed_req.params,
            parsed_req.query,
            parsed_req.fragment
        ))
        request.url = new_url
        if 'Host' in request.headers:
            request.headers['Host'] = parsed_mock.netloc
        return original_send(self, request, **kwargs)
        
    requests.Session.send = patched_send
import re
from bs4 import BeautifulSoup
import os
import sys
from tqdm import tqdm
import subprocess
import time
import cloudscraper
import base64
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Thread-safe tracker for active downloads to avoid naming collisions
active_downloads = set()
active_downloads_lock = threading.Lock()
logger = logging.getLogger("downloads")

def setup_logging(verbose=False, quiet=False):
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
        
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Attempt log file in /var/log/vid_download/downloads.log
    log_dir = "/var/log/vid_download"
    log_file = os.path.join(log_dir, "downloads.log")
    
    log_file_writable = False
    try:
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("")
        log_file_writable = True
    except Exception:
        # Fallback to local workspace downloads.log
        log_file = "downloads.log"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("")
            log_file_writable = True
        except Exception:
            pass
            
    if log_file_writable:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
    # Silence verbose library loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("cloudscraper").setLevel(logging.WARNING)


class VoeDownloader:
    def __init__(self, preferred_lang="german"):
        # Erstellt einen Scraper, der wie ein echter Browser agiert
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        self.mirrors = ["juliewomanwish.com", "rebeccasciencestreet.com", "nicholasbreakplan.com", "voe.sx", "ceremonioustakeintoaccountcustomer.com"]
        self.logged_in = False
        self.preferred_lang = preferred_lang

    def load_and_login(self, email=None, password=None, base_url=None):
        if self.logged_in:
            return True
            
        login_base = base_url if base_url else "http://186.2.175.5"
        
        # Falls Zugangsdaten direkt übergeben wurden
        if email and password:
            self.logged_in = self.login(email, password, login_base)
            return self.logged_in
            
        import json
        account_file = "account.json"
        
        if os.path.exists(account_file):
            try:
                with open(account_file, "r") as f:
                    data = json.load(f)
                email_json = data.get("email")
                password_json = data.get("password")
                if email_json and password_json:
                    self.logged_in = self.login(email_json, password_json, login_base)
                    return self.logged_in
            except Exception as e:
                logger.error(f"[!] Fehler beim Laden von account.json: {e}")
        return False

    def login(self, email, password, base_url):
        logger.info(f"[*] Versuche automatischen Login für {email} auf {base_url}...")
        try:
            from urllib.parse import urljoin
            login_url = urljoin(base_url, "/login")
            
            # 1. CSRF Token holen
            res = self.scraper.get(login_url, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            token_input = soup.find("input", {"name": "_token"})
            if not token_input:
                logger.error("[!] Login-Fehler: Kein CSRF-Token auf der Seite gefunden.")
                return False
                
            csrf_token = token_input.get("value")
            
            # 2. Login absenden
            payload = {
                "_token": csrf_token,
                "email": email,
                "password": password
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": login_url
            }
            
            post_res = self.scraper.post(login_url, data=payload, headers=headers, timeout=15)
            
            if "login" not in post_res.url.lower():
                logger.info("[+] Login erfolgreich! Captcha-Bypass ist jetzt aktiv.")
                return True
            else:
                logger.error("[!] Login-Fehler: Ungültige Zugangsdaten.")
                return False
        except Exception as e:
            logger.error(f"[!] Login-Fehler: {e}")
        return False

    def rot13(self, text):
        res = []
        for c in text:
            o = ord(c)
            if 65 <= o <= 90:
                res.append(chr((o - 65 + 13) % 26 + 65))
            elif 97 <= o <= 122:
                res.append(chr((o - 97 + 13) % 26 + 97))
            else:
                res.append(c)
        return "".join(res)

    def voe_decrypt_method7(self, scrambled):
        # Strip padding from the end before reversing
        scrambled = scrambled.rstrip('!=')
        
        # 1. ROT13
        step1 = self.rot13(scrambled)
        
        # 2. Pattern replacement
        patterns = ['@$', '^^', '~@', '%?', '*~', '!!', '#&']
        step2 = step1
        for p in patterns:
            step2 = step2.replace(p, '_')
            
        # 3. Underscore-Entfernung
        step3 = step2.replace('_', '')
        
        # 4. Base64-Dekodierung
        try:
            padding = (4 - len(step3) % 4) % 4
            step4_bytes = base64.b64decode(step3 + "=" * padding)
            step4 = step4_bytes.decode('utf-8', errors='ignore')
        except Exception as e:
            return f"FAILED step 4: {e}"
            
        # 5. Zeichen-Verschiebung (-3)
        step5 = "".join(chr(ord(c) - 3) for c in step4)
        
        # 6. Umkehren (Reverse)
        step6 = step5[::-1]
        
        # 7. Letzte Base64-Dekodierung
        try:
            padding = (4 - len(step6) % 4) % 4
            step7_bytes = base64.b64decode(step6 + "=" * padding)
            return step7_bytes.decode('utf-8')
        except Exception as e:
            return f"FAILED step 7: {e}"

    def extract_xor_key(self, html):
        patterns = [
            r'window\.c\s*=\s*[\'"]([a-f0-9]+)[\'"]',
            r'const\s+key\s*=\s*[\'"]([a-f0-9]+)[\'"]',
            r'var\s+key\s*=\s*[\'"]([a-f0-9]+)[\'"]',
            r'[\'"]key[\'"]\s*:\s*[\'"]([a-f0-9]+)[\'"]',
            r'window\.c\s*=\s*([a-f0-9]+)\b'
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                return m.group(1)
        return None

    def voe_decrypt_xor(self, scrambled, key):
        scrambled = scrambled[::-1]
        mapping = {'!': '0', '@': '1', '#': '2', '&': '3', '%': '4', '?': '5', '~': '6', '*': '7', '^': '8', '$': '9'}
        for k, v in mapping.items():
            scrambled = scrambled.replace(k, v)
        std_b64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        voe_b64 = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/"
        trans = str.maketrans(voe_b64, std_b64)
        translated = scrambled.translate(trans)
        try:
            decoded_bytes = base64.b64decode(translated + "===")
            res = ""
            for i, b in enumerate(decoded_bytes):
                res += chr(b ^ ord(key[i % len(key)]))
            return res
        except Exception as e:
            return f"FAILED: {e}"

    def parse_series_info(self, url):
        patterns = [
            r'/anime/stream/([^/]+)/staffel-([^/]+)/episode-([^/&#?]+)',
            r'/(?:serie|stream)/([^/]+)/staffel-([^/]+)/episode-([^/&#?]+)'
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                series_name = m.group(1).replace('-', ' ').title()
                try:
                    season_num = int(m.group(2))
                    season_str = f"S{season_num:02d}"
                except ValueError:
                    season_str = f"S_{m.group(2)}"
                try:
                    episode_num = int(m.group(3))
                    episode_str = f"E{episode_num:02d}"
                except ValueError:
                    episode_str = f"E_{m.group(3)}"
                return f"{series_name} - {season_str}{episode_str}"
        return None

    def _has_aria2c(self):
        """Prüft ob aria2c installiert ist."""
        try:
            subprocess.run(["aria2c", "--version"], capture_output=True, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def fast_download_file(self, direct_link, dest_path, referer):
        """Schneller Download mit aria2c (16 parallele Verbindungen) oder Fallback auf Python-Download."""
        dest_folder = os.path.dirname(dest_path)
        filename = os.path.basename(dest_path)
        
        if self._has_aria2c():
            logger.info(f"[⚡] Nutze aria2c mit 16 parallelen Verbindungen für maximale Geschwindigkeit...")
            cmd = [
                "aria2c",
                direct_link,
                "-x", "16",
                "-s", "16",
                "--min-split-size=1M",
                "--disk-cache=64M",
                "-d", dest_folder,   # Zielordner
                "-o", filename,      # Dateiname
                f"--referer={referer}",
                "--file-allocation=none",
                "--console-log-level=notice",
                "--summary-interval=5",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]
            try:
                result = subprocess.run(cmd)
                if result.returncode == 0:
                    logger.info(f"[+] Download erfolgreich abgeschlossen: {dest_path}")
                    return True
                else:
                    logger.warning(f"[!] aria2c beendet mit Code {result.returncode}. Versuche Python-Fallback...")
            except Exception as e:
                logger.warning(f"[!] aria2c Fehler: {e}. Versuche Python-Fallback...")
        else:
            logger.info("[*] aria2c nicht installiert. Nutze Python-Download (für mehr Speed: sudo apt install aria2)")

        # Python-Fallback mit 4MB Buffer und Download Resume
        logger.info(f"[*] Downloade Video nach: {dest_path}")
        try:
            initial_pos = 0
            if os.path.exists(dest_path):
                initial_pos = os.path.getsize(dest_path)
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": referer
            }
            if initial_pos > 0:
                headers["Range"] = f"bytes={initial_pos}-"
                
            r = self.scraper.get(direct_link, stream=True, timeout=60, headers=headers)
            
            if r.status_code == 416:
                logger.info(f"[+] Datei bereits vollständig heruntergeladen: {dest_path}")
                return True
                
            if r.status_code == 206:
                mode = 'ab'
                content_len = int(r.headers.get('content-length', 0))
                total = initial_pos + content_len
                logger.info(f"[*] Setze Download fort ab Byte {initial_pos}. Verbleibend: {content_len} Bytes. Gesamt: {total} Bytes.")
                start_pos = initial_pos
            elif r.status_code == 200:
                mode = 'wb'
                total = int(r.headers.get('content-length', 0))
                start_pos = 0
                if initial_pos > 0:
                    logger.info(f"[*] Server unterstützt Fortsetzen nicht oder Datei wird neu heruntergeladen. Überschreibe {dest_path}.")
            else:
                r.raise_for_status()
                mode = 'wb'
                total = int(r.headers.get('content-length', 0))
                start_pos = 0
                
            if total < 500000 and start_pos == 0:
                logger.error("[!] Fehler: Der Link führt nicht zu einer Videodatei (Inhalt zu klein).")
                return False
                
            bar = tqdm(total=total, initial=start_pos, unit='iB', unit_scale=True, desc=filename[:30])
            with open(dest_path, mode) as f:
                for chunk in r.iter_content(4194304):  # 4MB Chunks
                    if chunk:
                        bar.update(len(chunk))
                        f.write(chunk)
            bar.close()
            logger.info(f"[+] Download erfolgreich!")
            return True
        except Exception as e:
            logger.error(f"[!] Fehler beim Download: {e}")
            return False

    def fetch_page(self, url, referer=None):
        logger.info(f"[*] Lade Seite: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": referer if referer else url
        }
        
        # Falls es ein Weiterleitungs-Link ist, versuchen wir die DDoS-Guard / Cloudflare Blockade zu umgehen
        is_redirect_link = "/r?t=" in url or "/redirect/" in url or "/r/" in url
        if is_redirect_link:
            logger.info("[*] Weiterleitungs-Link erkannt. Versuche Direct-Location-Bypass...")
            try:
                # Mit allow_redirects=False abfragen, um die 302 Location direkt zu erhalten
                res = self.scraper.get(url, headers=headers, allow_redirects=False, timeout=15)
                location = res.headers.get("Location")
                if location:
                    logger.info(f"[+] Weiterleitungs-Ziel gefunden: {location}")
                    # Video-ID extrahieren
                    video_id_match = re.search(r'/e/([a-z0-9]{12})', location)
                    if video_id_match:
                        video_id = video_id_match.group(1)
                        logger.info(f"[+] Video-ID erfolgreich extrahiert: {video_id}")
                        
                        # Alle Mirrors nacheinander durchprobieren
                        for mirror in self.mirrors:
                            mirror_url = f"https://{mirror}/e/{video_id}"
                            logger.info(f"[*] Versuche Mirror-Abfrage: {mirror_url}")
                            try:
                                m_res = self.scraper.get(mirror_url, headers=headers, timeout=15)
                                if m_res.status_code == 200:
                                    # Prüfen, ob eine JS-Weiterleitung auf die aktive Domain vorliegt
                                    if "window.location.href" in m_res.text:
                                        m_js = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", m_res.text)
                                        if m_js:
                                            active_url = m_js.group(1)
                                            logger.info(f"[+] Aktive Player-URL über JS-Redirect erkannt: {active_url}")
                                            # Die aktive Player-Seite laden
                                            headers["Referer"] = mirror_url
                                            active_res = self.scraper.get(active_url, headers=headers, timeout=15)
                                            logger.info(f"[+] Aktive Seite geladen. Status: {active_res.status_code} | Länge: {len(active_res.text)} Bytes")
                                            return active_res.text, active_res.url
                                    
                                    # Fallback falls keine JS-Weiterleitung vorliegt aber die Seite geladen wurde
                                    if "application/json" in m_res.text or "window.c" in m_res.text:
                                        logger.info("[+] Mirror-Seite direkt geladen.")
                                        return m_res.text, m_res.url
                            except Exception as mirror_err:
                                logger.warning(f"[!] Fehler bei Mirror {mirror}: {mirror_err}")
            except Exception as redirect_err:
                logger.warning(f"[!] Fehler bei Direct-Location-Bypass: {redirect_err}. Weiche auf Standard-Abfrage aus...")

        # Standard-Abfrage falls der Bypass fehlschlägt oder es keine Weiterleitungs-URL ist
        res = self.scraper.get(url, headers=headers, timeout=15)
        logger.info(f"[*] Status: {res.status_code} | Finale URL: {res.url} | Länge: {len(res.text)} Bytes")
        
        # Cloudflare oder Blockierungserkennung
        if "cloudflare" in res.text.lower() or "just a moment" in res.text.lower():
            logger.warning("[!] Warnung: Cloudflare-Schutz auf dieser Seite erkannt!")
        elif res.status_code == 403:
            logger.warning("[!] Warnung: Zugriff verweigert (403 Forbidden). Möglicherweise wird die IP-Adresse blockiert.")
            
        # Keine JS-Weiterleitungen folgen für Serien-Hub-Seiten, da diese Seiten keine Player-Redirects haben
        is_series_hub = "aniworld.to" in res.url or "s.to" in res.url or "serienstream.to" in res.url or "/serie/" in res.url or "/stream/" in res.url
        if is_series_hub:
            return res.text, res.url
        # JS-Weiterleitungen folgen
        for _ in range(3): # Maximal 3 Weiterleitungen
            if "window.location.href" in res.text:
                m = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", res.text)
                if m:
                    next_url = m.group(1)
                    if next_url.startswith('//'):
                        next_url = 'https:' + next_url
                    elif next_url.startswith('/'):
                        from urllib.parse import urlparse
                        parsed = urlparse(res.url)
                        next_url = f"{parsed.scheme}://{parsed.netloc}{next_url}"
                    logger.info(f"[*] JS-Weiterleitung erkannt: {next_url}")
                    headers["Referer"] = res.url
                    res = self.scraper.get(next_url, headers=headers, timeout=15)
                    logger.info(f"[*] Status (JS): {res.status_code} | URL: {res.url} | Länge: {len(res.text)} Bytes")
                else:
                    break
            else:
                break
        return res.text, res.url

    def decrypt_page_source(self, html):
        """Versucht, die verschlüsselte Video-Quelle aus dem Quellcode zu extrahieren und zu entschlüsseln."""
        try:
            # 1. JSON-Datenblock finden
            json_match = re.search(r'<script type="application/json">([^<]+)</script>', html)
            if not json_match:
                return None
            
            import json
            json_data = json.loads(json_match.group(1))
            if not json_data or not isinstance(json_data, list):
                return None
            scrambled = json_data[0]
            
            # 2. Entschlüsseln versuchen
            decrypted_str = None
            
            # Zuerst neue XOR-Methode versuchen
            key = self.extract_xor_key(html)
            if key:
                logger.info(f"[*] XOR Key für Entschlüsselung gefunden: {key}")
                decrypted_str = self.voe_decrypt_xor(scrambled, key)
                if decrypted_str.startswith("FAILED") or "direct_access_url" not in decrypted_str:
                    logger.warning("[!] Neue XOR-Entschlüsselung fehlgeschlagen oder unvollständig. Versuche Methode 7...")
                    decrypted_str = None
            
            if not decrypted_str:
                decrypted_str = self.voe_decrypt_method7(scrambled)
                
            if decrypted_str.startswith("FAILED"):
                logger.error(f"[!] Entschlüsselung fehlgeschlagen: {decrypted_str}")
                return None
                
            decrypted_json = json.loads(decrypted_str)
            
            # 3. Direct Access MP4 oder master.m3u8 HLS extrahieren
            direct_url = decrypted_json.get("direct_access_url")
            hls_url = decrypted_json.get("source")
            
            # Überprüfen, ob es sich um ein echtes Video handelt (kein Testvideo)
            if direct_url and "test-videos" not in direct_url and "bigbuckbunny" not in direct_url:
                logger.info("[+] Direkte MP4-Download-URL erfolgreich entschlüsselt!")
                return direct_url
            elif hls_url and "test-videos" not in hls_url and "bigbuckbunny" not in hls_url:
                logger.info("[+] HLS (.m3u8) Stream-URL erfolgreich entschlüsselt!")
                return hls_url
        except Exception as e:
            logger.error(f"[!] Fehler bei der Quelltext-Entschlüsselung: {e}")
        return None

    def extract_direct_url(self, text):
        """Sucht im Text nach typischen Video-Streaming-Links."""
        text = text.replace(r'\/', '/') # Escapes entfernen
        patterns = [
            r'https?://[a-z0-9.-]+\.cloudwindow-route\.com/[^"\'<>]+(?:master\.m3u8|\.mp4)[^"\'<>]*',
            r'https?://[a-z0-9.-]+\.voe\.sx/[^"\'<>]+(?:master\.m3u8|\.mp4)[^"\'<>]*',
        ]
        for p in patterns:
            matches = re.findall(p, text)
            for m in matches:
                if "test-videos" not in m and "bigbuckbunny" not in m:
                    return m
        return None

    def extract_voe_from_aniworld(self, html, base_url):
        """Sucht auf einer Episodenseite (AniWorld, s.to, serienstream) nach VOE-Hostern und wählt den besten Link."""
        def get_priority(lang_id, lang_label):
            lang_id = str(lang_id or "").strip()
            lang_label = str(lang_label or "").lower().strip()
            
            pref = self.preferred_lang.lower()
            
            # s.to/aniworld IDs:
            # 1 = German (Dub)
            # 2 = English (Dub/Sub)
            # 3 = German Sub (Subbed)
            
            if pref == "german":
                if lang_id == "1" or ("deutsch" in lang_label and "sub" not in lang_label):
                    return 1
                if lang_id == "3" or "sub" in lang_label:
                    return 2
                if lang_id == "2" or "english" in lang_label or "englisch" in lang_label:
                    return 3
            elif pref == "gersub":
                if lang_id == "3" or ("deutsch" in lang_label and "sub" in lang_label):
                    return 1
                if lang_id == "1" or ("deutsch" in lang_label and "sub" not in lang_label):
                    return 2
                if lang_id == "2" or "english" in lang_label or "englisch" in lang_label:
                    return 3
            elif pref in ["english", "engsub"]:
                if lang_id == "2" or "english" in lang_label or "englisch" in lang_label:
                    return 1
                if lang_id == "1" or ("deutsch" in lang_label and "sub" not in lang_label):
                    return 2
                if lang_id == "3" or "sub" in lang_label:
                    return 3
            
            if "deutsch" in lang_label:
                return 1.5
            if "english" in lang_label or "englisch" in lang_label:
                return 3.5
            return 99

        try:
            soup = BeautifulSoup(html, 'html.parser')
            voe_options = []
            
            # Findet alle Tags (a, button, etc.), die Hoster-Redirect-Links/Play-URLs enthalten könnten
            for tag in soup.find_all(lambda t: t.name in ['a', 'button'] or t.has_attr('data-play-url')):
                href = tag.get('href') or tag.get('data-play-url')
                if not href:
                    continue
                
                # Muss eine Weiterleitung oder ein Play-URL sein
                is_redirect = '/redirect/' in href or '/r?' in href or href.startswith('/r/') or 'data-play-url' in tag.attrs
                if not is_redirect:
                    continue
                
                # Ist es VOE?
                text = tag.text.upper()
                parent_text = tag.parent.text.upper() if tag.parent else ""
                grandparent = tag.parent.parent if tag.parent else None
                grandparent_text = grandparent.text.upper() if grandparent else ""
                
                is_voe = (
                    tag.get('data-provider-name') == 'VOE' or
                    "VOE" in text or
                    "VOE" in parent_text or
                    "VOE" in grandparent_text or
                    "voe" in href.lower()
                )
                if not is_voe:
                    continue
                
                # Attribute für Sprache ermitteln
                lang_key = tag.get('data-lang-key') or tag.get('data-language-id')
                if not lang_key and grandparent:
                    lang_key = grandparent.get('data-lang-key') or grandparent.get('data-language-id')
                
                lang_label = tag.get('data-language-label') or tag.get('title') or ""
                if not lang_label and grandparent:
                    lang_label = grandparent.get('data-language-label') or grandparent.get('title') or ""
                
                # Priorität berechnen
                pri = get_priority(lang_key, lang_label)
                
                # Absoluten Link erstellen
                from urllib.parse import urljoin
                abs_url = urljoin(base_url, href)
                
                voe_options.append({
                    'url': abs_url,
                    'priority': pri,
                    'label': lang_label or ("Deutsch" if pri == 1 else "Englisch" if pri == 3 else "Unbekannt")
                })
                
            if not voe_options:
                return None
                
            # Sortieren nach Priorität (kleinste zuerst)
            voe_options.sort(key=lambda x: x['priority'])
            
            selected = voe_options[0]
            logger.info(f"[+] Serien-Hoster erkannt: VOE ({selected['label']}) -> {selected['url']}")
            return selected['url']
        except Exception as e:
            logger.error(f"[!] Fehler beim Extrahieren des Serien-Links: {e}")
        return None

    def get_direct_link(self, url, email=None, password=None):
        logger.info(f"[*] Analysiere: {url}")
        try:
            # 0. Falls es eine Serien-Hub-URL ist, den Hoster-Link extrahieren
            is_series_hub = "aniworld.to" in url or "s.to" in url or "serienstream.to" in url or "/serie/" in url or "/stream/" in url
            original_url = url
            if is_series_hub:
                logger.info(f"[*] Serien-Hub-URL erkannt: {url}")
                html, final_url = self.fetch_page(url)
                voe_redirect = self.extract_voe_from_aniworld(html, final_url)
                if voe_redirect:
                    url = voe_redirect
                else:
                    logger.error("[!] Fehler: Kein VOE-Hoster auf der Episodenseite gefunden.")
                    return None

            # 1. Hauptseite laden (inklusive Weiterleitungs-Handling)
            html, final_url = self.fetch_page(url, referer=original_url if is_series_hub else None)
            
            # Falls wir die Captcha-Bridge geladen haben, versuchen wir den automatischen Login
            if "frameBridge" in html or "g-recaptcha" in html or "cf-challenge" in html:
                logger.warning("[!] Captcha-Blockade oder Login-Abfrage erkannt.")
                from urllib.parse import urlparse
                parsed = urlparse(final_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                
                # Wenn wir übergebene Zugangsdaten oder account.json haben, loggen wir uns ein
                if not self.logged_in:
                    self.load_and_login(email, password, base_url)
                
                # Wenn wir immer noch nicht eingeloggt sind und im interaktiven Modus sind, fragen wir nach den Zugangsdaten
                if not self.logged_in and sys.stdin.isatty():
                    logger.info("[*] Um den Schutz vollautomatisch zu umgehen, erstelle dir ein kostenloses Konto auf SerienStream/s.to.")
                    logger.info("[*] Gib deine Anmeldedaten ein (werden lokal in account.json gespeichert):")
                    email_input = input("E-Mail: ").strip()
                    password_input = input("Passwort: ").strip()
                    if email_input and password_input:
                        import json
                        with open("account.json", "w") as f:
                            json.dump({"email": email_input, "password": password_input}, f)
                        self.load_and_login(email_input, password_input, base_url)
                
                if self.logged_in:
                    logger.info("[*] Lade Seite nach erfolgreichem Login erneut...")
                    html, final_url = self.fetch_page(url, referer=original_url if is_series_hub else None)
            
            # 2. Versuch der direkten Dekodierung über Methode 7 (Sehr robust!)
            direct_link = self.decrypt_page_source(html)
            if direct_link:
                return direct_link

            # Suche im rohen Quelltext als Fallback
            link = self.extract_direct_url(html)
            if link: return link

            # 3. Video-ID finden (Zufälliger 12-stelliger Code) als Fallback
            video_id = None
            clean_text = html.replace(r'\/', '/')
            id_matches = re.findall(r"['\"]([a-z0-9]{12})['\"]", clean_text)
            for mid in id_matches:
                if mid in ["bigbuckbunny", "generate-tok", "session-sync"]: continue
                if any(c.isdigit() for c in mid) and any(c.isalpha() for c in mid):
                    video_id = mid
                    break
            
            if not video_id:
                m = re.search(r"/(?:e/)?([a-z0-9]{12})(?:$|\?|/)", final_url)
                if m and m.group(1) != "bigbuckbunny": video_id = m.group(1)

            if not video_id:
                logger.error("[!] Fehler: Video-ID konnte nicht im Quelltext gefunden werden.")
                if len(html) < 2000:
                    logger.info(f"[*] Kompletter Quelltext der Seite:\n{html}")
                else:
                    logger.info(f"[*] Quelltext-Vorschau (erste 400 Zeichen): {repr(html[:400])}")
                title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
                if title_match:
                    logger.info(f"[*] HTML Titel der Seite: '{title_match.group(1).strip()}'")
                return None
            
            logger.info(f"[*] Video-ID erkannt: {video_id}")

            # 4. Session synchronisieren
            logger.info("[*] Synchronisiere Session...")
            try:
                t_res = self.scraper.get("https://voe.sx/api2/session/generate-token", headers={"Referer": url})
                token = t_res.json().get("token")
                if token:
                    self.scraper.get(f"https://voe.sx/session/sync?token={token}&redirect={url}")
            except: pass

            # 5. Alle Mirrors nach einem Download-Button oder Link absuchen
            for domain in self.mirrors:
                dl_url = f"https://{domain}/{video_id}/download"
                logger.info(f"[*] Prüfe Mirror {domain}...")
                try:
                    res = self.scraper.get(dl_url, headers={"Referer": url}, timeout=10)
                    if "window.location.href =" in res.text:
                        m = re.search(r"window\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", res.text)
                        if m: res = self.scraper.get(m.group(1), headers={"Referer": dl_url})
                    
                    link = self.extract_direct_url(res.text)
                    if link: return link
                except: continue

            # Letzter automatischer Versuch
            for domain in [final_url.split("/")[2], "voe.sx"]:
                check_url = f"https://{domain}/{video_id}"
                logger.info(f"[*] Versuche Extraktion via {domain}...")
                return check_url

        except Exception as e:
            logger.error(f"[!] Analysefehler: {e}")
        return None

    def download(self, url, dest_folder, email=None, password=None):
        logger.info("--- VOE Downloader Start ---")
        direct_link = self.get_direct_link(url, email, password)
        
        # Falls der gefundene Link die Website selbst ist, verwerfen
        if direct_link and (direct_link == url or "/access/" in direct_link):
            direct_link = None

        if not direct_link:
            logger.error("[!] AUTOMATISIERUNG DURCH WEBSITE-SCHUTZ GESCHEITERT")
            logger.info("[*] Die Website blockiert automatisierte Anfragen.")
            if sys.stdin.isatty():
                logger.info("[*] So holst du dir den Link in 10 Sekunden selbst:")
                logger.info("    1. Öffne das Video im Browser (Firefox/Chrome).")
                logger.info("    2. Drücke F12 -> Reiter 'Netzwerk' (Network).")
                logger.info("    3. Suche oben im Filter nach 'mp4'.")
                logger.info("    4. Kopiere die URL (Rechtsklick -> Adresse kopieren) und füge sie hier ein.")
                
                manual = input("\nManueller Video-Link (oder Enter zum Abbrechen): ").strip()
                if not manual: return False
                direct_link = manual
            else:
                logger.error("[!] Skript läuft im nicht-interaktiven Modus. Manueller Link-Eingabe übersprungen.")
                return False

        # Dateiname ermitteln oder generieren
        series_filename = self.parse_series_info(url)

        # Dateiname bestimmen
        if series_filename:
            filename = f"{series_filename}.mp4"
        else:
            name_match = re.search(r"[?&]n=([^&]+)", direct_link)
            filename = requests.utils.unquote(name_match.group(1)) if name_match else os.path.basename(direct_link.split('?')[0])
            filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
            if len(filename) > 100: filename = filename[:90] + ".mp4"
            if not filename or filename == "_": filename = f"video_{int(time.time())}.mp4"

        if not os.path.exists(dest_folder): os.makedirs(dest_folder)

        # Avoid collision with other concurrent threads downloading the same file
        with active_downloads_lock:
            base_name = series_filename if series_filename else f"video_{int(time.time())}"
            temp_path = os.path.join(dest_folder, f"{base_name}.mp4")
            counter = 1
            while temp_path in active_downloads:
                base_name = f"{series_filename or 'video'}_{counter}"
                temp_path = os.path.join(dest_folder, f"{base_name}.mp4")
                counter += 1
            active_downloads.add(temp_path)
            
        try:
            # Download-Entscheidung: yt-dlp für HLS-Streams, aria2c/direkt für MP4
            if ".m3u8" in direct_link:
                logger.info(f"[*] HLS-Stream erkannt. Nutze yt-dlp mit parallelen Fragments...")
                out_template = os.path.join(dest_folder, f"{base_name}.%(ext)s")
                    
                cmd = [
                    sys.executable, "-m", "yt_dlp",
                    direct_link,
                    "--referer", url,
                    "-o", out_template,
                    "--retries", "10",
                    "--fragment-retries", "10",
                ]
                if self._has_aria2c():
                    cmd.extend([
                        "--downloader", "aria2c",
                        "--downloader-args", "aria2c:--min-split-size=1M --max-connection-per-server=16 --split=16 --disk-cache=64M",
                        "--concurrent-fragments", "16"
                    ])
                else:
                    cmd.extend([
                        "--concurrent-fragments", "8"
                    ])
                try:
                    subprocess.run(cmd, check=True)
                    return True
                except Exception as e:
                    logger.error(f"[!] Fehler beim Ausführen von yt-dlp: {e}")
                    return False
            else:
                dest_path = os.path.join(dest_folder, filename)
                with active_downloads_lock:
                    if temp_path in active_downloads:
                        active_downloads.remove(temp_path)
                        
                with active_downloads_lock:
                    base_f, ext_f = os.path.splitext(filename)
                    counter_f = 1
                    while dest_path in active_downloads:
                        filename = f"{base_f}_{counter_f}{ext_f}"
                        dest_path = os.path.join(dest_folder, filename)
                        counter_f += 1
                    active_downloads.add(dest_path)
                    
                return self.fast_download_file(direct_link, dest_path, url)
        finally:
            with active_downloads_lock:
                if 'temp_path' in locals() and temp_path in active_downloads:
                    active_downloads.remove(temp_path)
                if 'dest_path' in locals() and dest_path in active_downloads:
                    active_downloads.remove(dest_path)

def is_url(string):
    return string.startswith("http://") or string.startswith("https://") or "://" in string

def get_episodes_in_season(scraper, base_url, season):
    clean_base = base_url
    for pattern in [r'/staffel-\d+.*', r'/episode-\d+.*']:
        clean_base = re.sub(pattern, '', clean_base)
    clean_base = clean_base.rstrip('/')
    
    season_url = f"{clean_base}/staffel-{season}"
    logger.info(f"[*] Lade Staffelseite zur Episodenerkennung: {season_url}")
    try:
        res = scraper.get(season_url, timeout=15)
        if res.status_code == 200:
            matches = re.findall(rf'staffel-{season}/episode-([^/&#?"]+)', res.text)
            if matches:
                episodes = []
                for m in matches:
                    try:
                        episodes.append(int(m))
                    except ValueError:
                        pass
                if episodes:
                    detected = sorted(list(set(episodes)))
                    logger.info(f"[+] Erkannte Episoden in Staffel {season}: {detected}")
                    return detected
            logger.warning(f"[!] Keine Episoden-Links im HTML von Staffel {season} gefunden.")
        else:
            logger.warning(f"[!] Staffelseite lieferte Status: {res.status_code}")
    except Exception as e:
        logger.error(f"[!] Fehler beim Laden der Staffelseite {season_url}: {e}")
    return []

def generate_template_urls(template, from_str, to_str):
    try:
        start = int(from_str)
        end = int(to_str)
    except (ValueError, TypeError):
        logger.error("[!] Bereichsgrenzen --from und --to müssen Ganzzahlen sein.")
        return []
    
    if start > end:
        logger.error("[!] Ungültiger Bereich: --from ist größer als --to.")
        return []
    
    width = 1
    if from_str.startswith('0') and len(from_str) > 1:
        width = len(from_str)
    elif to_str.startswith('0') and len(to_str) > 1:
        width = len(to_str)
        
    urls = []
    for val in range(start, end + 1):
        try:
            if "{}" in template:
                padded_val = f"{val:0{width}d}"
                formatted = template.replace("{}", padded_val)
                urls.append(formatted)
            else:
                urls.append(template.format(val))
        except Exception as e:
            logger.error(f"[!] Fehler beim Formatieren des Templates {template} mit Wert {val}: {e}")
    return urls

def generate_season_range_urls(range_str, base_url, scraper):
    pattern = r'^S(\d+)E(\d+)-S(\d+)E(\d+)$'
    match = re.match(pattern, range_str, re.IGNORECASE)
    if not match:
        logger.error(f"[!] Ungültiges Bereichsformat: {range_str}. Erwartet: SXXEXX-SYYEYY")
        return []
        
    s1, e1 = int(match.group(1)), int(match.group(2))
    s2, e2 = int(match.group(3)), int(match.group(4))
    
    if s1 > s2 or (s1 == s2 and e1 > e2):
        logger.error(f"[!] Ungültiger Bereich: Start liegt nach Ende ({range_str}).")
        return []
        
    if not base_url:
        logger.error("[!] Basis-URL wird für die Generierung des Staffelbereichs benötigt.")
        return []
        
    clean_base = base_url
    for pat in [r'/staffel-\d+.*', r'/episode-\d+.*']:
        clean_base = re.sub(pat, '', clean_base)
    clean_base = clean_base.rstrip('/')
    
    urls = []
    for s in range(s1, s2 + 1):
        if s1 == s2:
            episodes = list(range(e1, e2 + 1))
        else:
            episodes = get_episodes_in_season(scraper, clean_base, s)
            if not episodes:
                logger.warning(f"[!] Konnte Episoden für Staffel {s} nicht ermitteln. Verwende Fallback-Sequenz.")
                if s == s1:
                    episodes = list(range(e1, e1 + 24))
                elif s == s2:
                    episodes = list(range(1, e2 + 1))
                else:
                    episodes = list(range(1, 24))
                    
        for ep in episodes:
            if s == s1 and ep < e1:
                continue
            if s == s2 and ep > e2:
                continue
            urls.append(f"{clean_base}/staffel-{s}/episode-{ep}")
            
    return urls

def generate_urls_from_range_args(range_str, from_str, to_str, base_url, scraper):
    if range_str and re.match(r'^S\d+E\d+-S\d+E\d+$', range_str, re.IGNORECASE):
        return generate_season_range_urls(range_str, base_url, scraper)
        
    template = None
    if range_str and "{}" in range_str:
        template = range_str
    elif base_url and "{}" in base_url:
        template = base_url
        
    if template:
        if not from_str or not to_str:
            logger.error("[!] Bereichsgrenzen --from und --to werden für das Template benötigt.")
            return []
            
        generated = generate_template_urls(template, from_str, to_str)
        urls = []
        for item in generated:
            if is_url(item):
                urls.append(item)
            elif base_url:
                s_ep_match = re.match(r'^S(\d+)E(\d+)$', item, re.IGNORECASE)
                if s_ep_match:
                    s = int(s_ep_match.group(1))
                    ep = int(s_ep_match.group(2))
                    part = f"staffel-{s}/episode-{ep}"
                else:
                    part = item
                
                clean_base = base_url
                for pat in [r'/staffel-\d+.*', r'/episode-\d+.*']:
                    clean_base = re.sub(pat, '', clean_base)
                clean_base = clean_base.rstrip('/')
                urls.append(f"{clean_base}/{part.lstrip('/')}")
            else:
                urls.append(item)
        return urls
        
    logger.error("[!] Kein gültiges Bereichsformat oder Template angegeben.")
    return []

def download_single_worker(url, dest_folder, email, password, lang):
    try:
        downloader = VoeDownloader(preferred_lang=lang)
        success = downloader.download(url, dest_folder, email=email, password=password)
        return url, success
    except Exception as e:
        logger.error(f"[!] Unbehandelter Fehler beim Download von {url}: {e}", exc_info=True)
        return url, False

def download_batch(urls, dest_folder, email, password, lang, max_workers):
    logger.info(f"[*] Starte Batch-Download von {len(urls)} URLs mit {max_workers} Workern...")
    seen = set()
    unique_urls = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)
            
    if not unique_urls:
        logger.warning("[!] Keine URLs zum Herunterladen vorhanden.")
        return {}
        
    if max_workers <= 0:
        logger.warning(f"[!] Ungültige Worker-Anzahl {max_workers}. Verwende Standardwert 4.")
        max_workers = 4
    elif max_workers > 32:
        logger.warning(f"[!] Worker-Anzahl {max_workers} ist sehr hoch. Begrenze auf 32.")
        max_workers = 32
        
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(download_single_worker, url, dest_folder, email, password, lang): url
            for url in unique_urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                url, success = future.result()
                results[url] = success
                if success:
                    logger.info(f"[+] Batch-Download erfolgreich: {url}")
                else:
                    logger.error(f"[!] Batch-Download fehlgeschlagen: {url}")
            except Exception as e:
                logger.error(f"[!] Thread-Ausführung fehlgeschlagen für {url}: {e}")
                results[url] = False
    return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VOE & SerienStream Video Downloader CLI")
    parser.add_argument("url", nargs="?", help="Die URL des Videos oder der Serien-Episode")
    parser.add_argument("output", nargs="?", help="Zielordner, in den das Video gespeichert werden soll")
    parser.add_argument("--urls", help="Pfad zu einer Textdatei mit einer URL pro Zeile")
    parser.add_argument("--workers", type=int, default=4, help="Anzahl der parallelen Worker-Threads (Standard: 4)")
    parser.add_argument("--batch", nargs="+", help="Liste von URLs zum Herunterladen (durch Leerzeichen getrennt)")
    parser.add_argument("--range", help="Staffelbereich-Generierungs-Flag (Format: 'S01E01-S01E10' oder ein URL-Template mit '{}')")
    parser.add_argument("--from", dest="from_val", help="Startwert für den Bereich")
    parser.add_argument("--to", dest="to_val", help="Endwert für den Bereich")
    parser.add_argument("--email", "-e", help="E-Mail für s.to/aniworld.to Login (zur Umgehung von Captchas)")
    parser.add_argument("--password", "-p", help="Passwort für s.to/aniworld.to Login")
    parser.add_argument("--lang", "-l", default="german", choices=["german", "english", "gersub", "engsub"], help="Bevorzugte Sprache")
    parser.add_argument("--verbose", "-v", action="store_true", help="Ausführliche Logging-Ausgabe (DEBUG Level)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Stumme Logging-Ausgabe (nur ERROR Level)")
    args = parser.parse_args()
    
    if args.verbose and args.quiet:
        setup_logging(verbose=False, quiet=False)
    else:
        setup_logging(verbose=args.verbose, quiet=args.quiet)
        
    logger.info("--- VOE Video Downloader CLI ---")
    
    is_batch_mode = bool(args.urls or args.batch or args.range)
    
    urls_to_download = []
    dest_folder = args.output or "."
    if is_batch_mode and args.url and not is_url(args.url) and not args.output:
        dest_folder = args.url
    
    if args.urls:
        if not os.path.exists(args.urls):
            logger.error(f"[!] Datei nicht gefunden: {args.urls}")
            sys.exit(1)
        try:
            with open(args.urls, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.split("#")[0].strip()
                    if line:
                        urls_to_download.append(line)
        except Exception as e:
            logger.error(f"[!] Fehler beim Lesen der URL-Datei {args.urls}: {e}")
            sys.exit(1)
            
    if args.batch:
        batch_args = args.batch
        if batch_args:
            if not is_url(batch_args[-1]):
                extracted_dest = batch_args[-1]
                batch_urls = batch_args[:-1]
            else:
                extracted_dest = None
                batch_urls = batch_args
                
            dest_folder = args.output or extracted_dest or dest_folder
            urls_to_download.extend(batch_urls)
            
    if args.range:
        temp_downloader = VoeDownloader(preferred_lang=args.lang)
        if args.email and args.password:
            temp_downloader.load_and_login(args.email, args.password)
        base_url = args.url
        range_urls = generate_urls_from_range_args(args.range, args.from_val, args.to_val, base_url, temp_downloader.scraper)
        urls_to_download.extend(range_urls)
        
    if not is_batch_mode:
        u = args.url
        if not u:
            if sys.stdin.isatty():
                u = input("Video URL: ").strip()
            else:
                logger.error("[!] Fehler: Keine URL angegeben und keine interaktive Eingabe möglich.")
                sys.exit(1)
                
        if not u:
            sys.exit(0)
            
        o = args.output
        if not o:
            if sys.stdin.isatty():
                o = input("Zielordner (Standard '.'): ").strip() or "."
            else:
                o = "."
                
        downloader = VoeDownloader(preferred_lang=args.lang)
        success = downloader.download(u, o, email=args.email, password=args.password)
        sys.exit(0 if success else 1)
    else:
        results = download_batch(urls_to_download, dest_folder, args.email, args.password, args.lang, args.workers)
        sys.exit(0)
