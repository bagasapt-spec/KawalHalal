"""Tes HTTP endpoint agen dengan LLM terskrip (tanpa Supabase dan tanpa Gemini)."""
import io
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import sihalal_mock as sm  # noqa: E402
from kawal_agent import agent as A, tools as T  # noqa: E402
from routers import agent_chat  # noqa: E402
from test_agen_runner import LLMTerskrip, panggil, teks  # noqa: E402

KUNCI = "kunci-dev"


@pytest.fixture
def klien(tmp_path, monkeypatch):
    monkeypatch.setenv("DEV_INGEST_KEY", KUNCI)
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")
    monkeypatch.setattr(T, "GENERATED_DIR", tmp_path)
    monkeypatch.setattr(agent_chat, "GENERATED_DIR", tmp_path)
    sm.muat_seed()
    app = FastAPI()
    app.include_router(agent_chat.router)
    app.include_router(sm.router)
    return TestClient(app)


def H():
    return {"X-Dev-Key": KUNCI}


def test_chat_butuh_kunci(klien):
    assert klien.post("/api/agent/chat", data={"user_id": "+62811", "pesan": "hai"}).status_code == 403


def test_chat_kosong_dan_user_id_tidak_valid(klien):
    assert klien.post("/api/agent/chat", headers=H(), data={"user_id": "abc", "pesan": "hai"}).status_code == 422
    assert klien.post("/api/agent/chat", headers=H(), data={"user_id": "+62811", "pesan": " "}).status_code == 422


@pytest.mark.parametrize("nama,isi,mime,kode", [
    ("a.exe", b"MZ....", "application/octet-stream", 415),
    ("a.png", b"bukan png sungguhan", "image/png", 400),
    ("a.pdf", b"", "application/pdf", 400),
])
def test_lampiran_ditolak(klien, nama, isi, mime, kode):
    r = klien.post("/api/agent/chat", headers=H(), data={"user_id": "+62811", "pesan": "ini"}, files={"files": (nama, io.BytesIO(isi), mime)})
    assert r.status_code == kode


def test_chat_membuat_xlsx_dan_unduh_bertanda_tangan(klien):
    A.ganti_model(LLMTerskrip(skrip=[
        lambda r: panggil("pilih_kategori", kategori="makanan"),
        lambda r: panggil("buat_berkas_xlsx"),
        lambda r: teks("Berkas siap: " + [p.function_response.response for c in r.contents for p in c.parts or [] if p.function_response][-1]["url"]),
    ], log=[]))
    r = klien.post("/api/agent/chat", headers=H(), data={"user_id": "+62 811-222", "pesan": "buatkan berkasnya"})
    assert r.status_code == 200 and r.json()["alat"] == ["pilih_kategori", "buat_berkas_xlsx"]
    url = r.json()["balasan"].split("Berkas siap: ")[1].strip()
    assert "?t=" in url
    ok = klien.get(url)
    assert ok.status_code == 200 and ok.content[:2] == b"PK"
    # tanda tangan salah, tanpa tanda tangan, dan path traversal ditolak
    assert klien.get(url.split("?")[0] + "?t=salah").status_code == 403
    assert klien.get(url.split("?")[0]).status_code == 403
    assert klien.get("/api/agent/berkas/..%2F..%2Fsihalal_mock.py?t=x").status_code == 403


def test_state_dan_reset(klien):
    A.ganti_model(LLMTerskrip(skrip=[lambda r: panggil("pilih_kategori", kategori="jasa"), lambda r: teks("ok")], log=[]))
    klien.post("/api/agent/chat", headers=H(), data={"user_id": "+62833", "pesan": "jasa katering"})
    assert klien.get("/api/agent/state/+62833", headers=H()).json()["kategori"] == "jasa"
    assert klien.delete("/api/agent/sesi/+62833", headers=H()).json() == {"dihapus": True}
    assert klien.get("/api/agent/state/+62833", headers=H()).json() == {}


def test_login_akun_yang_didaftarkan_agen(klien):
    h = sm.daftarkan_akun("Warung Siti", "Siti", "siti@example.com", "08123456789", "", "Jl. B", "Bandung", "Jawa Barat", "40111", "mikro")
    ok = klien.post("/api/sihalal/akun/masuk", json={"pengguna": "SITI@example.com", "password": h["password"]})
    assert ok.json() == {"berhasil": True}
    assert klien.post("/api/sihalal/akun/masuk", json={"pengguna": h["username"], "password": "salah"}).json() == {"berhasil": False}
