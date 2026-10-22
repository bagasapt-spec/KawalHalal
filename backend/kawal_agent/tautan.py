"""Tautan unduh berkas bertanda tangan (HMAC): berkas xlsx yang dikirim lewat WhatsApp bisa dibuka tanpa header,
tetapi path-nya tidak bisa ditebak dari nomor telepon."""
import hashlib
import hmac
import os
import secrets

_RAHASIA = (os.getenv("BERKAS_SECRET") or os.getenv("DEV_INGEST_KEY") or secrets.token_hex(16)).encode()


def tanda(path: str) -> str:
    return hmac.new(_RAHASIA, path.encode(), hashlib.sha256).hexdigest()[:24]


def valid(path: str, t: str) -> bool:
    return bool(t) and hmac.compare_digest(tanda(path), t)
