"""Tes jembatan WhatsApp -> agen dengan Supabase palsu dan LLM terskrip."""
import asyncio
import os
import sys
import types

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from kawal_agent import agent as A, tools as T  # noqa: E402
from services import outbound, wa_agent  # noqa: E402
from test_agen_runner import LLMTerskrip, panggil, teks  # noqa: E402


class Tabel:
    def __init__(self, baris):
        self.baris, self.disimpan = baris, []

    def select(self, *_): return self
    def eq(self, *_): return self
    def order(self, *_, **__): return self
    def limit(self, *_): return self
    def upsert(self, data, **_):
        self.disimpan.append(data)
        return self
    def execute(self): return types.SimpleNamespace(data=self.baris)


class SupabasePalsu:
    def __init__(self, pesan):
        self.t = {"messages": Tabel([pesan]), "warung": Tabel([{"id": "w1", "wa_number": "+6281234567890"}])}

    def table(self, nama): return self.t[nama]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")
    monkeypatch.setattr(T, "GENERATED_DIR", tmp_path)
    wa_agent._sudah_diproses.clear()
    dikirim = []

    async def kirim(msg_id, ke, isi):
        dikirim.append((msg_id, ke, isi))
        return True

    monkeypatch.setattr(wa_agent, "kirim_balasan", kirim)
    return dikirim


def pasang(monkeypatch, pesan):
    sb = SupabasePalsu(pesan)
    monkeypatch.setitem(sys.modules, "db", types.SimpleNamespace(supabase=sb))
    return sb


def test_pesan_whatsapp_dibalas_dan_disimpan(env, monkeypatch):
    sb = pasang(monkeypatch, {"twilio_sid": "SM123", "body": "halo", "media_url": None, "media_type": None})
    A.ganti_model(LLMTerskrip(skrip=[lambda r: panggil("lihat_progres"), lambda r: teks("Halo! Mau daftar kategori apa?")], log=[]))
    asyncio.run(wa_agent.proses("s1", "w1"))
    assert env == [("SM123", "6281234567890", "Halo! Mau daftar kategori apa?")]
    keluar = sb.t["messages"].disimpan[0]
    assert keluar["direction"] == "out" and keluar["body"].startswith("Halo!")


def test_webhook_dikirim_ulang_tidak_dibalas_dua_kali(env, monkeypatch):
    pasang(monkeypatch, {"twilio_sid": "SM777", "body": "halo", "media_url": None, "media_type": None})
    A.ganti_model(LLMTerskrip(skrip=[lambda r: teks("Satu."), lambda r: teks("Dua.")], log=[]))
    asyncio.run(wa_agent.proses("s1", "w1"))
    asyncio.run(wa_agent.proses("s1", "w1"))
    assert len(env) == 1


def test_lampiran_whatsapp_diunduh_ke_agen(env, monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    pasang(monkeypatch, {"twilio_sid": "wamid.X1", "body": "", "media_url": "https://x.supabase.co/storage/v1/object/public/media/whatsapp/wamid.X1.png", "media_type": "image/png"})

    async def unduh(url):
        return png

    monkeypatch.setattr(wa_agent, "_unduh", unduh)
    m = LLMTerskrip(skrip=[lambda r: teks("Foto diterima.")], log=[])
    A.ganti_model(m)
    asyncio.run(wa_agent.proses("s1", "w1"))
    assert any(p.inline_data for c in m.log[0].contents for p in c.parts or [])
    assert env[0][0] == "wamid.X1"


def test_tipe_lampiran_tidak_didukung_dilewati(env, monkeypatch):
    pasang(monkeypatch, {"twilio_sid": "SM9", "body": "ini video", "media_url": "https://x/v.mp4", "media_type": "video/mp4"})
    m = LLMTerskrip(skrip=[lambda r: teks("Video belum bisa saya baca.")], log=[])
    A.ganti_model(m)
    asyncio.run(wa_agent.proses("s1", "w1"))
    assert not any(p.inline_data for c in m.log[0].contents for p in c.parts or [])


def test_pecah_pesan_dan_pemilihan_saluran():
    panjang = ("Kalimat satu. " * 200).strip()
    bagian = outbound.pecah_pesan(panjang)
    assert len(bagian) > 1 and all(len(b) <= outbound.BATAS_PESAN for b in bagian)
    assert "".join(b.replace(" ", "") for b in bagian) == panjang.replace(" ", "")
    assert outbound.pecah_pesan("") == [] and outbound.pecah_pesan("pendek") == ["pendek"]
    assert [outbound.saluran_dari_id(x) for x in ("SM1", "MM2", "wamid.A", "dev-123")] == ["twilio", "twilio", "meta", "dev"]
