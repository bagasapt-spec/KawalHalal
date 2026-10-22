"""Buat sekali Content Template twilio/text berisi {{1}} di akun Twilio dari .env, lalu cetak SID-nya (HX...).

Dipakai karena sandbox trial menolak kirim pesan bebas (Body) lewat REST API dengan error 21654.
Jalankan:  python buat_template_twilio.py
Lalu isi  TWILIO_CONTENT_SID=HX...  di .env dan restart server.
"""
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

sid, token = os.environ.get("TWILIO_ACCOUNT_SID", "").strip(), os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
if not sid or not token:
    sys.exit("TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN belum diisi di .env")

r = httpx.post(
    "https://content.twilio.com/v1/Content",
    auth=(sid, token),
    json={
        "friendly_name": "kawalhalal_balasan",
        "language": "id",
        "variables": {"1": "halo"},
        "types": {"twilio/text": {"body": "{{1}}"}},
    },
    timeout=20,
)
print(r.status_code)
print(r.text[:500])
if r.status_code < 300:
    print("\nIsi di .env:  TWILIO_CONTENT_SID=" + r.json()["sid"])
