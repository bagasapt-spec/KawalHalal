"""Tes WhatsApp lewat WAHA: parsing event dan alur pesan -> agen -> balasan (WAHA palsu, LLM terskrip)."""
import asyncio
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from kawal_agent import agent as A  # noqa: E402
from services import waha as W  # noqa: E402
from test_agen_runner import LLMTerskrip, teks  # noqa: E402


def _ev(**payload):
    return {"event": "message", "session": "default", "payload": {"from": "6281234@c.us", "fromMe": False, "id": "false_x_ABC123", **payload}}


def test_ekstrak_event_teks_dan_penyaring():
    e = W.ekstrak_event(_ev(body=" halo ", hasMedia=False))
    assert (e["chat_id"], e["uid"], e["teks"], e["file"]) == ("6281234@c.us", "6281234", "halo", None)
    assert W.ekstrak_event({"event": "session.status"}) is None
    assert W.ekstrak_event(_ev(body="x", fromMe=True)) is None
    assert W.ekstrak_event(_ev(body="x", **{"from": "123-456@g.us"})) is None


def test_ekstrak_event_foto_dokumen_dan_suara():
    f = W.ekstrak_event(_ev(body="label kecap", hasMedia=True, media={"url": "http://localhost:3000/api/files/default/a.jpg", "mimetype": "image/jpeg"}))
    assert f["file"]["mime"] == "image/jpeg" and f["file"]["nama"].endswith(".jpg") and f["teks"] == "label kecap"
    d = W.ekstrak_event(_ev(body="", hasMedia=True, media={"url": "http://x/api/files/d.xlsx", "mimetype": "application/vnd.ms-excel", "filename": "bahan.xlsx"}))
    assert d["file"]["nama"] == "bahan.xlsx"
    s = W.ekstrak_event(_ev(body="", hasMedia=True, media={"url": "http://x/api/files/v.oga", "mimetype": "audio/ogg; codecs=opus"}))
    assert s["suara"]["mime"] == "audio/ogg" and s["file"] is None
    assert W.ekstrak_event(_ev(body="", hasMedia=False))["tidak_didukung"]


def test_rapikan_tebal_whatsapp():
    assert W._rapikan("**Kecap** dan **Garam**") == "*Kecap* dan *Garam*"


class Palsu:
    def __init__(self):
        self.terkirim = []

    async def post(self, url, json=None, headers=None, timeout=None):
        class R:
            status_code = 200
            text = ""
        self.terkirim.append((url.rsplit("/", 1)[-1], json))
        return R()


def test_proses_event_membalas_lewat_sendtext(monkeypatch):
    monkeypatch.setenv("WAHA_URL", "http://waha:3000")
    A.ganti_model(LLMTerskrip(skrip=[lambda req: teks("Halo, saya Kala.")], log=[]))
    klien = Palsu()
    asyncio.run(A.di_loop_agen(W.proses_event(klien, _ev(body="Halo", hasMedia=False))))
    kirim = [x for x in klien.terkirim if x[0] == "sendText"]
    assert kirim and kirim[0][1]["chatId"] == "6281234@c.us" and "Kala" in kirim[0][1]["text"]


def test_webhook_menolak_bila_nonaktif(monkeypatch):
    from fastapi.testclient import TestClient
    import main

    monkeypatch.delenv("WAHA_URL", raising=False)
    assert TestClient(main.app).post("/api/waha/webhook", json={}).status_code == 404
