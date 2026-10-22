"""Jembatan WhatsApp -> agen: baca pesan masuk terakhir dari Supabase, jalankan agen, kirim dan simpan balasan."""
import asyncio
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


async def _susun_balasan(session_id: str, warung_id: str) -> Optional[tuple[str, str, str]]:
    """Jalankan agen untuk pesan masuk terakhir. Mengembalikan (balasan, id pesan masuk, nomor) atau None."""
    import db  # impor lambat supaya modul ini bisa dites tanpa Supabase
    from kawal_agent.agent import jalankan

    sb = db.supabase
    pesan = _pesan_masuk_terakhir(sb, session_id)
    if not pesan:
        return None
    msg_id = pesan.get("twilio_sid") or pesan.get("id") or ""
    if msg_id in _sudah_diproses:
        logger.info("Pesan %s sudah diproses, dilewati.", msg_id)
        return None
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
    return balasan, msg_id, nomor


async def proses(session_id: str, warung_id: str, **_) -> None:
    """Mode dorong: kirim balasan lewat REST API provider setelah agen selesai."""
    hasil = await _susun_balasan(session_id, warung_id)
    if hasil:
        balasan, msg_id, nomor = hasil
        await kirim_balasan(msg_id, nomor, balasan)


# ---- Mode TwiML sinkron: balasan dikirim sebagai response webhook ----
# Sandbox akun trial menolak balasan bebas lewat REST (error 21654), tetapi menerima balasan di response webhook.
# Twilio menunggu sekitar 15 detik; kalau agen belum selesai, hasilnya ditahan dan diambil pada pesan berikutnya.
_tertunda: dict[str, "asyncio.Future"] = {}
KATA_AMBIL = {"lanjut", "lanjutkan", "?", "sudah", "udah", "hasil", "cek", "ok", "oke"}
PESAN_TUNGGU = 'Sedang saya proses, mohon tunggu sekitar 15 detik lalu balas "lanjut".'


def _sepele(teks: str) -> bool:
    return (teks or "").strip().lower() in KATA_AMBIL


async def balas_sinkron(session_id: str, warung_id: str, nomor: str, teks: str, batas: float = 10.0) -> list[str]:
    """Daftar balasan untuk dimasukkan ke TwiML. Daftar kosong berarti tidak ada yang dibalas."""
    from kawal_agent.agent import kirim_ke_loop_agen

    awalan = ""
    tunda = _tertunda.get(nomor)
    if tunda is not None:
        if not tunda.done():
            return ['Pesan sebelumnya masih diproses. Tunggu sebentar lalu balas "lanjut".']
        _tertunda.pop(nomor, None)
        try:
            hasil_lama = await tunda
            awalan = hasil_lama[0] if hasil_lama else ""
        except Exception as e:
            logger.error("Hasil tertunda gagal: %s", e)
        if _sepele(teks):
            return [awalan] if awalan else ["Tidak ada balasan yang menunggu. Silakan lanjutkan pesan Anda."]

    fut = asyncio.wrap_future(kirim_ke_loop_agen(_susun_balasan(session_id, warung_id)))
    try:
        hasil = await asyncio.wait_for(asyncio.shield(fut), batas)
    except asyncio.TimeoutError:
        _tertunda[nomor] = fut
        return [x for x in (awalan, PESAN_TUNGGU) if x]
    except Exception as e:
        logger.error("Agen gagal di webhook sinkron: %s", e, exc_info=True)
        return [x for x in (awalan, "Maaf, ada gangguan. Coba kirim ulang pesan Anda.") if x]
    balasan = hasil[0] if hasil else ""
    if not hasil:
        logger.warning("Agen tidak menghasilkan balasan (pesan tidak ditemukan atau sudah diproses) untuk %s.", nomor)
    return [x for x in (awalan, balasan) if x]
