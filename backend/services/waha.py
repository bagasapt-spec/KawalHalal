"""WhatsApp lewat WAHA (WhatsApp HTTP API, https://waha.devlike.pro) -> agen KawalHalal.

WAHA berjalan sebagai container Docker di mesin yang sama dan mengirim event pesan ke POST /api/waha/webhook.
Balasan dikirim balik lewat REST WAHA. Aktif bila WAHA_URL diisi. Tanpa Twilio dan tanpa akun bisnis Meta,
tetapi memakai sesi WhatsApp Web biasa: cocok untuk demo, bukan untuk produksi.
"""
import asyncio
import base64
import logging
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from services.outbound import pecah_pesan

logger = logging.getLogger("kawalhalal.waha")

router = APIRouter(prefix="/api/waha", tags=["WhatsApp (WAHA)"])
BATAS_PESAN = 3500
BATAS_UNDUH = 20 * 1024 * 1024
PESAN_TIDAK_DIDUKUNG = "Maaf, saya baru bisa membaca teks, foto, dan dokumen (pdf, docx, xlsx)."
_terkirim: dict[str, float] = {}


def url_waha() -> str:
    return os.environ.get("WAHA_URL", "").strip().rstrip("/")


def aktif() -> bool:
    return bool(url_waha())


def _sesi() -> str:
    return os.environ.get("WAHA_SESSION", "default").strip() or "default"


def _header() -> dict:
    kunci = os.environ.get("WAHA_API_KEY", "").strip()
    return {"X-Api-Key": kunci} if kunci else {}


def ekstrak_event(ev: dict) -> Optional[dict]:
    """Ambil chat id, teks, dan berkas dari event WAHA. None bila bukan pesan masuk dari chat pribadi."""
    if ev.get("event") not in ("message", "message.any"):
        return None
    p = ev.get("payload") or {}
    chat_id = p.get("from") or ""
    if p.get("fromMe") or not chat_id or chat_id.endswith("@g.us") or chat_id == "status@broadcast":
        return None
    media = p.get("media") or {}
    hasil = {"chat_id": chat_id, "uid": re.sub(r"\D", "", chat_id), "teks": (p.get("body") or "").strip(),
             "file": None, "suara": None, "tidak_didukung": False, "id": p.get("id")}
    if p.get("hasMedia") and media.get("url"):
        mime = (media.get("mimetype") or "application/octet-stream").split(";")[0]
        info = {"url": media["url"], "mime": mime}
        if mime.startswith("audio/"):
            hasil["suara"] = info
        else:
            ekstensi = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}.get(mime, "")
            hasil["file"] = {**info, "nama": media.get("filename") or f"berkas-{str(p.get('id'))[-6:]}{ekstensi}"}
    elif p.get("hasMedia") or not hasil["teks"]:
        hasil["tidak_didukung"] = True
    return hasil


def _rapikan(teks: str) -> str:
    """WhatsApp memakai satu bintang untuk tebal."""
    return re.sub(r"\*\*(.+?)\*\*", r"*\1*", teks or "")


async def _unduh(client: httpx.AsyncClient, url: str) -> Optional[bytes]:
    # WAHA bisa menulis URL media dengan host yang tidak terjangkau dari sini: pakai path-nya saja.
    alamat = f"{url_waha()}{urlparse(url).path}"
    r = await client.get(alamat, headers=_header(), timeout=40.0)
    return r.content if r.status_code == 200 and len(r.content) <= BATAS_UNDUH else None


async def kirim_teks(client: httpx.AsyncClient, chat_id: str, teks: str) -> None:
    for bagian in pecah_pesan(_rapikan(teks), BATAS_PESAN):
        r = await client.post(f"{url_waha()}/api/sendText", headers=_header(), timeout=40.0,
                              json={"session": _sesi(), "chatId": chat_id, "text": bagian})
        if r.status_code >= 300:
            logger.error("sendText gagal: %s %s", r.status_code, r.text[:200])


async def kirim_berkas_baru(client: httpx.AsyncClient, chat_id: str, uid: str) -> None:
    """Kirim xlsx buatan agen sebagai dokumen."""
    from kawal_agent.agent import lihat_state
    from kawal_agent.tools import folder_pengguna

    for b in (await lihat_state(uid)).get("berkas_dibuat", []):
        path: Path = folder_pengguna(uid) / b["nama"]
        if not path.is_file():
            continue
        kunci, mtime = f"{uid}/{b['nama']}", path.stat().st_mtime
        if _terkirim.get(kunci) == mtime:
            continue
        _terkirim[kunci] = mtime
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        r = await client.post(f"{url_waha()}/api/sendFile", headers=_header(), timeout=60.0, json={
            "session": _sesi(), "chatId": chat_id,
            "file": {"mimetype": mime, "filename": b["nama"], "data": base64.b64encode(path.read_bytes()).decode()}})
        if r.status_code >= 300:
            logger.error("sendFile gagal: %s %s", r.status_code, r.text[:200])


async def proses_event(client: httpx.AsyncClient, ev: dict) -> None:
    from kawal_agent.agent import jalankan

    e = ekstrak_event(ev)
    if not e:
        return
    chat_id, uid = e["chat_id"], e["uid"]
    if e["tidak_didukung"]:
        await kirim_teks(client, chat_id, PESAN_TIDAK_DIDUKUNG)
        return
    lampiran, audio, mime_audio = [], None, "audio/ogg"
    if e["file"]:
        data = await _unduh(client, e["file"]["url"])
        if not data:
            await kirim_teks(client, chat_id, "Maaf, berkas itu tidak bisa saya unduh (maksimal 20 MB). Coba kirim ulang.")
            return
        lampiran.append({"nama": e["file"]["nama"], "mime": e["file"]["mime"], "data": data})
    if e["suara"]:
        audio, mime_audio = await _unduh(client, e["suara"]["url"]), e["suara"]["mime"]

    async def mengetik():
        while True:
            await client.post(f"{url_waha()}/api/startTyping", headers=_header(), json={"session": _sesi(), "chatId": chat_id})
            await asyncio.sleep(4)

    indikator = asyncio.create_task(mengetik())
    try:
        hasil = await jalankan(uid, e["teks"], lampiran, audio_bytes=audio, audio_mime=mime_audio)
    finally:
        indikator.cancel()
        await client.post(f"{url_waha()}/api/stopTyping", headers=_header(), json={"session": _sesi(), "chatId": chat_id})
    logger.info("WAHA %s -> alat: %s", uid, hasil.get("alat"))
    await kirim_teks(client, chat_id, hasil["balasan"])
    await kirim_berkas_baru(client, chat_id, uid)


async def _aman(ev: dict) -> None:
    try:
        async with httpx.AsyncClient() as client:
            await proses_event(client, ev)
    except Exception as err:
        logger.error("Gagal memproses event WAHA: %s", err, exc_info=True)


@router.post("/webhook")
async def webhook(request: Request, x_api_key: Optional[str] = Header(None, alias="X-Api-Key")):
    """Terima event WAHA dan jawab cepat; agen berjalan di latar belakang pada loop agen."""
    if not aktif():
        raise HTTPException(404, "WAHA tidak aktif.")
    rahasia = os.environ.get("WAHA_WEBHOOK_KEY", "").strip()
    if rahasia and x_api_key != rahasia:
        raise HTTPException(401, "Kunci webhook salah.")
    ev = await request.json()
    if ekstrak_event(ev):
        from kawal_agent.agent import kirim_ke_loop_agen

        kirim_ke_loop_agen(_aman(ev))
    return {"ok": True}
