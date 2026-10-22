"""Tes unit dan integrasi untuk agen operator ADK (Tahap 1 multi-agent)."""
import asyncio
import copy
import os
import sys

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import sihalal_mock as sm  # noqa: E402
from kawal_agent import agen_operator as AO, agent as A, operator_ui, sinkron as sk, tools as T  # noqa: E402
from tests.test_agen_runner import LLMTerskrip, hasil_fungsi_terakhir, panggil, teks  # noqa: E402
from tests.test_agen_tools import Ctx  # noqa: E402


class LayarPalsu:
    """Pengganti _Layar yang meniru perubahan di web SIHALAL tanpa membuka browser."""

    def __init__(self, live: dict, gagal_sekali: set[str] | None = None, gagal_selalu: set[str] | None = None):
        self.live = copy.deepcopy(live)
        self.gagal_sekali = set(gagal_sekali or ())
        self.gagal_selalu = set(gagal_selalu or ())
        self.dikerjakan: list[dict] = []
        self.log: list[str] = []
        self.tab: str | None = None

    def catat(self, pesan: str) -> None:
        self.log.append(pesan)

    def baca(self) -> dict:
        return copy.deepcopy(self.live)

    def buka(self, tab: str) -> None:
        self.tab = tab

    def lihat(self, tab: str = "") -> str:
        self.buka(tab or self.tab or "bahan")
        daftar_b = ", ".join(b["nama"] for b in self.live["bahan"]["daftarBahan"]) or "(kosong)"
        return f"Tab aktif: {self.tab} | Bahan tercatat: {daftar_b}"

    def lakukan(self, t: dict) -> None:
        aksi = t["aksi"]
        if aksi in self.gagal_selalu:
            raise RuntimeError(f"Elemen {aksi} selalu gagal diakses")
        if aksi in self.gagal_sekali:
            self.gagal_sekali.discard(aksi)
            raise TimeoutError(f"Dialog {aksi} belum siap")

        self.dikerjakan.append(copy.deepcopy(t))
        if aksi == "bahan_tambah":
            bid = f"b-{len(self.live['bahan']['daftarBahan']) + 1}"
            self.live["bahan"]["daftarBahan"].append({
                "id": bid,
                "nama": t["nama"],
                "tipe": t["tipe"],
                "jenis": t["jenis"],
                "produsen": t["produsen"],
                "noSertifikat": t["noSertifikat"],
            })
        elif aksi == "bahan_ubah":
            for b in self.live["bahan"]["daftarBahan"]:
                if sk._norm(b["nama"]) == sk._norm(t["nama"]):
                    b.update({
                        "tipe": t["tipe"],
                        "jenis": t["jenis"],
                        "produsen": t["produsen"],
                        "noSertifikat": t["noSertifikat"],
                    })
        elif aksi == "produk_tambah":
            pid = f"p-{len(self.live['produk']) + 1}"
            self.live["produk"].append({
                "id": pid,
                "nama": t["nama"],
                "merek": t["merek"],
                "klasifikasi": t["klasifikasi"],
                "rincian": t["rincian"],
                "bahanIds": [],
            })
        elif aksi == "input_bahan":
            id_per_nama = {sk._norm(b["nama"]): b["id"] for b in self.live["bahan"]["daftarBahan"]}
            for pr in self.live["produk"]:
                if sk._norm(pr["nama"]) == sk._norm(t["produk"]):
                    pr["bahanIds"] = [id_per_nama[sk._norm(b["nama"])] for b in t["bahan"] if sk._norm(b["nama"]) in id_per_nama]
        elif aksi == "petakan":
            pabrik_id = (self.live["data"].get("pabrikIds") or ["pb-1"])[0]
            for pr in self.live["produk"]:
                if sk._norm(pr["nama"]) == sk._norm(t["produk"]):
                    self.live["pemetaan"].append({"id": f"pm-{pr['id']}", "produkId": pr["id"], "pabrikId": pabrik_id})


@pytest.fixture(autouse=True)
def lingkungan(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_NONAKTIF", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")
    monkeypatch.setattr(T, "GENERATED_DIR", tmp_path)
    sm.muat_seed()
    sm._akun.clear()
    AO.ganti_model(None)
    yield
    AO.ganti_model(None)


