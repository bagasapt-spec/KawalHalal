"""Tes unit dan integrasi untuk agen pemeriksa ADK (Tahap 2 multi-agent)."""
import copy
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import sihalal_mock as sm  # noqa: E402
from kawal_agent import agen_operator as AO, agen_pemeriksa as AP, operator_ui, sinkron as sk, tools as T  # noqa: E402
from tests.test_agen_operator import LayarPalsu  # noqa: E402
from tests.test_agen_runner import LLMTerskrip, hasil_fungsi_terakhir, panggil, teks  # noqa: E402
from tests.test_agen_tools import Ctx, lengkapi_semua, setujui_pernyataan, siapkan_draf  # noqa: E402


@pytest.fixture(autouse=True)
def lingkungan(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_NONAKTIF", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")
    monkeypatch.setattr(T, "GENERATED_DIR", tmp_path)
    sm.muat_seed()
    sm._akun.clear()
    AO.ganti_model(None)
    AP.ganti_model(None)
    operator_ui.reset_pemeriksa()
    yield
    AO.ganti_model(None)
    AP.ganti_model(None)
    operator_ui.reset_pemeriksa()


def _siapkan_state_dan_live_lengkap():
    c = Ctx()
    T.pilih_kategori("makanan", c)
    T.catat_produk("Bakso Sapi", "Bakso Pak Joko", "Produk olahan daging", c)
    T.tambah_bahan("Kecap manis", "bahan", "Kecap Cap Layar", "ID1230000100101", "", "", "", c)
    T.tambah_bahan("Tepung tapioka", "bahan", "", "", "Pasar", "", "", c)
    live = copy.deepcopy(sm._cari(sm.buat_draf("self-declare", "baru")["id"]))
    live["data"]["pabrikIds"] = ["pb-1"]
    c.state["pengajuan_id"] = live["id"]
    return c, live


def test_konfigurasi_agen_pemeriksa_dan_model_ringan(monkeypatch):
    assert AP.pemeriksa.name == "pemeriksa"
    nama_tool = {fn.__name__ for fn in AP.pemeriksa.tools}
    assert {"baca_tab", "niat_kala"} <= nama_tool

    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.delenv("GEMINI_MODEL_RINGAN", raising=False)
    assert AP.bangun_agen().model == "gemini-2.0-flash"

    monkeypatch.setenv("GEMINI_MODEL_RINGAN", "gemini-2.0-flash-lite")
    assert AP.bangun_agen().model == "gemini-2.0-flash-lite"


def test_pemeriksa_data_klop_tanpa_mengulang_operator():
    c, live = _siapkan_state_dan_live_lengkap()
    pid = c.state["pengajuan_id"]
    layar = LayarPalsu(live)
    panggilan_operator = []

    def pelaksana_normal(p_id, st, ref, user):
        panggilan_operator.append(p_id)
        for t in operator_ui.rencana(st, layar.baca()):
            layar.lakukan(t)
        return []

    model_pemeriksa = LLMTerskrip(
        skrip=[
            lambda r: panggil("niat_kala"),
            lambda r: panggil("baca_tab", tab="bahan"),
            lambda r: panggil("baca_tab", tab="produk"),
            lambda r: teks(
                "Semua data bahan, produk, dan pemetaan sudah cocok dan lengkap sesuai niat Kala "
                f"(selisih: {len(hasil_fungsi_terakhir(r)['selisih_terdeteksi'])})."
            ),
        ],
        log=[],
    )
    AP.ganti_model(model_pemeriksa)

    pekerja = operator_ui._Pekerja(
        pelaksana=pelaksana_normal,
        pembuat_layar=lambda p_id, user, ref: layar,
    )
    pekerja._kerjakan({"pid": pid, "state": c.state, "ref": "ref-klop"})

    # Operator hanya dijalankan 1 kali karena pemeriksa menyatakan data klop
    assert len(panggilan_operator) == 1
    assert len(model_pemeriksa.log) == 4
    hasil = pekerja.hasil_pemeriksa(pid)
    assert hasil is not None
    assert hasil["cocok"] is True
    assert hasil["selisih"] == []
    assert hasil["diulang"] is False
    assert any("sesuai dengan niat Kala (cocok)" in baris for baris in pekerja.riwayat(pid))


