import requests
import re
from bs4 import BeautifulSoup
import os
import sys
from tqdm import tqdm
import subprocess
import time
import cloudscraper
import base64

class VoeDownloader:
    def __init__(self, preferred_lang="german"):
        # Erstellt einen Scraper, der wie ein echter Browser agiert
        self.scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
        self.mirrors = ["rebeccasciencestreet.com", "nicholasbreakplan.com", "voe.sx", "ceremonioustakeintoaccountcustomer.com"]
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
                print(f"[!] Fehler beim Laden von account.json: {e}")
        return False

    def login(self, email, password, base_url):
        print(f"[*] Versuche automatischen Login für {email} auf {base_url}...")
        try:
            from urllib.parse import urljoin
            login_url = urljoin(base_url, "/login")
            
            # 1. CSRF Token holen
            res = self.scraper.get(login_url, timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            token_input = soup.find("input", {"name": "_token"})
            if not token_input:
                print("[!] Login-Fehler: Kein CSRF-Token auf der Seite gefunden.")
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
                print("[+] Login erfolgreich! Captcha-Bypass ist jetzt aktiv.")
                return True
            else:
                print("[!] Login fehlgeschlagen: Ungültige Zugangsdaten.")
                return False
        except Exception as e:
            print(f"[!] Login-Fehler: {e}")
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

    def fetch_page(self, url, referer=None):
        print(f"[*] Lade Seite: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": referer if referer else url
        }
        res = self.scraper.get(url, headers=headers, timeout=15)
        print(f"[*] Status: {res.status_code} | Finale URL: {res.url} | Länge: {len(res.text)} Bytes")
        
        # Cloudflare oder Blockierungserkennung
        if "cloudflare" in res.text.lower() or "just a moment" in res.text.lower():
            print("[!] Warnung: Cloudflare-Schutz auf dieser Seite erkannt!")
        elif res.status_code == 403:
            print("[!] Warnung: Zugriff verweigert (403 Forbidden). Möglicherweise wird die IP-Adresse blockiert.")
            
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
                    print(f"[*] JS-Weiterleitung erkannt: {next_url}")
                    headers["Referer"] = res.url
                    res = self.scraper.get(next_url, headers=headers, timeout=15)
                    print(f"[*] Status (JS): {res.status_code} | URL: {res.url} | Länge: {len(res.text)} Bytes")
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
                print(f"[*] XOR Key für Entschlüsselung gefunden: {key}")
                decrypted_str = self.voe_decrypt_xor(scrambled, key)
                if decrypted_str.startswith("FAILED") or "direct_access_url" not in decrypted_str:
                    print("[!] Neue XOR-Entschlüsselung fehlgeschlagen oder unvollständig. Versuche Methode 7...")
                    decrypted_str = None
            
            if not decrypted_str:
                decrypted_str = self.voe_decrypt_method7(scrambled)
                
            if decrypted_str.startswith("FAILED"):
                print(f"[!] Entschlüsselung fehlgeschlagen: {decrypted_str}")
                return None
                
            decrypted_json = json.loads(decrypted_str)
            
            # 3. Direct Access MP4 oder master.m3u8 HLS extrahieren
            direct_url = decrypted_json.get("direct_access_url")
            hls_url = decrypted_json.get("source")
            
            # Überprüfen, ob es sich um ein echtes Video handelt (kein Testvideo)
            if direct_url and "test-videos" not in direct_url and "bigbuckbunny" not in direct_url:
                print("[+] Direkte MP4-Download-URL erfolgreich entschlüsselt!")
                return direct_url
            elif hls_url and "test-videos" not in hls_url and "bigbuckbunny" not in hls_url:
                print("[+] HLS (.m3u8) Stream-URL erfolgreich entschlüsselt!")
                return hls_url
        except Exception as e:
            print(f"[!] Fehler bei der Quelltext-Entschlüsselung: {e}")
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
            print(f"[+] Serien-Hoster erkannt: VOE ({selected['label']}) -> {selected['url']}")
            return selected['url']
        except Exception as e:
            print(f"[!] Fehler beim Extrahieren des Serien-Links: {e}")
        return None

    def get_direct_link(self, url, email=None, password=None):
        print(f"[*] Analysiere: {url}")
        try:
            # 0. Falls es eine Serien-Hub-URL ist, den Hoster-Link extrahieren
            is_series_hub = "aniworld.to" in url or "s.to" in url or "serienstream.to" in url or "/serie/" in url or "/stream/" in url
            original_url = url
            if is_series_hub:
                print(f"[*] Serien-Hub-URL erkannt: {url}")
                html, final_url = self.fetch_page(url)
                voe_redirect = self.extract_voe_from_aniworld(html, final_url)
                if voe_redirect:
                    url = voe_redirect
                else:
                    print("[!] Fehler: Kein VOE-Hoster auf der Episodenseite gefunden.")
                    return None

            # 1. Hauptseite laden (inklusive Weiterleitungs-Handling)
            html, final_url = self.fetch_page(url, referer=original_url if is_series_hub else None)
            
            # Falls wir die Captcha-Bridge geladen haben, versuchen wir den automatischen Login
            if "frameBridge" in html or "g-recaptcha" in html or "cf-challenge" in html:
                print("\n[!] Captcha-Blockade oder Login-Abfrage erkannt.")
                from urllib.parse import urlparse
                parsed = urlparse(final_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                
                # Wenn wir übergebene Zugangsdaten oder account.json haben, loggen wir uns ein
                if not self.logged_in:
                    self.load_and_login(email, password, base_url)
                
                # Wenn wir immer noch nicht eingeloggt sind und im interaktiven Modus sind, fragen wir nach den Zugangsdaten
                if not self.logged_in and sys.stdin.isatty():
                    print("[*] Um den Schutz vollautomatisch zu umgehen, erstelle dir ein kostenloses Konto auf SerienStream/s.to.")
                    print("[*] Gib deine Anmeldedaten ein (werden lokal in account.json gespeichert):")
                    email_input = input("E-Mail: ").strip()
                    password_input = input("Passwort: ").strip()
                    if email_input and password_input:
                        import json
                        with open("account.json", "w") as f:
                            json.dump({"email": email_input, "password": password_input}, f)
                        self.load_and_login(email_input, password_input, base_url)
                
                if self.logged_in:
                    print("[*] Lade Seite nach erfolgreichem Login erneut...")
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
                print("[!] Fehler: Video-ID konnte nicht im Quelltext gefunden werden.")
                if len(html) < 2000:
                    print(f"[*] Kompletter Quelltext der Seite:\n{html}")
                else:
                    print(f"[*] Quelltext-Vorschau (erste 400 Zeichen): {repr(html[:400])}")
                title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
                if title_match:
                    print(f"[*] HTML Titel der Seite: '{title_match.group(1).strip()}'")
                return None
            
            print(f"[*] Video-ID erkannt: {video_id}")

            # 4. Session synchronisieren
            print("[*] Synchronisiere Session...")
            try:
                t_res = self.scraper.get("https://voe.sx/api2/session/generate-token", headers={"Referer": url})
                token = t_res.json().get("token")
                if token:
                    self.scraper.get(f"https://voe.sx/session/sync?token={token}&redirect={url}")
            except: pass

            # 5. Alle Mirrors nach einem Download-Button oder Link absuchen
            for domain in self.mirrors:
                dl_url = f"https://{domain}/{video_id}/download"
                print(f"[*] Prüfe Mirror {domain}...")
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
                print(f"[*] Versuche Extraktion via {domain}...")
                return check_url

        except Exception as e:
            print(f"[!] Analysefehler: {e}")
        return None

    def download(self, url, dest_folder, email=None, password=None):
        print(f"\n--- VOE Downloader Start ---")
        direct_link = self.get_direct_link(url, email, password)
        
        # Falls der gefundene Link die Website selbst ist, verwerfen
        if direct_link and (direct_link == url or "/access/" in direct_link):
            direct_link = None

        if not direct_link:
            print("\n[!] AUTOMATISIERUNG DURCH WEBSITE-SCHUTZ GESCHEITERT")
            print("[*] Die Website blockiert automatisierte Anfragen.")
            if sys.stdin.isatty():
                print("[*] So holst du dir den Link in 10 Sekunden selbst:")
                print("    1. Öffne das Video im Browser (Firefox/Chrome).")
                print("    2. Drücke F12 -> Reiter 'Netzwerk' (Network).")
                print("    3. Suche oben im Filter nach 'mp4'.")
                print("    4. Kopiere die URL (Rechtsklick -> Adresse kopieren) und füge sie hier ein.")
                
                manual = input("\nManueller Video-Link (oder Enter zum Abbrechen): ").strip()
                if not manual: return
                direct_link = manual
            else:
                print("[!] Skript läuft im nicht-interaktiven Modus. Manueller Link-Eingabe übersprungen.")
                return

        # Dateiname ermitteln oder generieren
        series_filename = self.parse_series_info(url)

        # Download-Entscheidung: yt-dlp oder Direkt-Download
        if ".m3u8" in direct_link or "voe.sx" in direct_link:
            print(f"[*] Nutze yt-dlp für den Download...")
            if not os.path.exists(dest_folder): os.makedirs(dest_folder)
            
            if series_filename:
                out_template = os.path.join(dest_folder, f"{series_filename}.%(ext)s")
            else:
                out_template = os.path.join(dest_folder, "%(title)s.%(ext)s")
                
            cmd = [sys.executable, "-m", "yt_dlp", direct_link, "--referer", url, "-o", out_template]
            try:
                subprocess.run(cmd)
            except:
                print("[!] Fehler beim Ausführen von yt-dlp.")
        else:
            # Normaler Dateidownload
            if series_filename:
                filename = f"{series_filename}.mp4"
            else:
                name_match = re.search(r"[?&]n=([^&]+)", direct_link)
                filename = requests.utils.unquote(name_match.group(1)) if name_match else os.path.basename(direct_link.split('?')[0])
                filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
                if len(filename) > 100: filename = filename[:90] + ".mp4"
                if not filename or filename == "_": filename = f"video_{int(time.time())}.mp4"
            
            dest_path = os.path.join(dest_folder, filename)
            if not os.path.exists(dest_folder): os.makedirs(dest_folder)
            
            print(f"[*] Downloade Video nach: {dest_path}")
            try:
                r = self.scraper.get(direct_link, stream=True, timeout=60)
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                if total < 500000: # Kleiner als 500KB ist wahrscheinlich kein Video
                    print("[!] Fehler: Der Link führt nicht zu einer Videodatei (Inhalt zu klein).")
                    return
                bar = tqdm(total=total, unit='iB', unit_scale=True, desc=filename[:30])
                with open(dest_path, 'wb') as f:
                    for chunk in r.iter_content(262144):
                        bar.update(len(chunk))
                        f.write(chunk)
                bar.close()
                print(f"[+] Download erfolgreich!")
            except Exception as e:
                print(f"[!] Fehler beim Download: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="VOE & SerienStream Video Downloader CLI")
    parser.add_argument("url", nargs="?", help="Die URL des Videos oder der Serien-Episode")
    parser.add_argument("output", nargs="?", help="Zielordner, in den das Video gespeichert werden soll")
    parser.add_argument("--email", "-e", help="E-Mail für s.to/aniworld.to Login (zur Umgehung von Captchas)")
    parser.add_argument("--password", "-p", help="Passwort für s.to/aniworld.to Login")
    parser.add_argument("--lang", "-l", default="german", choices=["german", "english", "gersub", "engsub"], help="Bevorzugte Sprache")
    args = parser.parse_args()
    
    print("\n--- VOE Video Downloader CLI ---")
    
    u = args.url
    if not u:
        if sys.stdin.isatty():
            u = input("Video URL: ").strip()
        else:
            print("[!] Fehler: Keine URL angegeben und keine interaktive Eingabe möglich.")
            sys.exit(1)
            
    if not u:
        sys.exit(0)
        
    o = args.output
    if not o:
        if sys.stdin.isatty():
            o = input("Zielordner (Standard '.'): ").strip() or "."
        else:
            o = "."
            
    VoeDownloader(preferred_lang=args.lang).download(u, o, email=args.email, password=args.password)
