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
    monkeypatch.setenv("GEMINI_API_KEY", "kunci-palsu")
    monkeypatch.setattr(T, "GENERATED_DIR", tmp_path)
    sm.muat_seed()
    sm._akun.clear()
    yield


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