def test_pemeriksa_selisih_buatan_memicu_ulangan_operator_tepat_sekali():
    c, live = _siapkan_state_dan_live_lengkap()
    pid = c.state["pengajuan_id"]
    layar = LayarPalsu(live)
    panggilan_operator = []

    def pelaksana_lupa_satu_bahan_di_awal(p_id, st, ref, user):
        putaran = len(panggilan_operator) + 1
        panggilan_operator.append(putaran)
        for t in operator_ui.rencana(st, layar.baca()):
            # Pada putaran pertama, sengaja lewati bahan 'Tepung tapioka' agar timbul selisih buatan
            if putaran == 1 and t["aksi"] == "bahan_tambah" and sk._norm(t["nama"]) == "tepung tapioka":
                continue
            if putaran == 1 and t["aksi"] == "input_bahan":
                t = {
                    **t,
                    "bahan": [b for b in t["bahan"] if sk._norm(b["nama"]) != "tepung tapioka"],
                }
            layar.lakukan(t)
        return []

    model_pemeriksa = LLMTerskrip(
        skrip=[
            # Pemeriksaan 1 (setelah putaran 1 operator): mendeteksi Tepung tapioka belum masuk
            lambda r: panggil("niat_kala"),
            lambda r: panggil("baca_tab", tab="bahan"),
            lambda r: teks(
                "missing: Bahan 'Tepung tapioka' belum masuk di SIHALAL. "
                + "; ".join(hasil_fungsi_terakhir(r)["selisih_terdeteksi"])
            ),
            # Pemeriksaan 2 (setelah 1x pengulangan operator): semua sudah lengkap
            lambda r: panggil("niat_kala"),
            lambda r: panggil("baca_tab", tab="bahan"),
            lambda r: teks("Semua data bahan, produk, dan pemetaan di SIHALAL sudah cocok dan lengkap."),
        ],
        log=[],
    )
    AP.ganti_model(model_pemeriksa)

    pekerja = operator_ui._Pekerja(
        pelaksana=pelaksana_lupa_satu_bahan_di_awal,
        pembuat_layar=lambda p_id, user, ref: layar,
    )
    pekerja._kerjakan({"pid": pid, "state": c.state, "ref": "ref-selisih"})

    # Operator dijalankan tepat 2 kali (1 awal + 1 ulangan karena selisih)
    assert panggilan_operator == [1, 2]
    nama_bahan_akhir = {b["nama"] for b in layar.live["bahan"]["daftarBahan"]}
    assert {"Kecap manis", "Tepung tapioka"} <= nama_bahan_akhir

    hasil = pekerja.hasil_pemeriksa(pid)
    assert hasil is not None
    assert hasil["diulang"] is True
    assert hasil["jumlah_ulang"] == 1
    assert any("Tepung tapioka" in s for s in hasil["selisih_awal"])
    assert hasil["cocok"] is True
    assert hasil["selisih"] == []

    riwayat = pekerja.riwayat(pid)
    assert any("mengulang operator (1/1)" in baris for baris in riwayat)
    assert any("selisih teratasi setelah 1x pengulangan operator" in baris for baris in riwayat)


