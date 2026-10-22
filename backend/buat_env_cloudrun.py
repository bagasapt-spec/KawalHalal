"""Buat ../.cloudrun-env.yaml dari backend/.env untuk `gcloud run deploy --env-vars-file`.

Hanya variabel yang dipakai di server. GEMINI_API_KEY dan GOOGLE_APPLICATION_CREDENTIALS sengaja dibuang:
di Cloud Run, autentikasi Vertex AI lewat service account layanan. File hasilnya berisi rahasia, jangan di-commit.
"""
import json
from pathlib import Path

from dotenv import dotenv_values

PAKAI = [
    "SUPABASE_URL", "SUPABASE_SECRET_KEY", "DEV_INGEST_KEY", "TELEGRAM_BOT_TOKEN",
    "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM",
    "GOOGLE_GENAI_USE_ENTERPRISE", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GEMINI_MODEL",
]
env = dotenv_values(Path(__file__).parent / ".env")
baris, hilang = [], []
for k in PAKAI:
    v = (env.get(k) or "").strip()
    if v:
        baris.append(f"{k}: {json.dumps(v)}")
    else:
        hilang.append(k)
baris.append('SIHALAL_SEED: "kosong"')
tujuan = Path(__file__).parent.parent / ".cloudrun-env.yaml"
tujuan.write_text("\n".join(baris) + "\n", encoding="utf-8")
print(f"Ditulis: {tujuan}")
print("Terisi :", ", ".join(k for k in PAKAI if k not in hilang))
print("Kosong (dilewati):", ", ".join(hilang) or "-")