def _siapkan_state_dan_live():
    c = Ctx()
    T.pilih_kategori("makanan", c)
    T.catat_produk("Bakso Sapi", "Bakso Pak Joko", "Produk olahan daging", c)
    T.tambah_bahan("Kecap manis", "bahan", "Kecap Cap Layar", "ID1230000100101", "", "", "", c)
    live = copy.deepcopy(sm._cari(sm.buat_draf("self-declare", "baru")["id"]))
    live["data"]["pabrikIds"] = ["pb-1"]
    c.state["pengajuan_id"] = live["id"]
    return c.state, live


def test_konfigurasi_agen_operator_dan_isolasi_modul(monkeypatch):
    assert "sihalal_mock" not in AO.__dict__
    assert AO.operator.name == "operator"

    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    monkeypatch.delenv("GEMINI_MODEL_RINGAN", raising=False)
    assert AO.bangun_agen().model == "gemini-2.0-flash"

    monkeypatch.setenv("GEMINI_MODEL_RINGAN", "gemini-2.0-flash-lite")
    assert AO.bangun_agen().model == "gemini-2.0-flash-lite"


def test_agen_operator_memanggil_lihat_rencana_dan_kerjakan_tugas_berurutan():
    state, live = _siapkan_state_dan_live()
    layar = LayarPalsu(live)

    AO.ganti_model(
        LLMTerskrip(
            skrip=[
                lambda r: panggil("lihat_rencana"),
                lambda r: panggil("kerjakan_tugas", nomor=1),
                lambda r: panggil("kerjakan_tugas", nomor=2),
                lambda r: panggil("kerjakan_tugas", nomor=3),
                lambda r: panggil("kerjakan_tugas", nomor=4),
                lambda r: teks(f"Selesai mengerjakan {hasil_fungsi_terakhir(r)['nomor']} langkah."),
            ],
            log=[],
        )
    )

    hasil = asyncio.run(AO.jalankan(state, layar, pid=state["pengajuan_id"]))
    assert hasil["alat"] == [
        "lihat_rencana",
        "kerjakan_tugas",
        "kerjakan_tugas",
        "kerjakan_tugas",
        "kerjakan_tugas",
    ]
    assert hasil["gagal"] == []
    assert [t["aksi"] for t in layar.dikerjakan] == ["bahan_tambah", "produk_tambah", "input_bahan", "petakan"]
    assert "Selesai mengerjakan 4 langkah." in hasil["balasan"]


def test_agen_operator_mengulang_langkah_gagal_maksimal_sekali_dan_lihat_layar():
    state, live = _siapkan_state_dan_live()
    layar = LayarPalsu(live, gagal_sekali={"bahan_tambah"})

    AO.ganti_model(
        LLMTerskrip(
            skrip=[
                lambda r: panggil("lihat_rencana"),
                lambda r: panggil("kerjakan_tugas", nomor=1),  # percobaan 1 gagal
                lambda r: panggil("lihat_layar", tab="bahan"),
                lambda r: panggil("kerjakan_tugas", nomor=1),  # ulangan 1 berhasil
                lambda r: panggil("kerjakan_tugas", nomor=2),
                lambda r: panggil("kerjakan_tugas", nomor=3),
                lambda r: panggil("kerjakan_tugas", nomor=4),
                lambda r: teks("Semua langkah beres setelah 1 kali ulang."),
            ],
            log=[],
        )
    )

    hasil = asyncio.run(AO.jalankan(state, layar, pid=state["pengajuan_id"]))
    assert hasil["gagal"] == []
    assert "lihat_layar" in hasil["alat"]
    assert hasil["riwayat_tugas"][0]["status"] == "gagal"
    assert hasil["riwayat_tugas"][1]["status"] == "ok" and hasil["riwayat_tugas"][1]["percobaan"] == 2
    assert len([x for x in layar.dikerjakan if x["aksi"] == "bahan_tambah"]) == 1

    # Verifikasi batas pengulangan maksimal 1 kali ulang (total 2 percobaan)
    layar_rusak = LayarPalsu(live, gagal_selalu={"bahan_tambah"})
    AO.pasang_konteks(state, layar_rusak)
    AO.lihat_rencana()
    r1 = AO.kerjakan_tugas(1)
    r2 = AO.kerjakan_tugas(1)
    r3 = AO.kerjakan_tugas(1)
    assert r1["status"] == "gagal" and r1["percobaan"] == 1
    assert r2["status"] == "gagal" and r2["percobaan"] == 2
    assert r3["status"] == "gagal" and r3.get("batas_ulang") is True


