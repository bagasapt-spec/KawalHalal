"""Tes bot Telegram: parsing update dan alur pesan -> agen -> balasan (Telegram palsu, LLM terskrip)."""
import asyncio
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from kawal_agent import agent as A, tools as T  # noqa: E402
from services import telegram_bot as TB  # noqa: E402
from test_agen_runner import LLMTerskrip, panggil, teks  # noqa: E402


def test_ekstrak_update():
    assert TB.ekstrak_update({"update_id": 1}) is None
    t = TB.ekstrak_update({"message": {"chat": {"id": 7}, "message_id": 3, "text": " halo "}})
    assert t["chat_id"] == 7 and t["teks"] == "halo" and t["file"] is None and not t["tidak_didukung"]
    f = TB.ekstrak_update({"message": {"chat": {"id": 7}, "message_id": 4, "caption": "label bumbu",
                                       "photo": [{"file_id": "kecil"}, {"file_id": "besar"}]}})
    assert f["file"] == {"file_id": "besar", "nama": "foto-4.jpg", "mime": "image/jpeg"} and f["teks"] == "label bumbu"
    d = TB.ekstrak_update({"message": {"chat": {"id": 7}, "message_id": 5,
                                       "document": {"file_id": "x", "file_name": "bahan.xlsx", "mime_type": "application/vnd.ms-excel"}}})
    assert d["file"]["nama"] == "bahan.xlsx"
    assert TB.ekstrak_update({"message": {"chat": {"id": 7}, "message_id": 6, "voice": {"file_id": "v"}}})["tidak_didukung"]


class Palsu:
    """Pengganti klien httpx dan API Telegram."""

    def __init__(self, unduhan=b""):
        self.terkirim, self.unduhan = [], unduhan

    async def post(self, url, json=None, data=None, files=None, timeout=None):
        class R:
            status_code = 200
            text = ""
        self.terkirim.append((url.rsplit("/", 1)[-1], json or data))
        return R()

    async def get(self, url, timeout=None):
        class R:
            status_code = 200
        R.content = self.unduhan
        return R()


@pytest.fixture(autouse=True)
def lingkungan(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("GEMINI_API_KEY", "palsu")
    monkeypatch.setattr(T, "GENERATED_DIR", tmp_path)


def pasang_api(monkeypatch, file_info=None):
    async def api(client, metode, **params):
        client.terkirim.append((metode, params))
        if metode == "getFile":
            return {"ok": True, "result": {"file_path": "photos/a.jpg", "file_size": 10}}
        return {"ok": True, "result": {}}

    monkeypatch.setattr(TB, "_api", api)


def test_pesan_teks_dibalas(monkeypatch):
    A.ganti_model(LLMTerskrip(skrip=[lambda r: panggil("lihat_progres"), lambda r: teks("Halo! **Pilih** kategori.")], log=[]))
    pasang_api(monkeypatch)
    k = Palsu()
    asyncio.run(TB.proses_update(k, {"message": {"chat": {"id": 42}, "message_id": 1, "text": "hi"}}))
    kirim = [p for m, p in k.terkirim if m == "sendMessage"]
    assert kirim == [{"chat_id": 42, "text": "Halo! Pilih kategori."}]  # penanda ** dibuang


def test_foto_diunduh_dan_sampai_ke_agen(monkeypatch):
    m = LLMTerskrip(skrip=[lambda r: teks("Foto diterima.")], log=[])
    A.ganti_model(m)
    pasang_api(monkeypatch)
    k = Palsu(unduhan=b"\xff\xd8\xff\xe0" + b"\x00" * 10)
    asyncio.run(TB.proses_update(k, {"message": {"chat": {"id": 42}, "message_id": 2, "caption": "label",
                                                   "photo": [{"file_id": "f1"}]}}))
    assert any(p.inline_data and p.inline_data.mime_type == "image/jpeg" for c in m.log[0].contents for p in c.parts or [])
    assert any(mt == "sendMessage" for mt, _ in k.terkirim)


def test_xlsx_dikirim_sebagai_dokumen(monkeypatch):
    A.ganti_model(LLMTerskrip(skrip=[lambda r: panggil("pilih_kategori", kategori="makanan"),
                                     lambda r: panggil("buat_berkas_xlsx"), lambda r: teks("Berkas sudah dibuat.")], log=[]))
    pasang_api(monkeypatch)
    TB._terkirim.clear()
    k = Palsu()
    asyncio.run(TB.proses_update(k, {"message": {"chat": {"id": 43}, "message_id": 1, "text": "buatkan berkasnya"}}))
    assert any(mt == "sendDocument" for mt, _ in k.terkirim)


def test_suara_ditolak_sopan(monkeypatch):
    pasang_api(monkeypatch)
    k = Palsu()
    asyncio.run(TB.proses_update(k, {"message": {"chat": {"id": 9}, "message_id": 1, "voice": {"file_id": "v"}}}))
    assert [p["text"] for m, p in k.terkirim if m == "sendMessage"] == [TB.PESAN_TIDAK_DIDUKUNG]
