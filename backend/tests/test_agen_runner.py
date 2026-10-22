"""Tes integrasi ADK: Runner + callback + tool dengan LLM terskrip (tanpa API Gemini)."""
import asyncio
import os
import sys

import pytest
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import sihalal_mock as sm  # noqa: E402
from kawal_agent import agent as A, tools as T  # noqa: E402


class LLMTerskrip(BaseLlm):
    """Model palsu: tiap panggilan mengambil langkah berikutnya dari skrip. Langkah = fungsi(llm_request) -> Part list."""

    model: str = "terskrip"
    skrip: list = []
    log: list = []

    async def generate_content_async(self, llm_request, stream=False):
        i = len(self.log)
        self.log.append(llm_request)
        parts = self.skrip[i](llm_request)
        yield LlmResponse(content=types.Content(role="model", parts=parts))


def panggil(_fungsi, **args):
    return [types.Part.from_function_call(name=_fungsi, args=args)]


def teks(t):
    return [types.Part.from_text(text=t)]


def hasil_fungsi_terakhir(req) -> dict:
    for c in reversed(req.contents):
        for p in c.parts or []:
            if p.function_response:
                return p.function_response.response
    return {}


@pytest.fixture(autouse=True)
def lingkungan(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_NONAKTIF", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")
    monkeypatch.setattr(T, "GENERATED_DIR", tmp_path)
    sm.muat_seed()
    sm._akun.clear()
    from kawal_agent import operator_ui

    operator_ui.reset_pemeriksa()
    yield
    operator_ui.reset_pemeriksa()


def pakai(skrip):
    m = LLMTerskrip(skrip=skrip, log=[])
    A.ganti_model(m)
    return m


def jalan(user, pesan, lampiran=None):
    return asyncio.run(A.jalankan(user, pesan, lampiran))


def test_agen_memakai_tool_dan_state_tersimpan():
    m = pakai([
        lambda r: panggil("lihat_progres"),
        lambda r: teks(f"Halo! Pilih kategori: {len(hasil_fungsi_terakhir(r)['pilihan_kategori'])} pilihan."),
        lambda r: panggil("pilih_kategori", kategori="2"),
        lambda r: teks("Kategori " + hasil_fungsi_terakhir(r)["label"]),
    ])
    r = jalan("+628111", "halo")
    assert r["balasan"] == "Halo! Pilih kategori: 5 pilihan." and r["alat"] == ["lihat_progres"]
    r = jalan("+628111", "2")
    assert r["balasan"] == "Kategori Minuman" and r["alat"] == ["pilih_kategori"]
    assert asyncio.run(A.lihat_state("+628111"))["kategori"] == "minuman"
    # pesan pengguna dan hasil tool memang sampai ke model
    assert any("halo" in (p.text or "") for c in m.log[0].contents for p in c.parts or [])


def test_guardrail_mengganti_klaim_halal():
    pakai([lambda r: teks("Tenang, produk Anda pasti halal dan pasti lolos.")])
    r = jalan("+628112", "apakah produk saya halal?")
    assert "tidak dapat menyatakan" in r["balasan"].lower() and "pasti halal" not in r["balasan"].lower()
    assert asyncio.run(A.lihat_state("+628112"))["guardrail_terpicu"] == 1


def test_konfirmasi_lintas_giliran_lewat_runner():
    """Gate dijalankan callback ADK dari pesan pengguna sungguhan, bukan dari model."""
    pakai([
        # giliran 1: daftar akun, buat draf, tambah bahan bercelah, minta konfirmasi
        lambda r: panggil("pilih_kategori", kategori="makanan"),
        lambda r: panggil("daftarkan_akun_sihalal", nama_usaha="Bakso Pak Joko", nama_penanggung_jawab="Joko", email="joko@example.com",
                          no_hp="081234567890", nib="9120001234567", alamat="Jl. Mawar 1", kab_kota="Bandung", provinsi="Jawa Barat",
                          kode_pos="40135", skala="mikro"),
        lambda r: panggil("buat_draf_pengajuan", jalur="self-declare"),
        lambda r: panggil("tambah_bahan", nama="Gelatin", jenis="bahan", produsen="", nomor_sertifikat="", pemasok="", jenis_hewan="", foto_bukti=""),
        lambda r: panggil("minta_konfirmasi", aksi_id="masukkan_bahan_bermasalah", ringkasan="Gelatin belum ada sertifikat. Tetap masukkan?"),
        lambda r: teks("Gelatin belum punya sertifikat. Tetap dimasukkan? Balas YA atau TIDAK."),
        # giliran 2: model mencoba sinkron; hanya berhasil karena pengguna benar-benar membalas YA
        lambda r: panggil("lihat_progres"),
        lambda r: panggil("sinkron_ke_sihalal"),
        lambda r: teks("Sudah masuk sebagai perlu konfirmasi."),
    ])
    u = "+628113"
    r = jalan(u, "mulai daftar makanan")
    assert "YA atau TIDAK" in r["balasan"]
    pid = asyncio.run(A.lihat_state(u))["pengajuan_id"]
    assert sm._cari(pid)["bahan"]["daftarBahan"] == []
    r = jalan(u, "ya")
    st = asyncio.run(A.lihat_state(u))
    assert [b["nama"] for b in sm._cari(pid)["bahan"]["daftarBahan"]] == ["Gelatin"]
    assert r["alat"] == ["lihat_progres", "sinkron_ke_sihalal"]