def test_pemeriksa_selisih_permanen_berhenti_setelah_satu_kali_ulang_tanpa_infinite_loop():
    c, live = _siapkan_state_dan_live_lengkap()
    pid = c.state["pengajuan_id"]
    layar = LayarPalsu(live)
    panggilan_operator = []

    def pelaksana_selalu_lupa_produk(p_id, st, ref, user):
        panggilan_operator.append(len(panggilan_operator) + 1)
        for t in operator_ui.rencana(st, layar.baca()):
            # Sengaja selalu abaikan penambahan produk Bakso Sapi bahkan saat diulang
            if t["aksi"] in ("produk_tambah", "input_bahan", "petakan"):
                continue
            layar.lakukan(t)
        return []

    model_pemeriksa = LLMTerskrip(
        skrip=[
            lambda r: panggil("niat_kala"),
            lambda r: panggil("baca_tab", tab="produk"),
            lambda r: teks("missing: Produk 'Bakso Sapi' belum masuk di SIHALAL."),
            lambda r: panggil("niat_kala"),
            lambda r: panggil("baca_tab", tab="produk"),
            lambda r: teks("missing: Produk 'Bakso Sapi' masih belum masuk di SIHALAL."),
        ],
        log=[],
    )
    AP.ganti_model(model_pemeriksa)

    pekerja = operator_ui._Pekerja(
        pelaksana=pelaksana_selalu_lupa_produk,
        pembuat_layar=lambda p_id, user, ref: layar,
    )
    pekerja._kerjakan({"pid": pid, "state": c.state, "ref": "ref-permanen"})

    # Wajib berhenti setelah 1 kali ulang (total 2 panggilan operator), tidak boleh infinite loop
    assert panggilan_operator == [1, 2]
    hasil = pekerja.hasil_pemeriksa(pid)
    assert hasil is not None
    assert hasil["diulang"] is True
    assert hasil["jumlah_ulang"] == 1
    assert hasil["cocok"] is False
    assert any("Bakso Sapi" in s for s in hasil["selisih"])
    assert any("berhenti sesuai batas ulang" in baris for baris in pekerja.riwayat(pid))


def test_periksa_pengajuan_memuat_laporan_dan_selisih_pemeriksa():
    c = siapkan_draf(Ctx().giliran("mulai"))
    lengkapi_semua(c)
    setujui_pernyataan(c)
    pid = c.state["pengajuan_id"]

    # Sengaja hapus satu bahan ('Tepung tapioka') langsung dari penyimpanan SIHALAL
    # untuk mensimulasikan selisih nyata antara niat Kala dan data di SIHALAL
    with sm._kunci:
        p = sm._cari(pid)
        p["bahan"]["daftarBahan"] = [
            b for b in p["bahan"]["daftarBahan"] if sk._norm(b["nama"]) != "tepung tapioka"
        ]

    AP.ganti_model(
        LLMTerskrip(
            skrip=[
                lambda r: panggil("niat_kala"),
                lambda r: panggil("baca_tab", tab="bahan"),
                lambda r: teks(
                    "Pemeriksa menemukan selisih: missing Bahan 'Tepung tapioka' belum masuk di SIHALAL."
                ),
            ],
            log=[],
        )
    )

    cek = T.periksa_pengajuan(c)
    assert cek["siap_kirim"] is False
    assert "pemeriksa" in cek
    assert cek["pemeriksa"]["cocok"] is False
    assert any("Tepung tapioka" in s for s in cek["selisih_pemeriksa"])
    assert "Tepung tapioka" in cek["catatan_pemeriksa"]
    assert any("Tepung tapioka" in m for m in cek["harus_diperbaiki"])

    # Setelah disinkronkan ulang dan data kembali lengkap, periksa_pengajuan menyatakan siap_kirim
    T.sinkron_ke_sihalal(c)
    AP.ganti_model(
        LLMTerskrip(
            skrip=[
                lambda r: panggil("niat_kala"),
                lambda r: panggil("baca_tab", tab="bahan"),
                lambda r: teks("Semua data bahan, produk, dan pemetaan sudah cocok dan lengkap."),
            ],
            log=[],
        )
    )
    cek_ulang = T.periksa_pengajuan(c)
    assert cek_ulang["siap_kirim"] is True
    assert cek_ulang["pemeriksa"]["cocok"] is True
    assert cek_ulang["selisih_pemeriksa"] == []