def test_idempotensi_kerjakan_tugas_tidak_menduplikasi_isian():
    state, live = _siapkan_state_dan_live()
    layar = LayarPalsu(live)

    AO.ganti_model(
        LLMTerskrip(
            skrip=[
                lambda r: panggil("lihat_rencana"),
                lambda r: panggil("kerjakan_tugas", nomor=1),
                lambda r: panggil("kerjakan_tugas", nomor=1),  # panggilan duplikat
                lambda r: panggil("kerjakan_tugas", nomor=2),
                lambda r: panggil("kerjakan_tugas", nomor=3),
                lambda r: panggil("kerjakan_tugas", nomor=4),
                lambda r: teks("Selesai tanpa duplikasi."),
            ],
            log=[],
        )
    )

    hasil = asyncio.run(AO.jalankan(state, layar, pid=state["pengajuan_id"]))
    assert hasil["gagal"] == []
    assert len(layar.live["bahan"]["daftarBahan"]) == 1
    assert len([x for x in layar.dikerjakan if x["aksi"] == "bahan_tambah"]) == 1


def test_pekerja_operator_ui_integrasi_agen_dan_fallback_429(monkeypatch):
    state, live = _siapkan_state_dan_live()
    pid = state["pengajuan_id"]

    # 1. Mode KALA_OPERATOR_AGEN=1 sukses lewat Runner terpisah tanpa menyentuh pelaksana deterministik
    monkeypatch.setenv("KALA_OPERATOR_AGEN", "1")
    layar_sukses = LayarPalsu(live)
    fallback_dipanggil = []

    def pelaksana_cadangan(p_id, st, ref, user):
        fallback_dipanggil.append(p_id)
        return []

    pekerja = operator_ui._Pekerja(
        pelaksana=pelaksana_cadangan,
        pembuat_layar=lambda p_id, user, ref: layar_sukses,
    )
    AO.ganti_model(
        LLMTerskrip(
            skrip=[
                lambda r: panggil("lihat_rencana"),
                lambda r: panggil("kerjakan_tugas", nomor=1),
                lambda r: panggil("kerjakan_tugas", nomor=2),
                lambda r: panggil("kerjakan_tugas", nomor=3),
                lambda r: panggil("kerjakan_tugas", nomor=4),
                lambda r: teks("Berhasil diisi lewat agen."),
            ],
            log=[],
        )
    )
    pekerja._kerjakan({"pid": pid, "state": state, "ref": "ref-1"})
    assert fallback_dipanggil == []
    assert [b["nama"] for b in layar_sukses.live["bahan"]["daftarBahan"]] == ["Kecap manis"]
    assert [p["nama"] for p in layar_sukses.live["produk"]] == ["Bakso Sapi"]
    # Pastikan sesi Kala tetap terisolasi (kosong)
    assert asyncio.run(A.lihat_state(f"operator-{pid}")) == {}

    # 2. Mode KALA_OPERATOR_AGEN=1 mengalami error runtime 429 di tengah jalan -> otomatis fallback deterministik
    layar_429 = LayarPalsu(live)
    pekerja_429 = operator_ui._Pekerja(
        pembuat_layar=lambda p_id, user, ref: layar_429,
    )

    def ledakkan_429(_req):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: Quota exceeded for gemini")

    AO.ganti_model(
        LLMTerskrip(
            skrip=[
                lambda r: panggil("lihat_rencana"),
                lambda r: panggil("kerjakan_tugas", nomor=1),  # baru selesai langkah 1
                ledakkan_429,  # langkah berikutnya kena 429
            ],
            log=[],
        )
    )
    pekerja_429._kerjakan({"pid": pid, "state": state, "ref": "ref-2"})

    # Langkah 1 yang sudah dikerjakan agen tidak diduplikasi, dan sisa langkah 2..4 diselesaikan fallback deterministik
    assert [b["nama"] for b in layar_429.live["bahan"]["daftarBahan"]] == ["Kecap manis"]
    assert [p["nama"] for p in layar_429.live["produk"]] == ["Bakso Sapi"]
    assert layar_429.live["produk"][0]["bahanIds"] != []
    assert layar_429.live["pemetaan"] != []
    assert [t["aksi"] for t in layar_429.dikerjakan] == ["bahan_tambah", "produk_tambah", "input_bahan", "petakan"]
    assert any("beralih ke pelaksana deterministik" in baris for baris in pekerja_429.riwayat(pid))
