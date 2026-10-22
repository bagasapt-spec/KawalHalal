"""Tes operator Kala: rencana murni, dan satu uji nyata dengan browser terhadap server lokal."""
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import sihalal_mock as sm  # noqa: E402
from kawal_agent import operator_ui, tools as T  # noqa: E402
from tests.test_agen_tools import Ctx, siapkan_draf  # noqa: E402

DIST = Path(BACKEND_DIR).parent / "frontend" / "dist"


@pytest.fixture(autouse=True)
def bersih(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "GENERATED_DIR", tmp_path)
    sm.muat_seed()
    sm._akun.clear()
    yield


def _live():
    return sm._cari(sm.buat_draf("self-declare", "baru")["id"])


def _state_dengan_kecap():
    c = Ctx()
    c.state.update({"kategori": "makanan"})
    T.pilih_kategori("makanan", c)
    T.catat_produk("Bakso Sapi", "Bakso Pak Joko", "Produk olahan daging", c)
    T.tambah_bahan("Kecap manis", "bahan", "Kecap Cap Layar", "ID1230000100101", "", "", "", c)
    return c


def test_rencana_menyusun_langkah_formulir_berurutan():
    c = _state_dengan_kecap()
    c.state["pengajuan_id"] = "pj-x"
    live = _live()
    jenis = [t["aksi"] for t in operator_ui.rencana(c.state, live)]
    assert jenis[:3] == ["bahan_tambah", "produk_tambah", "input_bahan"]


def test_rencana_kosong_bila_layar_sudah_sesuai():
    c = _state_dengan_kecap()
    live = _live()
    live["bahan"]["daftarBahan"].append({"id": "b1", "nama": "Kecap manis", "tipe": "bersertifikat", "jenis": "bahan",
                                         "produsen": "Kecap Cap Layar", "noSertifikat": "ID1230000100101"})
    live["produk"].append({"id": "p1", "nama": "Bakso Sapi", "merek": "Bakso Pak Joko", "bahanIds": ["b1"]})
    assert [t["aksi"] for t in operator_ui.rencana(c.state, live) if t["aksi"] != "petakan"] == []


def test_bahan_bercelah_dicatat_tanpa_nomor_agar_bukti_kurang():
    c = Ctx()
    T.pilih_kategori("makanan", c)
    T.tambah_bahan("Gelatin", "bahan", "", "", "", "", "", c)
    c.state["dok"]["bahan"][0]["disetujui"] = True
    (d,) = operator_ui._bahan_diinginkan(c.state)
    assert (d["tipe"], d["noSertifikat"]) == ("bersertifikat", "")


def _port_bebas() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _browser_tersedia() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


@pytest.mark.skipif(not (DIST / "index.html").exists() or not _browser_tersedia(), reason="butuh build frontend dan Chromium Playwright")
def test_operator_mengisi_form_lewat_browser(monkeypatch):
    import uvicorn
    import main
    from services import telegram_bot

    monkeypatch.setattr(telegram_bot, "aktif", lambda: False)
    port = _port_bebas()
    monkeypatch.setenv("KALA_OPERATOR", "ui")
    monkeypatch.setenv("OPERATOR_BASE_URL", f"http://127.0.0.1:{port}")
    main.sajikan_frontend(DIST)
    server = uvicorn.Server(uvicorn.Config(main.app, port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.1)
    try:
        c = siapkan_draf(Ctx())
        T.catat_produk("Bakso Sapi", "Bakso Pak Joko", "Produk olahan daging", c)
        T.tambah_bahan("Kecap manis", "bahan", "Kecap Cap Layar", "ID1230000100101", "", "", "", c)
        T.tambah_bahan("Tepung tapioka", "bahan", "", "", "", "", "", c)
        T.catat_pembelian_bahan("Kecap manis", 2, "kg", "2026-10-21", "Dapur", "2026-10-21", c)
        pid = c.state["pengajuan_id"]
        assert operator_ui.tunggu(pid, 120)
        p = sm._cari(pid)
        nama = {b["nama"]: b for b in p["bahan"]["daftarBahan"]}
        assert {"Kecap manis", "Tepung tapioka"} <= set(nama)
        assert nama["Kecap manis"]["sumber"]["oleh"] == "kawalhalal"
        assert nama["Kecap manis"]["noSertifikat"] == "ID1230000100101"
        assert p["produk"][0]["bahanIds"], "bahan belum terpasang ke produk"
        assert p["pemetaan"], "produk belum dipetakan ke fasilitas"
        assert p["bahan"]["catatanPembelian"] and p["bahan"]["pemeriksaan"]
        # sinkron kedua tidak menulis ulang: layar sudah sesuai
        T.sinkron_ke_sihalal(c)
        assert operator_ui.tunggu(pid, 60)
        assert len(sm._cari(pid)["bahan"]["daftarBahan"]) == len(p["bahan"]["daftarBahan"])
    finally:
        operator_ui.tutup()
        server.should_exit = True
