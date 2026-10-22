"""Jembatan WhatsApp -> agen: baca pesan masuk terakhir dari Supabase, jalankan agen, kirim dan simpan balasan."""
import logging
import re
import uuid
from typing import Optional

import httpx

from services.outbound import kirim_balasan

logger = logging.getLogger("kawalhalal.wa_agent")

_sudah_diproses: set[str] = set()  # webhook yang dikirim ulang provider tidak boleh dibalas dua kali
MIME_DIDUKUNG = {
    "image/jpeg", "image/png", "image/webp", "application/pdf",
    "audio/ogg", "audio/opus", "audio/mpeg", "audio/mp3", "audio/mp4",
    "audio/aac", "audio/amr", "audio/wav", "audio/x-wav", "audio/webm", "audio/flac",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _pesan_masuk_terakhir(sb, session_id: str) -> Optional[dict]:
    res = (
        sb.table("messages").select("*").eq("session_id", session_id).eq("direction", "in")
        .order("created_at", desc=True).limit(1).execute()
    )
    return res.data[0] if res.data else None


async def _unduh(url: str) -> Optional[bytes]:
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            r = await client.get(url)
        return r.content if r.status_code == 200 else None
    except Exception as e:
        logger.error("Gagal mengunduh lampiran: %s", e)
        return None


async def proses(session_id: str, warung_id: str, **_) -> None:
    import db  # impor lambat supaya modul ini bisa dites tanpa Supabase
    from kawal_agent.agent import jalankan

    sb = db.supabase
    pesan = _pesan_masuk_terakhir(sb, session_id)
    if not pesan:
        return
    msg_id = pesan.get("twilio_sid") or pesan.get("id") or ""
    if msg_id in _sudah_diproses:
        logger.info("Pesan %s sudah diproses, dilewati.", msg_id)
        return
    _sudah_diproses.add(msg_id)

    warung = sb.table("warung").select("*").eq("id", warung_id).limit(1).execute().data[0]
    nomor = re.sub(r"\D", "", warung["wa_number"])

    lampiran = []
    mime = (pesan.get("media_type") or "").split(";")[0].lower()
    if pesan.get("media_url") and mime in MIME_DIDUKUNG:
        data = await _unduh(pesan["media_url"])
        if data:
            nama = pesan["media_url"].rsplit("/", 1)[-1].split("?")[0] or f"{msg_id}.bin"
            lampiran.append({"nama": nama, "mime": mime, "data": data})
    elif pesan.get("media_url"):
        logger.info("Tipe lampiran %s belum didukung.", mime)

    hasil = await jalankan(nomor, pesan.get("body") or "", lampiran)
    balasan = hasil["balasan"]
    logger.info("Balasan agen untuk %s (alat: %s)", nomor, hasil.get("alat"))

    try:
        sb.table("messages").upsert(
            {"session_id": session_id, "direction": "out", "body": balasan, "media_url": None, "media_type": None,
             "twilio_sid": f"out-{uuid.uuid4()}"},
            on_conflict="twilio_sid", ignore_duplicates=True,
        ).execute()
    except Exception as e:
        logger.warning("Balasan tidak tersimpan ke DB: %s", e)
    await kirim_balasan(msg_id, nomor, balasan)
