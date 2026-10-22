"""Bot Telegram -> agen KawalHalal (long polling, tanpa webhook dan tanpa Supabase).

Berjalan di dalam proses server yang sama (loop agen), supaya data yang ditulis agen ke mock SIHALAL
(di memori) terlihat oleh frontend. Aktif bila TELEGRAM_BOT_TOKEN diisi.
"""
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import httpx

from services.outbound import pecah_pesan

logger = logging.getLogger("kawalhalal.telegram")

API = "https://api.telegram.org"
BATAS_PESAN = 3500  # batas Telegram 4096
BATAS_UNDUH = 20 * 1024 * 1024  # batas getFile untuk bot
PESAN_TIDAK_DIDUKUNG = "Maaf, saya baru bisa membaca teks, foto, dan dokumen (pdf, docx, xlsx)."
_terkirim: dict[str, float] = {}  # berkas hasil agen yang sudah dikirim (kunci -> mtime)


def token() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def aktif() -> bool:
    return bool(token())


def ekstrak_update(upd: dict) -> Optional[dict]:
    """Ambil chat id, teks, dan (bila ada) berkas dari update Telegram. None bila bukan pesan."""
    msg = upd.get("message")
    if not msg or "chat" not in msg:
        return None
    hasil = {"chat_id": msg["chat"]["id"], "teks": (msg.get("text") or msg.get("caption") or "").strip(),
             "file": None, "tidak_didukung": False, "message_id": msg.get("message_id")}
    if msg.get("photo"):
        terbesar = msg["photo"][-1]
        hasil["file"] = {"file_id": terbesar["file_id"], "nama": f"foto-{msg.get('message_id')}.jpg", "mime": "image/jpeg"}
    elif msg.get("document"):
        d = msg["document"]
        hasil["file"] = {"file_id": d["file_id"], "nama": d.get("file_name") or f"berkas-{msg.get('message_id')}",
                         "mime": d.get("mime_type") or "application/octet-stream"}
    elif not hasil["teks"]:
        hasil["tidak_didukung"] = True  # suara, video, stiker, dst.
    return hasil


async def _api(client: httpx.AsyncClient, metode: str, **params) -> dict:
    r = await client.post(f"{API}/bot{token()}/{metode}", json=params, timeout=40.0)
    return r.json()


async def _unduh(client: httpx.AsyncClient, file_id: str) -> Optional[bytes]:
    info = await _api(client, "getFile", file_id=file_id)
    if not info.get("ok"):
        logger.warning("getFile gagal: %s", info)
        return None
    f = info["result"]
    if f.get("file_size", 0) > BATAS_UNDUH:
        return None
    r = await client.get(f"{API}/file/bot{token()}/{f['file_path']}", timeout=40.0)
    return r.content if r.status_code == 200 else None


def _rapikan(teks: str) -> str:
    """Telegram polos tidak merender markdown: buang penanda tebal supaya tidak berantakan."""
    return (teks or "").replace("**", "")


async def kirim_teks(client: httpx.AsyncClient, chat_id: int, teks: str) -> None:
    for bagian in pecah_pesan(_rapikan(teks), BATAS_PESAN):
        r = await _api(client, "sendMessage", chat_id=chat_id, text=bagian)
        if not r.get("ok"):
            logger.error("sendMessage gagal: %s", r)


async def kirim_berkas_baru(client: httpx.AsyncClient, chat_id: int, uid: str) -> None:
    """Kirim xlsx buatan agen langsung sebagai dokumen (lebih baik daripada tautan)."""
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
        r = await client.post(f"{API}/bot{token()}/sendDocument", data={"chat_id": str(chat_id)},
                              files={"document": (b["nama"], path.read_bytes())}, timeout=60.0)
        if r.status_code >= 300:
            logger.error("sendDocument gagal: %s", r.text[:200])


async def proses_update(client: httpx.AsyncClient, upd: dict) -> None:
    from kawal_agent.agent import jalankan

    e = ekstrak_update(upd)
    if not e:
        return
    chat_id, uid = e["chat_id"], str(e["chat_id"])
    if e["tidak_didukung"]:
        await kirim_teks(client, chat_id, PESAN_TIDAK_DIDUKUNG)
        return
    lampiran = []
    if e["file"]:
        data = await _unduh(client, e["file"]["file_id"])
        if data:
            lampiran.append({"nama": e["file"]["nama"], "mime": e["file"]["mime"], "data": data})
        else:
            await kirim_teks(client, chat_id, "Maaf, berkas itu tidak bisa saya unduh (maksimal 20 MB). Coba kirim ulang.")
            return

    async def mengetik():
        while True:
            await _api(client, "sendChatAction", chat_id=chat_id, action="typing")
            await asyncio.sleep(4)

    indikator = asyncio.create_task(mengetik())
    try:
        hasil = await jalankan(uid, e["teks"], lampiran)
    finally:
        indikator.cancel()
    logger.info("Telegram %s -> alat: %s", uid, hasil.get("alat"))
    await kirim_teks(client, chat_id, hasil["balasan"])
    await kirim_berkas_baru(client, chat_id, uid)


async def _aman(coro) -> None:
    try:
        await coro
    except Exception as err:
        logger.error("Gagal memproses update Telegram: %s", err, exc_info=True)


async def polling() -> None:
    """Loop long polling. Dijalankan di event loop agen."""
    if not aktif():
        return
    async with httpx.AsyncClient() as client:
        saya = await _api(client, "getMe")
        if not saya.get("ok"):
            logger.error("Token Telegram tidak valid: %s", saya)
            return
        logger.info("Bot Telegram aktif: @%s", saya["result"].get("username"))
        await _api(client, "deleteWebhook")  # polling tidak boleh bersamaan dengan webhook
        offset = None
        while True:
            try:
                res = await _api(client, "getUpdates", timeout=25, offset=offset, allowed_updates=["message"])
            except Exception as err:
                logger.warning("getUpdates gagal: %s", err)
                await asyncio.sleep(3)
                continue
            if not res.get("ok"):
                logger.error("getUpdates ditolak: %s", res)  # mis. 409: ada instance lain yang polling
                await asyncio.sleep(5)
                continue
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                asyncio.create_task(_aman(proses_update(client, upd)))
