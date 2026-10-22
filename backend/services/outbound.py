"""Pengiriman balasan WhatsApp: Twilio (sandbox) atau Meta Cloud API, dipilih dari awalan id pesan masuk."""
import logging
import os
import re

import httpx

logger = logging.getLogger("kawalhalal.outbound")

BATAS_PESAN = 1500  # Twilio menolak body di atas 1600 karakter


def pecah_pesan(teks: str, batas: int = BATAS_PESAN) -> list[str]:
    """Pecah di batas paragraf/kalimat supaya tiap bagian muat dalam satu pesan WhatsApp."""
    teks = (teks or "").strip()
    if len(teks) <= batas:
        return [teks] if teks else []
    bagian, sisa = [], teks
    while len(sisa) > batas:
        potong = max(sisa.rfind("\n\n", 0, batas), sisa.rfind("\n", 0, batas), sisa.rfind(". ", 0, batas))
        if potong < batas // 3:
            potong = batas
        bagian.append(sisa[:potong].strip())
        sisa = sisa[potong:].strip()
    if sisa:
        bagian.append(sisa)
    return bagian


def saluran_dari_id(msg_id: str) -> str:
    """twilio untuk SM/MM..., meta untuk wamid..., dev untuk simulasi (tidak dikirim ke mana pun)."""
    if (msg_id or "").startswith("dev-"):
        return "dev"
    if (msg_id or "").startswith("wamid"):
        return "meta"
    return "twilio"


async def _kirim_twilio(ke: str, teks: str) -> bool:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    dari = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886").strip()
    if not sid or not token:
        logger.warning("Twilio tidak dikonfigurasi, balasan tidak dikirim.")
        return False
    tujuan = "whatsapp:+" + re.sub(r"\D", "", ke)
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"From": dari, "To": tujuan, "Body": teks},
            auth=(sid, token),
        )
    if r.status_code >= 300:
        logger.error("Twilio gagal kirim (%s): %s", r.status_code, r.text[:300])
        return False
    return True


async def _kirim_meta(ke: str, teks: str) -> bool:
    from routers.meta_webhook import send_text  # impor lambat: modul itu memuat db

    return await send_text(ke, teks) is not None


async def kirim_balasan(msg_id_masuk: str, ke: str, teks: str) -> bool:
    saluran = saluran_dari_id(msg_id_masuk)
    if saluran == "dev":
        return False
    kirim = _kirim_meta if saluran == "meta" else _kirim_twilio
    sukses = True
    for bagian in pecah_pesan(teks):
        sukses = await kirim(ke, bagian) and sukses
    return sukses
