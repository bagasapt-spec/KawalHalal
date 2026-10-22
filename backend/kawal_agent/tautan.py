"""Tautan unduh berkas bertanda tangan (HMAC) dan pembentuk URL peninjauan web demo SIHALAL."""
import hashlib
import hmac
import os
import secrets

_RAHASIA = (os.getenv("BERKAS_SECRET") or os.getenv("DEV_INGEST_KEY") or secrets.token_hex(16)).encode()
DEFAULT_SIHALAL_FRONTEND_URL = "https://kawalhalal-demo-96225654727.asia-southeast2.run.app"


def tanda(path: str) -> str:
    return hmac.new(_RAHASIA, path.encode(), hashlib.sha256).hexdigest()[:24]


def valid(path: str, t: str) -> bool:
    return bool(t) and hmac.compare_digest(tanda(path), t)


def url_frontend() -> str:
    """Basis URL web demo SIHALAL (dapat dikonfigurasi via env SIHALAL_FRONTEND_URL)."""
    return (os.getenv("SIHALAL_FRONTEND_URL") or DEFAULT_SIHALAL_FRONTEND_URL).strip().rstrip("/")


def url_pengajuan(pengajuan_id: str) -> str:
    """Tautan langsung ke halaman detail pengajuan di web SIHALAL."""
    pid = (pengajuan_id or "").strip()
    base = url_frontend()
    if not pid:
        return f"{base}/pengajuan"
    return f"{base}/pengajuan/{pid}"