def test_lampiran_disimpan_dan_dilaporkan_ke_model(tmp_path):
    m = pakai([lambda r: panggil("lihat_progres"), lambda r: teks("ok " + ",".join(hasil_fungsi_terakhir(r)["berkas_dari_pengguna"]))])
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    r = jalan("+628114", "ini label bumbu", [{"nama": "../../label bumbu.png", "mime": "image/png", "data": png}])
    assert r["balasan"] == "ok label bumbu.png"
    # gambar benar-benar dikirim ke model sebagai bagian multimodal
    assert any(p.inline_data and p.inline_data.mime_type == "image/png" for c in m.log[0].contents for p in c.parts or [])
    assert (T.folder_pengguna("+628114") / "unggahan" / "label bumbu.png").exists()


def test_tanpa_kunci_model_jujur_tidak_pura_pura(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_ENTERPRISE", raising=False)
    r = jalan("+628115", "halo")
    assert r["aktif"] is False and "belum aktif" in r["balasan"]


def test_ya_otomatis_memasukkan_bahan_tanpa_model_memanggil_sinkron():
    """Bahan bercelah: sistem mencatat konfirmasi sendiri, dan balasan YA langsung memasukkannya walau model hanya membalas teks."""
    pakai([
        lambda r: panggil("pilih_kategori", kategori="makanan"),
        lambda r: panggil("daftarkan_akun_sihalal", nama_usaha="Bakso Pak Joko", nama_penanggung_jawab="Joko", email="joko@example.com",
                          no_hp="081234567890", nib="9120001234567", alamat="Jl. Mawar 1", kab_kota="Bandung", provinsi="Jawa Barat",
                          kode_pos="40135", skala="mikro"),
        lambda r: panggil("buat_draf_pengajuan", jalur="self-declare"),
        # model LUPA memanggil minta_konfirmasi, hanya bertanya lewat teks
        lambda r: panggil("tambah_bahan", nama="Gelatin", jenis="bahan", produsen="", nomor_sertifikat="", pemasok="", jenis_hewan="", foto_bukti=""),
        lambda r: teks("Gelatin belum ada sertifikat. Tetap dimasukkan? YA atau TIDAK."),
        # giliran 2: model hanya membalas teks, tidak memanggil tool apa pun
        lambda r: teks("Baik, sudah masuk."),
    ])
    u = "+628119"
    jalan(u, "mulai")
    pid = asyncio.run(A.lihat_state(u))["pengajuan_id"]
    assert sm._cari(pid)["bahan"]["daftarBahan"] == []
    assert asyncio.run(A.lihat_state(u))["menunggu"]["id"] == "masukkan_bahan_bermasalah"
    jalan(u, "ya")
    assert [b["nama"] for b in sm._cari(pid)["bahan"]["daftarBahan"]] == ["Gelatin"]


def test_jawaban_ragu_tidak_memasukkan_bahan():
    pakai([
        lambda r: panggil("pilih_kategori", kategori="makanan"),
        lambda r: panggil("daftarkan_akun_sihalal", nama_usaha="Warung A", nama_penanggung_jawab="Ani", email="ani@example.com",
                          no_hp="081234567891", nib="", alamat="Jl. B", kab_kota="Bandung", provinsi="Jawa Barat",
                          kode_pos="40111", skala="mikro"),
        lambda r: panggil("buat_draf_pengajuan", jalur="self-declare"),
        lambda r: panggil("tambah_bahan", nama="Gelatin", jenis="bahan", produsen="", nomor_sertifikat="", pemasok="", jenis_hewan="", foto_bukti=""),
        lambda r: teks("Tetap dimasukkan?"),
        lambda r: teks("Baik."),
    ])
    u = "+628118"
    jalan(u, "mulai")
    pid = asyncio.run(A.lihat_state(u))["pengajuan_id"]
    jalan(u, "ya tapi nanti dulu")
    assert sm._cari(pid)["bahan"]["daftarBahan"] == []


def test_instruksi_kala_memuat_aturan_orkestrator_operator_dan_pemeriksa():
    from kawal_agent import prompts

    assert prompts.INSTRUKSI_KALA == prompts.INSTRUKSI
    assert "lihat_progres" in prompts.INSTRUKSI_KALA
    assert "pemeriksa" in prompts.INSTRUKSI_KALA.lower()
    assert "latar belakang" in prompts.INSTRUKSI_KALA.lower()
    assert "YA atau TIDAK" in prompts.INSTRUKSI_KALA
    assert "selisih_pemeriksa" in prompts.INSTRUKSI_KALA
    assert "latar belakang" in prompts.INSTRUKSI_OPERATOR.lower()
    assert "pemeriksa" in prompts.INSTRUKSI_OPERATOR.lower()


def test_kala_menyebutkan_proses_operator_latar_belakang_saat_tugas_dijadwalkan(monkeypatch):
    from kawal_agent import operator_ui

    monkeypatch.setenv("KALA_OPERATOR", "ui")
    antrean_dijadwalkan = []

    def serahkan_palsu(state, ref):
        pid = state.get("pengajuan_id")
        antrean_dijadwalkan.append((pid, ref))
        return {
            "disinkronkan": True,
            "mode": "operator_ui",
            "bahan_ditahan_menunggu_konfirmasi": [],
            "pesan": "Operator Kala mengisi formulir SIHALAL di latar belakang dan hasilnya muncul bertahap dalam beberapa detik.",
        }

    monkeypatch.setattr(operator_ui, "serahkan", serahkan_palsu)
    monkeypatch.setattr(operator_ui, "tunggu", lambda pid, batas=60.0: True)

    pakai([
        # Giliran 1: Kala menjadwalkan produk & bahan, membaca info mode operator_ui dari tool, dan mengabarkan proses latar belakang
        lambda r: panggil("pilih_kategori", kategori="makanan"),
        lambda r: panggil(
            "daftarkan_akun_sihalal",
            nama_usaha="Bakso Maju",
            nama_penanggung_jawab="Budi",
            email="budi@example.com",
            no_hp="081234567892",
            nib="9120001234568",
            alamat="Jl. Melati 2",
            kab_kota="Bandung",
            provinsi="Jawa Barat",
            kode_pos="40135",
            skala="mikro",
        ),
        lambda r: panggil("buat_draf_pengajuan", jalur="self-declare"),
        lambda r: panggil("catat_produk", nama="Bakso Sapi", merek="Bakso Maju", rincian="Produk olahan daging"),
        lambda r: teks("Operator kami sedang menyiapkan draf di latar belakang: " + hasil_fungsi_terakhir(r)["pesan"]),
        # Giliran 2: Model nakal mencoba mengklaim formulir sudah berhasil tersimpan dan terpetakan sebelum divalidasi lihat_progres/pemeriksa
        lambda r: panggil(
            "tambah_bahan",
            nama="Kecap manis",
            jenis="bahan",
            produsen="Kecap Cap Layar",
            nomor_sertifikat="ID1230000100101",
            pemasok="Toko A",
            jenis_hewan="",
            foto_bukti="",
        ),
        lambda r: teks("Formulir SIHALAL sudah berhasil tersimpan dan terpetakan serta pengajuan sudah selesai."),
    ])

    u = "+628120"
    r1 = jalan(u, "tolong siapkan draf bakso")
    assert len(antrean_dijadwalkan) >= 1
    assert "latar belakang" in r1["balasan"].lower()

    r2 = jalan(u, "tambah kecap manis")
    assert "latar belakang" in r2["balasan"].lower()
    assert "pemeriksa" in r2["balasan"].lower()
    assert asyncio.run(A.lihat_state(u)).get("penyelarasan_orkestrator") == 1


def test_kala_tidak_menyatakan_pengajuan_selesai_jika_pemeriksa_melaporkan_selisih():
    from kawal_agent import sinkron as sk

    pakai([
        # Giliran 1: siapkan draf, produk, dan 2 bahan
        lambda r: panggil("pilih_kategori", kategori="makanan"),
        lambda r: panggil(
            "daftarkan_akun_sihalal",
            nama_usaha="Warung Bakso Sari",
            nama_penanggung_jawab="Sari",
            email="sari@example.com",
            no_hp="081234567893",
            nib="9120001234569",
            alamat="Jl. Kenanga 3",
            kab_kota="Bandung",
            provinsi="Jawa Barat",
            kode_pos="40135",
            skala="mikro",
        ),
        lambda r: panggil("buat_draf_pengajuan", jalur="self-declare"),
        lambda r: panggil("catat_produk", nama="Bakso Sapi", merek="Bakso Sari", rincian="Produk olahan daging"),
        lambda r: panggil(
            "tambah_bahan",
            nama="Kecap manis",
            jenis="bahan",
            produsen="Kecap Cap Layar",
            nomor_sertifikat="ID1230000100101",
            pemasok="Toko A",
            jenis_hewan="",
            foto_bukti="",
        ),
        lambda r: panggil(
            "tambah_bahan",
            nama="Tepung tapioka",
            jenis="bahan",
            produsen="",
            nomor_sertifikat="",
            pemasok="Pasar",
            jenis_hewan="",
            foto_bukti="",
        ),
        lambda r: teks("Produk dan bahan sudah dicatat."),
        # Giliran 2: periksa_pengajuan mendeteksi selisih dari pemeriksa, namun model mencoba mengklaim pengajuan sudah selesai
        lambda r: panggil("periksa_pengajuan"),
        lambda r: teks("Semua data sudah lengkap dan pengajuan sudah selesai serta siap dikirim."),
        # Giliran 3: lihat_progres juga menyalurkan selisih_pemeriksa ke konteks Kala
        lambda r: panggil("lihat_progres"),
        lambda r: teks("Catatan pemeriksa: " + "; ".join(hasil_fungsi_terakhir(r)["selisih_pemeriksa"])),
    ])

    u = "+628121"
    jalan(u, "daftar bakso")
    pid = asyncio.run(A.lihat_state(u))["pengajuan_id"]

    # Buat selisih nyata di SIHALAL: hapus Tepung tapioka dari daftarBahan
    with sm._kunci:
        p = sm._cari(pid)
        p["bahan"]["daftarBahan"] = [
            b for b in p["bahan"]["daftarBahan"] if sk._norm(b["nama"]) != "tepung tapioka"
        ]

    r2 = jalan(u, "apakah sudah selesai?")
    assert "belum selesai" in r2["balasan"].lower()
    assert "Tepung tapioka" in r2["balasan"]
    assert asyncio.run(A.lihat_state(u)).get("penyelarasan_orkestrator") == 1

    r3 = jalan(u, "lihat progresnya")
    assert "Tepung tapioka" in r3["balasan"]


def test_kala_menjaga_gerbang_persetujuan_ya_tidak_untuk_rph_dan_gelatin():
    pakai([
        # Giliran 1: tambah bahan kritis daging sapi dengan RPH belum terdaftar -> ditahan gerbang konfirmasi
        lambda r: panggil("pilih_kategori", kategori="makanan"),
        lambda r: panggil(
            "daftarkan_akun_sihalal",
            nama_usaha="Bakso Amanah",
            nama_penanggung_jawab="Hasan",
            email="hasan@example.com",
            no_hp="081234567894",
            nib="9120001234570",
            alamat="Jl. Dahlia 4",
            kab_kota="Bandung",
            provinsi="Jawa Barat",
            kode_pos="40135",
            skala="mikro",
        ),
        lambda r: panggil("buat_draf_pengajuan", jalur="self-declare"),
        lambda r: panggil(
            "tambah_bahan",
            nama="Daging sapi",
            jenis="bahan",
            produsen="",
            nomor_sertifikat="",
            pemasok="Lapak Pasar Tanpa Sertifikat",
            jenis_hewan="sapi",
            foto_bukti="",
        ),
        lambda r: teks("Daging sapi dari lapak tersebut belum memiliki sertifikat RPH halal. Tetap masukkan? Balas YA atau TIDAK."),
        # Giliran 2: pengguna membalas TIDAK -> bahan tidak dimasukkan ke SIHALAL
        lambda r: panggil("lihat_progres"),
        lambda r: teks("Keputusan: " + str((hasil_fungsi_terakhir(r)["keputusan_terakhir"] or {}).get("keputusan"))),
    ])

    u = "+628122"
    r1 = jalan(u, "tambah daging sapi")
    assert "YA atau TIDAK" in r1["balasan"]
    pid = asyncio.run(A.lihat_state(u))["pengajuan_id"]
    assert sm._cari(pid)["bahan"]["daftarBahan"] == []

    r2 = jalan(u, "tidak")
    assert "ditolak" in r2["balasan"]
    assert sm._cari(pid)["bahan"]["daftarBahan"] == []

