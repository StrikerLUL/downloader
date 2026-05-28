import requests
import re

url = "https://vickisaveworker.com/js/loader.bc4a6543429.js"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://rebeccasciencestreet.com/"
}

r = requests.get(url, headers=headers)
with open("voe_loader.js", "w", encoding="utf-8") as f:
    f.write(r.text)
