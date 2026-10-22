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
from kawal_agent import gates, operator_ui, tools as T  # noqa: E402
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


def test_rencana_menjadwalkan_proses_dokumen_dan_kirim_pengajuan():
    c = _state_dengan_kecap()
    T.catat_alur_proses("Pembuatan bakso", "Giling daging; Bulatkan; Rebus", c)
    T.catat_catatan_produksi("penyimpanan_bahan", "Kecap manis", 3, "2026-10-20", "", c)
    T.catat_catatan_produksi("penyimpanan_produk", "Bakso Sapi", 15, "2026-10-21", "", c)
    T.catat_catatan_produksi("hasil_produksi", "Bakso Sapi", 50, "2026-10-21", "", c)
    T.catat_catatan_produksi("distribusi", "Bakso Sapi", 25, "2026-10-22", "Warung Berkah", c)
    T.lampirkan_berkas("layout", "denah_dapur.jpg", c)
    T.lampirkan_berkas("tanda_tangan_pj", "ttd_pj.png", c)
    c.state["berkas_dibuat"] = [{"nama": "sjph_pendukung.pdf", "url": "/api/agent/berkas/anon/sjph_pendukung.pdf"}]
    c.state["kirim_pengajuan"] = True

    live = _live()
    aksi = [t["aksi"] for t in operator_ui.rencana(c.state, live)]
    assert "unggah_layout" in aksi
    assert aksi.count("penyimpanan") == 2
    assert "alur_proses" in aksi
    assert "hasil_produksi" in aksi
    assert "distribusi" in aksi
    assert "tanda_tangan" in aksi
    assert "dokumen_lain" in aksi
    assert aksi[-1] == "kirim_pengajuan"

    # Jika pemeriksa melaporkan belum cocok, kirim_pengajuan tidak dijadwalkan
    c.state["hasil_pemeriksa"] = {"cocok": False, "selisih": ["missing: sesuatu"]}
    aksi_tertahan = [t["aksi"] for t in operator_ui.rencana(c.state, live)]
    assert "kirim_pengajuan" not in aksi_tertahan


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

        # Tahap 4: lengkapi proses, komitmen, dokumen/tanda tangan, dan kirim pengajuan lewat browser
        T.isi_data_pengajuan("nomorSurat", "001/PJ/2026", c)
        T.catat_pembelian_bahan("Tepung tapioka", 5, "kg", "2026-10-21", "Gudang", "2026-10-21", c)
        T.catat_alur_proses("Pembuatan bakso sapi", "Cuci daging; Giling; Bulatkan; Rebus", c)
        T.catat_catatan_produksi("penyimpanan_bahan", "Kecap manis", 2, "2026-10-21", "", c)
        T.catat_catatan_produksi("penyimpanan_produk", "Bakso Sapi", 20, "2026-10-21", "", c)
        T.catat_catatan_produksi("hasil_produksi", "Bakso Sapi", 50, "2026-10-21", "", c)
        T.catat_catatan_produksi("distribusi", "Bakso Sapi", 30, "2026-10-22", "Warung Makan Sejahtera", c)
        T.tambah_anggota_komitmen("Joko", "Pemilik", "ketua", c)
        for j_pernyataan in ("kebijakan_halal", "pengertian_halal_haram", "praktik_sjph", "bebas_babi"):
            T.setujui_pernyataan(j_pernyataan, c)
            c.giliran("YA")
            T.setujui_pernyataan(j_pernyataan, c)
        T.lampirkan_berkas("layout", "denah_dapur.png", c)
        T.lampirkan_berkas("tanda_tangan_pj", "ttd_pj.png", c)

        assert operator_ui.tunggu(pid, 120)
        p2 = sm._cari(pid)
        assert len(p2["proses"]["layout"]) == 1
        assert p2["proses"]["layout"][0]["sumber"]["oleh"] == "kawalhalal"
        assert len(p2["proses"]["penyimpanan"]) == 2
        assert p2["proses"]["alurProses"][0]["langkah"] == ["Cuci daging", "Giling", "Bulatkan", "Rebus"]
        assert len(p2["proses"]["hasilProduksi"]) == 1
        assert len(p2["proses"]["distribusi"]) == 1
        assert len(p2["pemantauan"]["tandaTangan"]) == 1
        assert p2["pemantauan"]["tandaTangan"][0]["sumber"]["oleh"] == "kawalhalal"

        cek = T.periksa_pengajuan(c)
        assert cek["siap_kirim"] is True
        assert f"/pengajuan/{pid}" in cek["url_pengajuan"]

        T.minta_konfirmasi("kirim_pengajuan", "Kirim pengajuan sekarang", c)
        c.giliran("YA")
        hasil_kirim = T.kirim_pengajuan_sihalal(c)
        assert hasil_kirim["status"] == "terkirim"
        assert hasil_kirim["nomor_daftar"].startswith("SH")
        assert f"/pengajuan/{pid}" in hasil_kirim["url_pengajuan"]
        assert sm._cari(pid)["status"] == "terkirim"
    finally:
        operator_ui.tutup()
        server.should_exit = True
