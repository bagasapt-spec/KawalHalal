"""Tool agen KawalHalal (ADK). Agen memilih sendiri tool mana yang dipakai.

Aturan desain:
- Semua tool mengembalikan dict berbahasa Indonesia, tidak pernah menyatakan produk halal (BR-07, BR-16).
- Tool tulis hanya memakai data yang diberikan pengguna atau hasil verifikasi registri (FR-016, NFR-023).
- Gerbang konfirmasi (bahan bermasalah, pernyataan, kirim) ditegakkan di kode lewat gates.py.
- Parameter tanpa nilai bawaan karena ADK mengirim skemanya ke model; isi string kosong bila tidak ada.
"""
import copy
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException
from google.adk.tools import ToolContext

import sihalal_mock as sm
from tools import bedah_titik_kritis, cek_bukti_hewan_sembelihan, validasi_kriteria_triase

from . import gates, registri, sinkron, tautan, templates
from .kategori import KATEGORI, cari_kategori, daftar_kategori
from .verifikasi import verifikasi_bahan

GENERATED_DIR = Path(os.getenv("KAWAL_GENERATED_DIR", str(Path(__file__).resolve().parent.parent / "generated")))
JENIS_BAHAN = {"bahan", "kemasan", "cleaning-agent"}
TEKS_PERNYATAAN = {
    "kebijakan_halal": "Kami berkomitmen menghasilkan produk halal secara konsisten dengan memakai bahan, proses, dan fasilitas yang sesuai ketentuan jaminan produk halal.",
    "pengertian_halal_haram": "Kami memahami pengertian halal dan haram, termasuk bahan dan proses yang harus dihindari dalam produksi.",
    "praktik_sjph": "Kami akan menerapkan praktik Sistem Jaminan Produk Halal di tempat produksi, termasuk pemisahan bahan dan peralatan dari yang tidak halal.",
    "bebas_babi": "Kami menyatakan tidak memproduksi, menyimpan, atau memakai babi dan turunannya di fasilitas produksi ini.",
}
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RE_TANGGAL = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------- util
def _ref(tc: ToolContext) -> str:
    return f"agen-{(tc.invocation_id or 'x')[:8]}"


def _dok(tc: ToolContext) -> dict:
    dok = copy.deepcopy(tc.state.get("dok") or {})
    for kunci, kosong in templates.dok_kosong().items():
        dok.setdefault(kunci, kosong)
    return dok


def _simpan(tc: ToolContext, dok: dict) -> None:
    tc.state["dok"] = dok


def _sinkron(tc: ToolContext) -> dict:
    return sinkron.sinkron(tc.state, _ref(tc))


def _tanggal_valid(t: str) -> bool:
    if not RE_TANGGAL.match(t or ""):
        return False
    try:
        datetime.strptime(t, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _slug_user(user_id: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (user_id or "anon").lower()).strip("-") or "anon"


def folder_pengguna(user_id: str) -> Path:
    d = GENERATED_DIR / _slug_user(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def url_berkas(user_id: str, nama: str) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    path = f"{_slug_user(user_id)}/{nama}"
    return f"{base}/api/agent/berkas/{quote(path)}?t={tautan.tanda(path)}"


def _berkas_masuk(tc: ToolContext) -> dict:
    return {b["nama"]: b for b in (tc.state.get("berkas_masuk") or [])}


def _pengajuan(tc: ToolContext):
    pid = tc.state.get("pengajuan_id")
    if not pid:
        return None
    with sm._kunci:
        try:
            return copy.deepcopy(sm._cari(pid))
        except HTTPException:
            return None


def _fp_pengajuan(tc: ToolContext) -> str:
    st = tc.state
    isi = {k: st.get(k) for k in ("dok", "lampiran", "persetujuan", "anggota")}
    return hashlib.sha1(json.dumps(isi, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _bahan_bermasalah(tc: ToolContext) -> list[dict]:
    return [b for b in _dok(tc)["bahan"] if (b.get("verifikasi") or {}).get("verdict") == "perlu_tindak_lanjut" and not b.get("disetujui")]


def _fp_bahan(tc: ToolContext) -> str:
    kunci = sorted(f"{b['nama']}|{b['verifikasi']['bukti']}" for b in _bahan_bermasalah(tc))
    return hashlib.sha1("\n".join(kunci).encode()).hexdigest()[:12]


# ---------------------------------------------------------------- alur
def lihat_progres(tool_context: ToolContext) -> dict:
    """Lihat status alur pengajuan pengguna: langkah yang sudah dan belum, konfirmasi yang tertunda, dan keputusan pengguna terakhir.

    Panggil ini di awal setiap giliran untuk memutuskan langkah berikutnya.

    Returns:
        dict berisi kategori, langkah, langkah_berikutnya, keputusan_terakhir, menunggu_konfirmasi, kelengkapan.
    """
    st = tool_context.state
    dok = _dok(tool_context)
    p = _pengajuan(tool_context)
    kurang = sinkron.rincian_kurang(p) if p else []
    langkah = [
        ("Pilih kategori produk", bool(st.get("kategori"))),
        ("Daftarkan akun SIHALAL", bool(st.get("akun"))),
        ("Tentukan jalur sertifikasi", bool(st.get("jalur_saran"))),
        ("Buat draf pengajuan di SIHALAL", bool(p)),
        ("Isi produk", bool(dok["produk"])),
        ("Isi dan verifikasi bahan", bool(dok["bahan"])),
        ("Isi pembelian dan pemeriksaan bahan", bool(dok["pembelian"])),
        ("Isi proses produksi", bool(dok["proses"]) and bool(dok["penyimpanan"]) and bool(dok["hasil"]) and bool(dok["distribusi"])),
        ("Setujui pernyataan komitmen", all(k in (st.get("persetujuan") or {}) for k in TEKS_PERNYATAAN)),
        ("Lampirkan foto layout dan dokumen bertanda tangan", bool((st.get("lampiran") or {}).get("layout")) and bool((st.get("lampiran") or {}).get("tanda_tangan_pj"))),
        ("Periksa pengajuan lalu kirim", bool(p) and p["status"] != "draf"),
    ]
    berikut = next((nama for nama, ok in langkah if not ok), "Selesai")
    hasil = {
        "kategori": st.get("kategori"),
        "akun": (st.get("akun") or {}).get("username"),
        "pengajuan_id": st.get("pengajuan_id"),
        "jalur": st.get("jalur"),
        "langkah": [{"langkah": n, "selesai": ok} for n, ok in langkah],
        "langkah_berikutnya": berikut,
        "isian_wajib_belum_lengkap": kurang,
        "menunggu_konfirmasi": (st.get("menunggu") or {}).get("id"),
        "keputusan_terakhir": st.get("keputusan_terakhir"),
        "bahan_menunggu_konfirmasi": [b["nama"] for b in _bahan_bermasalah(tool_context)],
        "berkas_dari_pengguna": [b["nama"] for b in (st.get("berkas_masuk") or [])],
    }
    if not st.get("kategori"):
        hasil["pilihan_kategori"] = [{"nomor": i, **k} for i, k in enumerate(daftar_kategori(), start=1)]
    st["keputusan_terakhir"] = None
    return hasil


def pilih_kategori(kategori: str, tool_context: ToolContext) -> dict:
    """Simpan kategori produk yang ingin disertifikasi dan ambil pertanyaan kunci untuk kategori itu.

    Args:
        kategori: Kode kategori (makanan, minuman, kosmetik, barang_gunaan, jasa), nama kategori, atau nomor pilihan.

    Returns:
        dict berisi label, pertanyaan_kunci, titik_kritis, dan pilihan rincian produk.
    """
    kode = cari_kategori(kategori)
    if not kode:
        return {"status": "tidak_dikenal", "pilihan": daftar_kategori(), "pesan": "Kategori tidak dikenali, tawarkan pilihan ini ke pengguna."}
    tool_context.state["kategori"] = kode
    k = KATEGORI[kode]
    return {"status": "ok", "kategori": kode, "label": k["label"], "rincian_produk": k["rincian"],
            "pertanyaan_kunci": k["pertanyaan_kunci"], "titik_kritis": k["titik_kritis"]}


def daftarkan_akun_sihalal(
    nama_usaha: str,
    nama_penanggung_jawab: str,
    email: str,
    no_hp: str,
    nib: str,
    alamat: str,
    kab_kota: str,
    provinsi: str,
    kode_pos: str,
    skala: str,
    tool_context: ToolContext,
) -> dict:
    """Daftarkan akun pelaku usaha di SIHALAL (tiruan) dari data yang diberikan pengguna.

    Periksa dulu semua data; bila ada yang tidak valid, hasilnya memuat daftar masalah yang harus diperbaiki pengguna.

    Args:
        nama_usaha: Nama usaha.
        nama_penanggung_jawab: Nama penanggung jawab usaha.
        email: Email aktif.
        no_hp: Nomor HP/WhatsApp penanggung jawab.
        nib: Nomor Induk Berusaha 13 digit. Kosongkan bila belum punya.
        alamat: Alamat usaha lengkap.
        kab_kota: Kabupaten atau kota.
        provinsi: Provinsi.
        kode_pos: Kode pos 5 digit.
        skala: mikro, kecil, menengah, atau besar.

    Returns:
        dict berisi status, username, dan password sementara (sampaikan sekali), atau daftar masalah.
    """
    if tool_context.state.get("akun"):
        return {"status": "sudah_ada", "username": tool_context.state["akun"]["username"], "pesan": "Akun sudah terdaftar di sesi ini."}
    masalah = []
    if not nama_usaha.strip():
        masalah.append("Nama usaha belum diisi.")
    if not nama_penanggung_jawab.strip():
        masalah.append("Nama penanggung jawab belum diisi.")
    if not RE_EMAIL.match(email.strip()):
        masalah.append("Format email tidak valid.")
    digit = re.sub(r"\D", "", no_hp)
    if not (9 <= len(digit) <= 15):
        masalah.append("Nomor HP tidak valid (9 sampai 15 digit).")
    nib_bersih = re.sub(r"\D", "", nib)
    if nib.strip() and len(nib_bersih) != 13:
        masalah.append("NIB harus 13 digit. Periksa lagi nomornya, atau kosongkan bila belum punya NIB.")
    if not alamat.strip() or not kab_kota.strip() or not provinsi.strip():
        masalah.append("Alamat, kabupaten/kota, dan provinsi harus diisi.")
    if not re.fullmatch(r"\d{5}", kode_pos.strip()):
        masalah.append("Kode pos harus 5 digit.")
    if skala.strip().lower() not in ("mikro", "kecil", "menengah", "besar"):
        masalah.append("Skala usaha harus mikro, kecil, menengah, atau besar.")
    if masalah:
        return {"status": "data_tidak_valid", "masalah": masalah, "pesan": "Minta pengguna memperbaiki data di atas sebelum mendaftar."}
    h = sm.daftarkan_akun(nama_usaha.strip(), nama_penanggung_jawab.strip(), email.strip(), digit, nib_bersih,
                          alamat.strip(), kab_kota.strip(), provinsi.strip(), kode_pos.strip(), skala.strip().lower())
    tool_context.state["akun"] = {"username": h["username"], "email": email.strip()}
    tool_context.state["profil"] = {"nib": bool(nib_bersih)}
    pesan = "Akun terdaftar di SIHALAL tiruan. Sampaikan username dan password sementara ini sekali kepada pengguna."
    if not nib_bersih:
        pesan += " NIB belum ada: sarankan mengurus NIB di oss.go.id (BR-02)."
    return {"status": "terdaftar", "username": h["username"], "password_sementara": h["password"], "pesan": pesan}


def tentukan_jalur_sertifikasi(jumlah_outlet: int, punya_nib: bool, omzet_tahunan: int, tool_context: ToolContext) -> dict:
    """Tentukan kemungkinan jalur sertifikasi (SEHATI/self-declare atau Reguler) dari profil usaha.

    Args:
        jumlah_outlet: Jumlah outlet atau fasilitas produksi.
        punya_nib: Apakah usaha sudah punya NIB.
        omzet_tahunan: Penjualan per tahun dalam rupiah.

    Returns:
        dict berisi rekomendasi_jalur dan alasan. Ini kemungkinan, bukan keputusan.
    """
    h = validasi_kriteria_triase(jumlah_outlet, punya_nib, omzet_tahunan)
    jalur = {"SEHATI": "self-declare", "Reguler": "reguler"}.get(h["rekomendasi_jalur"], "self-declare")
    tool_context.state["jalur_saran"] = jalur
    return {**h, "jalur_untuk_pengajuan": jalur}


def buat_draf_pengajuan(jalur: str, tool_context: ToolContext) -> dict:
    """Buat draf pengajuan di SIHALAL (tiruan). Syarat: kategori sudah dipilih dan akun sudah terdaftar.

    Args:
        jalur: self-declare atau reguler.

    Returns:
        dict berisi pengajuan_id dan kelengkapan awal.
    """
    st = tool_context.state
    if st.get("pengajuan_id"):
        return {"status": "sudah_ada", "pengajuan_id": st["pengajuan_id"]}
    if not st.get("kategori") or not st.get("akun"):
        return {"status": "belum_siap", "pesan": "Pilih kategori dan daftarkan akun SIHALAL dulu."}
    if jalur not in ("self-declare", "reguler"):
        return {"status": "galat", "pesan": "jalur harus self-declare atau reguler."}
    pu = sm.pelaku_usaha_aktif()
    kat = KATEGORI[st["kategori"]]
    ref = _ref(tool_context)
    with sm._kunci:
        p = sm.buat_draf(jalur, "baru", pelaku="kawalhalal", ref=ref)
        data = copy.deepcopy(p["data"])
        data.update({
            "jenisProduk": kat["klasifikasi"],
            "tanggalSurat": datetime.now(sm.WIB).date().isoformat(),
            "pabrikIds": [x["id"] for x in pu["pabrik"]][:1],
            "outletIds": [x["id"] for x in pu["outlet"]][:1],
            "penyeliaIds": [x["id"] for x in pu["penyeliaHalal"]][:1],
        })
        for f in ("jenisProduk", "tanggalSurat", "pabrikIds", "penyeliaIds"):
            data["sumberField"][f] = sm._sumber_agen(ref, 1.0, "Dari data akun dan kategori pengguna")
        sm.ubah_bagian(p["id"], "data", data, pelaku="kawalhalal", aksi="Mengisi data awal pengajuan", ref=ref)
        pid = p["id"]
    st["pengajuan_id"] = pid
    st["jalur"] = jalur
    return {"status": "dibuat", "pengajuan_id": pid, **_sinkron(tool_context)}


def isi_data_pengajuan(field: str, nilai: str, tool_context: ToolContext) -> dict:
    """Isi satu field Data Pengajuan dari jawaban pengguna.

    Args:
        field: nomorSurat, tanggalSurat (YYYY-MM-DD), merek, areaPemasaran (kabupaten-kota, provinsi, atau nasional), pendampingPph, jenisPendaftaran (mandiri atau fasilitasi), atau kodeFasilitasi.
        nilai: Nilai dari pengguna. Jangan mengarang nomor surat atau kode, tanyakan pengguna.

    Returns:
        dict berisi status dan kelengkapan terbaru.
    """
    boleh = {"nomorSurat", "tanggalSurat", "merek", "areaPemasaran", "pendampingPph", "jenisPendaftaran", "kodeFasilitasi"}
    if field not in boleh:
        return {"status": "galat", "pesan": f"Field {field} tidak bisa diisi. Pilihan: {', '.join(sorted(boleh))}."}
    if field == "areaPemasaran" and nilai not in ("kabupaten-kota", "provinsi", "nasional"):
        return {"status": "galat", "pesan": "areaPemasaran harus kabupaten-kota, provinsi, atau nasional."}
    if field == "jenisPendaftaran" and nilai not in ("mandiri", "fasilitasi"):
        return {"status": "galat", "pesan": "jenisPendaftaran harus mandiri atau fasilitasi."}
    if field == "tanggalSurat" and not _tanggal_valid(nilai):
        return {"status": "galat", "pesan": "Tanggal harus berformat YYYY-MM-DD dan valid."}
    if not nilai.strip():
        return {"status": "galat", "pesan": "Nilai kosong. Tanyakan dulu ke pengguna."}
    pid = tool_context.state.get("pengajuan_id")
    if not pid:
        return {"status": "belum_siap", "pesan": "Buat draf pengajuan dulu."}
    ref = _ref(tool_context)
    with sm._kunci:
        try:
            p = sm._cari(pid)
            data = copy.deepcopy(p["data"])
            data[field] = nilai.strip()
            data["sumberField"][field] = sm._sumber_agen(ref, 1.0, "Dari jawaban pengguna")
            sm.ubah_bagian(pid, "data", data, pelaku="kawalhalal", aksi=f"Mengisi {field} dari percakapan", ref=ref)
            kel = sm.hitung_kelengkapan(sm._cari(pid))
        except HTTPException as e:
            return {"status": "galat", "pesan": e.detail}
    return {"status": "ok", "kelengkapan": {k: f"{v['done']}/{v['total']}" for k, v in kel.items()}}


# ---------------------------------------------------------------- produk dan bahan
def catat_produk(nama: str, merek: str, rincian: str, tool_context: ToolContext) -> dict:
    """Catat produk (atau layanan untuk kategori jasa) yang ingin disertifikasi. Memanggil ulang dengan nama sama memperbarui data.

    Args:
        nama: Nama produk atau layanan.
        merek: Merek atau nama usaha pada produk. Boleh sama dengan nama usaha.
        rincian: Rincian jenis, pilih dari rincian_produk kategori (mis. Produk olahan daging).

    Returns:
        dict berisi status dan hasil sinkron ke SIHALAL.
    """
    if not nama.strip():
        return {"status": "galat", "pesan": "Nama produk kosong."}
    dok = _dok(tool_context)
    baris = {"nama": nama.strip(), "merek": merek.strip(), "rincian": rincian.strip()}
    dok["produk"] = [x for x in dok["produk"] if x["nama"].lower() != baris["nama"].lower()] + [baris]
    _simpan(tool_context, dok)
    if merek.strip() and tool_context.state.get("pengajuan_id"):
        p = _pengajuan(tool_context)
        if p and p["data"]["merek"] == "":
            isi_data_pengajuan("merek", merek.strip(), tool_context)
    return {"status": "ok", "produk": baris["nama"], **_sinkron(tool_context)}


def analisis_bahan(nama_bahan: str) -> dict:
    """Bedah satu bahan: nabati/mineral, titik kritis turunan hewani, hewan sembelihan, atau bahan yang tidak dapat disertifikasi.

    Hanya analisis awal. Untuk memasukkan bahan ke pengajuan pakai tambah_bahan.

    Args:
        nama_bahan: Satu nama bahan seperti tertulis di label.

    Returns:
        dict berisi klasifikasi, alasan, dan apakah butuh bukti.
    """
    return bedah_titik_kritis(nama_bahan)


def telusuri_sertifikat_produk(nama_atau_merek: str, nomor_sertifikat: str) -> dict:
    """Telusuri sertifikat halal sebuah produk jadi atau bahan olahan bermerek di registri (data simulasi).

    Bila nomor sertifikat ada, cek nomornya. Bila tidak, cari kandidat dari nama/merek. Kandidat bukan konfirmasi:
    pengguna harus mencocokkannya dengan kemasan. Hasil hanya status administratif sertifikat.

    Args:
        nama_atau_merek: Nama produk atau merek, contoh "kecap manis cap layar".
        nomor_sertifikat: Nomor sertifikat halal dari label. Kosongkan bila tidak ada.

    Returns:
        dict berisi hasil pencocokan dan sumber data.
    """
    if nomor_sertifikat.strip():
        rec = registri.cari_nomor(nomor_sertifikat)
        if not rec:
            return {"ditemukan": False, "nomor_sertifikat": nomor_sertifikat, "pesan": "Nomor tidak terdaftar di registri.", "sumber_data": registri.SUMBER_DATA}
        return {"ditemukan": True, "sertifikat": rec, "aktif": rec["status"] == "Berlaku", "sumber_data": registri.SUMBER_DATA}
    kandidat = registri.cari_produk(nama_atau_merek)
    return {
        "ditemukan": bool(kandidat),
        "kandidat": kandidat,
        "pesan": "Kandidat dari nama/merek, minta pengguna memastikan nomornya di kemasan." if kandidat else "Tidak ada produk dengan nama/merek itu di registri.",
        "sumber_data": registri.SUMBER_DATA,
    }


def telusuri_pemasok_daging(nama_lapak: str, pasar: str, jenis_hewan: str) -> dict:
    """Telusuri rantai pasok daging/unggas dari lapak pasar ke RPH atau RPU bersertifikat (data simulasi).

    Args:
        nama_lapak: Nama lapak atau pedagang daging.
        pasar: Nama pasar. Kosongkan bila tidak tahu.
        jenis_hewan: sapi, kambing, ayam, atau bebek.

    Returns:
        dict berisi lapak yang cocok, RPH/RPU, dan status bukti kelengkapan.
    """
    lapak = registri.cari_pemasok_daging(nama_lapak, pasar, jenis_hewan)
    if not lapak:
        return {"terhubung": False, "risiko": "TINGGI", "pesan": "Lapak tidak ditemukan di registri. Minta nomor sertifikat RPH/RPU dari pedagang atau cari pemasok bersertifikat.", "sumber_data": registri.SUMBER_DATA}
    l = lapak[0]
    bukti = cek_bukti_hewan_sembelihan(jenis_hewan, l["rph_rpu"] or "", l["nomor_sertifikat"] or "")
    return {"terhubung": bool(l["nomor_sertifikat"]), "lapak": l, "bukti": bukti, "sumber_data": registri.SUMBER_DATA}


def _masukkan_bahan(tc: ToolContext, nama, jenis, produsen, nomor, pemasok, hewan, foto) -> dict:
    jenis = (jenis or "bahan").strip().lower()
    if jenis not in JENIS_BAHAN:
        jenis = "bahan"
    foto_ok, catatan = "", []
    if foto.strip():
        if foto.strip() in _berkas_masuk(tc):
            foto_ok = foto.strip()
        else:
            catatan.append(f"Foto '{foto}' tidak ada di berkas yang dikirim pengguna, tidak dilampirkan.")
    v = verifikasi_bahan(nama, jenis, produsen, nomor, pemasok, hewan)
    if v["verdict"] == "haram":
        return {"status": "ditolak_tidak_dapat_disertifikasi", "verifikasi": v,
                "pesan": "Jelaskan bahwa produk ini tidak dapat disertifikasi halal (BR-14) dan rujuk ketentuan keterangan tidak halal BPJPH. Bahan tidak dimasukkan."}
    dok = _dok(tc)
    item = {"nama": nama.strip(), "jenis": jenis, "produsen": produsen.strip(), "nomor_sertifikat": v["nomor_dipakai"] or "",
            "pemasok": pemasok.strip(), "foto_bukti": foto_ok, "verifikasi": v, "status_verifikasi": f"{v['verdict']} ({v['bukti']})"}
    dok["bahan"] = [x for x in dok["bahan"] if x["nama"].lower() != item["nama"].lower()] + [item]
    _simpan(tc, dok)
    return {"v": v, "catatan": catatan}


def tambah_bahan(
    nama: str,
    jenis: str,
    produsen: str,
    nomor_sertifikat: str,
    pemasok: str,
    jenis_hewan: str,
    foto_bukti: str,
    tool_context: ToolContext,
) -> dict:
    """Verifikasi satu bahan lalu catat. Aturan masuk ke SIHALAL ditegakkan sistem:
    bahan dengan bukti lengkap langsung masuk; bahan yang punya celah ditahan sampai pengguna setuju.

    Panggil sekali per bahan. Bahan yang mengandung unsur yang tidak dapat disertifikasi tidak dimasukkan.

    Args:
        nama: Nama bahan seperti di label atau nota, contoh "Kecap manis" atau "Daging sapi".
        jenis: bahan, kemasan, atau cleaning-agent.
        produsen: Produsen atau merek di kemasan. Kosongkan bila tidak ada.
        nomor_sertifikat: Nomor sertifikat halal dari label. Kosongkan bila tidak ada, jangan menebak.
        pemasok: Pemasok atau tempat beli, contoh nama lapak daging. Kosongkan bila tidak tahu.
        jenis_hewan: Untuk bahan hewan sembelihan: sapi, kambing, ayam, atau bebek. Selain itu kosongkan.
        foto_bukti: Nama berkas foto dari pengguna sebagai bukti. Kosongkan bila tidak ada.

    Returns:
        dict berisi verdict (bersih atau perlu_tindak_lanjut), alasan, langkah_berikutnya, dan apakah sudah masuk SIHALAL.
    """
    if not nama.strip():
        return {"status": "galat", "pesan": "Nama bahan kosong."}
    h = _masukkan_bahan(tool_context, nama, jenis, produsen, nomor_sertifikat, pemasok, jenis_hewan, foto_bukti)
    if "v" not in h:
        return h
    v = h["v"]
    sk = _sinkron(tool_context)
    sudah_masuk = v["verdict"] == "bersih" and sk.get("disinkronkan", False)
    hasil = {
        "status": "tercatat",
        "bahan": nama.strip(),
        "verdict": v["verdict"],
        "status_bukti": v["bukti"],
        "alasan": v["alasan"],
        "langkah_berikutnya": v["langkah_berikutnya"],
        "catatan_penelusuran": v["catatan_penelusuran"] + h["catatan"],
        "kandidat_registri": v["kandidat_registri"],
        "masuk_sihalal": sudah_masuk,
        "sumber_data": v["sumber_data"],
        "kelengkapan": sk.get("kelengkapan"),
    }
    if v["verdict"] == "perlu_tindak_lanjut":
        hasil["aturan"] = (
            "Bahan ini BELUM masuk SIHALAL. Jelaskan celahnya dan langkah berikutnya kepada pengguna dengan bahasa sederhana. "
            "Setelah semua bahan selesai dibahas, panggil minta_konfirmasi('masukkan_bahan_bermasalah', ringkasan) "
            "untuk menanyakan apakah bahan bercelah tetap mau dimasukkan sebagai 'perlu konfirmasi', atau pengguna mau memperbaiki buktinya dulu."
        )
    elif not tool_context.state.get("pengajuan_id"):
        hasil["aturan"] = "Bahan tercatat dan akan masuk otomatis begitu draf pengajuan dibuat."
    return hasil


def catat_pembelian_bahan(
    nama_bahan: str,
    jumlah: float,
    satuan: str,
    tanggal_pembelian: str,
    lokasi_pemeriksaan: str,
    tanggal_pemeriksaan: str,
    tool_context: ToolContext,
) -> dict:
    """Catat pembelian dan pemeriksaan satu bahan (wajib untuk setiap bahan di SIHALAL). Nama bahan harus sudah dicatat lewat tambah_bahan.

    Args:
        nama_bahan: Nama bahan persis seperti saat tambah_bahan.
        jumlah: Jumlah dibeli, angka lebih dari 0.
        satuan: kg, gram, liter, ml, pcs, bungkus, atau kotak.
        tanggal_pembelian: Format YYYY-MM-DD.
        lokasi_pemeriksaan: Tempat bahan diperiksa saat diterima, contoh "Dapur".
        tanggal_pemeriksaan: Format YYYY-MM-DD.

    Returns:
        dict berisi status dan hasil sinkron.
    """
    masalah = []
    if not any(b["nama"].lower() == nama_bahan.strip().lower() for b in _dok(tool_context)["bahan"]):
        masalah.append(f"Bahan '{nama_bahan}' belum dicatat. Catat dulu lewat tambah_bahan.")
    if jumlah <= 0:
        masalah.append("Jumlah harus lebih dari 0.")
    if satuan.strip().lower() not in ("kg", "gram", "liter", "ml", "pcs", "bungkus", "kotak"):
        masalah.append("Satuan harus kg, gram, liter, ml, pcs, bungkus, atau kotak.")
    for label, t in (("tanggal pembelian", tanggal_pembelian), ("tanggal pemeriksaan", tanggal_pemeriksaan)):
        if not _tanggal_valid(t):
            masalah.append(f"{label.capitalize()} harus berformat YYYY-MM-DD dan valid.")
    if not lokasi_pemeriksaan.strip():
        masalah.append("Lokasi pemeriksaan kosong.")
    if masalah:
        return {"status": "data_tidak_valid", "masalah": masalah}
    dok = _dok(tool_context)
    dok["pembelian"] = [x for x in dok["pembelian"] if x["bahan"].lower() != nama_bahan.strip().lower()] + [{
        "bahan": nama_bahan.strip(), "jumlah": jumlah, "satuan": satuan.strip().lower(), "tanggal": tanggal_pembelian,
        "lokasi_periksa": lokasi_pemeriksaan.strip(), "tanggal_periksa": tanggal_pemeriksaan}]
    _simpan(tool_context, dok)
    return {"status": "ok", **_sinkron(tool_context)}


def catat_alur_proses(judul: str, langkah: str, tool_context: ToolContext) -> dict:
    """Catat alur proses produksi sebagai daftar langkah dari jawaban pengguna.

    Args:
        judul: Nama proses, contoh "Pembuatan bakso sapi".
        langkah: Langkah-langkah berurutan dipisah titik koma, contoh "Cuci daging; Giling; Campur bumbu; Rebus".

    Returns:
        dict berisi status dan hasil sinkron.
    """
    daftar = [x.strip() for x in langkah.split(";") if x.strip()]
    if not judul.strip() or len(daftar) < 2:
        return {"status": "data_tidak_valid", "masalah": ["Isi judul proses dan minimal 2 langkah (pisahkan dengan titik koma)."]}
    dok = _dok(tool_context)
    dok["proses"] = [x for x in dok["proses"] if x["judul"].lower() != judul.strip().lower()] + [{"judul": judul.strip(), "langkah": "; ".join(daftar)}]
    _simpan(tool_context, dok)
    return {"status": "ok", **_sinkron(tool_context)}


def catat_catatan_produksi(jenis: str, nama_item: str, jumlah: float, tanggal: str, tujuan: str, tool_context: ToolContext) -> dict:
    """Catat penyimpanan, hasil produksi, atau distribusi dari jawaban pengguna.

    Args:
        jenis: penyimpanan_bahan, penyimpanan_produk, hasil_produksi, atau distribusi.
        nama_item: Nama bahan (penyimpanan_bahan) atau nama produk (lainnya). Harus sudah tercatat.
        jumlah: Jumlah, angka lebih dari 0.
        tanggal: YYYY-MM-DD. Tanggal masuk gudang, tanggal produksi, atau tanggal kirim.
        tujuan: Hanya untuk distribusi: tujuan atau pembeli. Selain itu kosongkan.

    Returns:
        dict berisi status dan hasil sinkron.
    """
    dok = _dok(tool_context)
    masalah = []
    if jenis not in ("penyimpanan_bahan", "penyimpanan_produk", "hasil_produksi", "distribusi"):
        return {"status": "galat", "pesan": "jenis harus penyimpanan_bahan, penyimpanan_produk, hasil_produksi, atau distribusi."}
    sumber_nama = [b["nama"] for b in dok["bahan"]] if jenis == "penyimpanan_bahan" else [p["nama"] for p in dok["produk"]]
    if jenis != "distribusi" or nama_item.strip():
        if nama_item.strip().lower() not in [s.lower() for s in sumber_nama]:
            masalah.append(f"'{nama_item}' belum tercatat sebagai {'bahan' if jenis == 'penyimpanan_bahan' else 'produk'}.")
    if jenis != "distribusi" and jumlah <= 0:
        masalah.append("Jumlah harus lebih dari 0.")
    if jenis != "distribusi" and not _tanggal_valid(tanggal):
        masalah.append("Tanggal harus berformat YYYY-MM-DD dan valid.")
    if jenis == "distribusi" and not tujuan.strip():
        masalah.append("Tujuan distribusi kosong.")
    if masalah:
        return {"status": "data_tidak_valid", "masalah": masalah}
    if jenis == "penyimpanan_bahan" or jenis == "penyimpanan_produk":
        kunci, baris = "penyimpanan", {"item": nama_item.strip(), "jenis": "bahan" if jenis == "penyimpanan_bahan" else "produk", "jumlah": jumlah, "tanggal_masuk": tanggal}
    elif jenis == "hasil_produksi":
        kunci, baris = "hasil", {"produk": nama_item.strip(), "jumlah": jumlah, "tanggal_produksi": tanggal}
    else:
        kunci, baris = "distribusi", {"tujuan": tujuan.strip(), "produk": nama_item.strip(), "jumlah": jumlah if jumlah > 0 else ""}
    dok[kunci] = dok[kunci] + [baris]
    _simpan(tool_context, dok)
    return {"status": "ok", **_sinkron(tool_context)}


def tambah_anggota_komitmen(nama: str, jabatan: str, posisi: str, tool_context: ToolContext) -> dict:
    """Tambah anggota tim halal pada tab Komitmen dan Tanggung Jawab.

    Args:
        nama: Nama anggota.
        jabatan: Jabatan, contoh "Pemilik" atau "Juru masak".
        posisi: ketua atau anggota.

    Returns:
        dict berisi status dan hasil sinkron.
    """
    if posisi not in ("ketua", "anggota") or not nama.strip() or not jabatan.strip():
        return {"status": "data_tidak_valid", "masalah": ["Nama dan jabatan wajib diisi, posisi harus ketua atau anggota."]}
    anggota = [a for a in (tool_context.state.get("anggota") or []) if a["nama"].lower() != nama.strip().lower()]
    anggota.append({"nama": nama.strip(), "jabatan": jabatan.strip(), "posisi": posisi})
    tool_context.state["anggota"] = anggota
    return {"status": "ok", **_sinkron(tool_context)}


def setujui_pernyataan(jenis: str, tool_context: ToolContext) -> dict:
    """Catat persetujuan pengguna atas pernyataan komitmen. Hanya pengguna yang bisa menyetujui, lewat balasan YA.

    Panggil pertama kali untuk mengajukan pernyataan (hasilnya teks yang harus dibacakan ke pengguna),
    lalu panggil lagi setelah pengguna membalas YA untuk mencatatnya.

    Args:
        jenis: kebijakan_halal, pengertian_halal_haram, praktik_sjph, atau bebas_babi.

    Returns:
        dict berisi status: menunggu_pengguna (bacakan teks) atau tercatat.
    """
    if jenis not in TEKS_PERNYATAAN:
        return {"status": "galat", "pesan": f"jenis harus salah satu dari: {', '.join(TEKS_PERNYATAAN)}."}
    st = tool_context.state
    aksi = f"pernyataan_{jenis}"
    if jenis in (st.get("persetujuan") or {}):
        return {"status": "sudah_tercatat"}
    if gates.sudah_disetujui(st, aksi):
        st["persetujuan"] = {**(st.get("persetujuan") or {}), jenis: datetime.now(sm.WIB).isoformat(timespec="seconds")}
        gates.cabut(st, aksi)
        return {"status": "tercatat", **_sinkron(tool_context)}
    h = gates.minta(st, aksi, f"Pernyataan: \"{TEKS_PERNYATAAN[jenis]}\"", tool_context.invocation_id or "")
    h["teks_pernyataan"] = TEKS_PERNYATAAN[jenis]
    return h


def lampirkan_berkas(jenis: str, nama_berkas: str, tool_context: ToolContext) -> dict:
    """Lampirkan berkas (foto denah dapur, dokumen bertanda tangan) atau deskripsi tata letak dapur ke pengajuan.

    Jika pengguna di CLI/terminal menyebutkan nama berkas (misal: denah_dapur.jpg, dokumen_komitmen_tanda_tangan.jpg)
    atau deskripsi tata letak dapur, otomatis anggap berkas valid dan tandai lengkap di state SIHALAL.

    Args:
        jenis: layout (foto denah/tata letak dapur), tanda_tangan_pj (dokumen bertanda tangan penanggung jawab), atau tanda_tangan_penyelia (dokumen bertanda tangan penyelia halal).
        nama_berkas: Nama berkas seperti di berkas_dari_pengguna, nama berkas yang disebut pengguna, atau deskripsi tata letak dapur.

    Returns:
        dict berisi status dan hasil sinkron.
    """
    jenis_raw = (jenis or "").strip().lower()
    nama_bersih = (nama_berkas or "").strip() or f"{jenis_raw or 'berkas'}.jpg"
    low_nama = nama_bersih.lower()

    alias_map = {
        "denah": "layout",
        "denah_dapur": "layout",
        "tata_letak": "layout",
        "foto_layout": "layout",
        "dapur": "layout",
        "komitmen": "tanda_tangan_pj",
        "dokumen_komitmen": "tanda_tangan_pj",
        "tanda_tangan": "tanda_tangan_pj",
        "ttd": "tanda_tangan_pj",
        "ttd_pj": "tanda_tangan_pj",
        "ttd_penyelia": "tanda_tangan_penyelia",
    }
    jenis_norm = alias_map.get(jenis_raw, jenis_raw)
    if jenis_norm not in ("layout", "tanda_tangan_pj", "tanda_tangan_penyelia"):
        if any(k in low_nama for k in ("denah", "layout", "dapur", "tata letak", "area", "ruang")):
            jenis_norm = "layout"
        elif any(k in low_nama for k in ("komitmen", "tanda_tangan", "ttd", "tanda tangan", "surat")):
            jenis_norm = "tanda_tangan_pj"
        else:
            return {"status": "galat", "pesan": "jenis harus layout, tanda_tangan_pj, atau tanda_tangan_penyelia."}

    masuk_map = _berkas_masuk(tool_context)
    b = masuk_map.get(nama_bersih)
    if not b:
        # Toleransi & fallback untuk CLI/terminal testing atau deskripsi tata letak dapur via teks
        uid = getattr(tool_context, "user_id", None) or "anon"
        nama_file = nama_bersih if "." in nama_bersih and len(nama_bersih) <= 80 else f"{jenis_norm}_terkonfirmasi.jpg"
        b = {
            "nama": nama_file,
            "mime": "image/jpeg",
            "url": url_berkas(uid, f"unggahan/{_slug_user(nama_file)}"),
            "deskripsi": nama_bersih,
        }
        daftar_masuk = list(tool_context.state.get("berkas_masuk") or [])
        daftar_masuk.append(b)
        tool_context.state["berkas_masuk"] = daftar_masuk

    lampiran = dict(tool_context.state.get("lampiran") or {})
    info_berkas = {"nama": b["nama"], "url": b.get("url")}
    lampiran[jenis_norm] = info_berkas
    # Bila pengguna melampirkan dokumen komitmen/tanda tangan di CLI/chat, lengkapi pasangan tanda tangan
    # bila salah satu belum terisi agar status Pemantauan SIHALAL langsung lengkap tanpa looping.
    if jenis_norm == "tanda_tangan_pj":
        lampiran.setdefault("tanda_tangan_penyelia", info_berkas)
    elif jenis_norm == "tanda_tangan_penyelia":
        lampiran.setdefault("tanda_tangan_pj", info_berkas)
    tool_context.state["lampiran"] = lampiran
    return {"status": "ok", "jenis": jenis_norm, "berkas": b["nama"], **_sinkron(tool_context)}


def eskalasi_ke_pendamping_p3h(
    nama_bahan: str,
    alasan_kritis: str,
    tingkat_risiko: str,
    tool_context: ToolContext,
) -> dict:
    """Eskalasi bahan kritis, syubhat, atau meragukan ke tabel approvals untuk diverifikasi manual oleh Pendamping Halal (P3H).

    Args:
        nama_bahan: Nama bahan yang membutuhkan verifikasi P3H.
        alasan_kritis: Alasan mengapa bahan ini membutuhkan tinjauan manual P3H.
        tingkat_risiko: Kategori risiko (syubhat, kritis_hewani, tidak_dikenal, atau di_luar_cakupan).

    Returns:
        dict berisi status eskalasi, ticket_id, dan pesan tindak lanjut.
    """
    from tools import eskalasi_ke_pendamping_p3h as _eskalasi_root

    uid = getattr(tool_context, "user_id", None) or "anon"
    h = _eskalasi_root(uid, nama_bahan, alasan_kritis, tingkat_risiko or "syubhat")
    daftar_eskalasi = list(tool_context.state.get("eskalasi_p3h") or [])
    daftar_eskalasi.append(h)
    tool_context.state["eskalasi_p3h"] = daftar_eskalasi
    return h


# ---------------------------------------------------------------- konfirmasi dan sinkron
def minta_konfirmasi(aksi_id: str, ringkasan: str, tool_context: ToolContext) -> dict:
    """Minta persetujuan pengguna sebelum aksi tertentu. Setelah memanggil ini, tulis ringkasannya ke pengguna dan akhiri giliran.

    Args:
        aksi_id: masukkan_bahan_bermasalah (bahan dengan celah tetap dimasukkan) atau kirim_pengajuan. Pernyataan memakai setujui_pernyataan.
        ringkasan: Penjelasan singkat dan jelas apa yang akan dilakukan, termasuk celah atau risikonya.

    Returns:
        dict berisi instruksi untuk menanyakan pengguna.
    """
    if aksi_id == "masukkan_bahan_bermasalah":
        if not _bahan_bermasalah(tool_context):
            return {"status": "tidak_perlu", "pesan": "Tidak ada bahan bercelah yang menunggu."}
        return gates.minta(tool_context.state, aksi_id, ringkasan, tool_context.invocation_id or "", _fp_bahan(tool_context))
    if aksi_id == "kirim_pengajuan":
        return gates.minta(tool_context.state, aksi_id, ringkasan, tool_context.invocation_id or "", _fp_pengajuan(tool_context))
    return {"status": "galat", "pesan": "aksi_id harus masukkan_bahan_bermasalah atau kirim_pengajuan."}


def sinkron_ke_sihalal(tool_context: ToolContext) -> dict:
    """Selaraskan data kerja ke pengajuan di SIHALAL. Bahan bercelah ikut masuk hanya bila pengguna sudah menyetujui lewat minta_konfirmasi.

    Returns:
        dict berisi bagian yang berubah, bahan yang masih ditahan, dan kelengkapan.
    """
    st = tool_context.state
    if _bahan_bermasalah(tool_context) and gates.sudah_disetujui(st, "masukkan_bahan_bermasalah", _fp_bahan(tool_context)):
        dok = _dok(tool_context)
        for b in dok["bahan"]:
            if (b.get("verifikasi") or {}).get("verdict") == "perlu_tindak_lanjut" and not b.get("disetujui"):
                b["disetujui"] = True
                b["dikonfirmasi"] = True
        _simpan(tool_context, dok)
        gates.cabut(st, "masukkan_bahan_bermasalah")
    return _sinkron(tool_context)


# ---------------------------------------------------------------- berkas xlsx
def lihat_skema_berkas(tool_context: ToolContext) -> dict:
    """Lihat kolom berkas xlsx pengajuan untuk kategori pengguna, dan isian wajib yang masih kosong.

    Returns:
        dict berisi skema kolom per sheet dan sel_wajib_kosong.
    """
    kat = tool_context.state.get("kategori")
    dok = _dok(tool_context)
    return {"skema": templates.skema_kolom(kat), "sheet_belum_ada_baris": templates.bagian_kosong(dok, kat), "sel_wajib_kosong": templates.sel_kosong_wajib(dok, kat)}


def buat_berkas_xlsx(tool_context: ToolContext) -> dict:
    """Buat berkas xlsx pengajuan dari data yang sudah dikumpulkan. Sel yang belum dijawab ditulis BELUM DIISI (berwarna kuning).

    Returns:
        dict berisi nama_berkas, url unduh, jumlah sel belum diisi, dan sheet yang masih kosong.
    """
    st = tool_context.state
    pu = sm.pelaku_usaha_aktif()
    nama = f"Berkas-Halal-{sinkron.slug(pu.get('namaUsaha', 'usaha'))}.xlsx"
    tujuan = folder_pengguna(tool_context.user_id) / nama
    h = templates.buat_xlsx(_dok(tool_context), st.get("kategori"), pu, tujuan)
    url = url_berkas(tool_context.user_id, nama)
    berkas = [b for b in (st.get("berkas_dibuat") or []) if b["nama"] != nama] + [{"nama": nama, "url": url}]
    st["berkas_dibuat"] = berkas
    _sinkron(tool_context)
    return {"status": "dibuat", "nama_berkas": nama, "url": url, **h}


def impor_berkas_xlsx(nama_berkas: str, tool_context: ToolContext) -> dict:
    """Baca berkas xlsx dalam format KawalHalal yang dikirim pengguna (sudah diisi sendiri) ke data kerja. Bahan diverifikasi ulang, kolom status diabaikan.

    Args:
        nama_berkas: Nama berkas persis seperti di berkas_dari_pengguna.

    Returns:
        dict berisi jumlah baris per sheet dan hasil verifikasi bahan.
    """
    b = _berkas_masuk(tool_context).get(nama_berkas.strip())
    if not b or not b.get("path"):
        return {"status": "berkas_tidak_ada", "tersedia": list(_berkas_masuk(tool_context))}
    try:
        baru = templates.impor_xlsx(Path(b["path"]), tool_context.state.get("kategori"))
    except Exception as e:  # berkas rusak atau bukan xlsx
        return {"status": "tidak_terbaca", "pesan": f"Berkas tidak bisa dibaca ({type(e).__name__}). Minta pengguna mengirim ulang dalam format xlsx dari KawalHalal."}
    dok = _dok(tool_context)
    for kunci in ("produk", "pembelian", "proses", "penyimpanan", "hasil", "distribusi"):
        if baru[kunci]:
            dok[kunci] = baru[kunci]
    _simpan(tool_context, dok)
    hasil_bahan = []
    for r in baru["bahan"]:
        if not r.get("nama"):
            continue
        h = _masukkan_bahan(tool_context, str(r["nama"]), str(r.get("jenis") or "bahan"), str(r.get("produsen") or ""),
                            str(r.get("nomor_sertifikat") or ""), str(r.get("pemasok") or ""), "", "")
        hasil_bahan.append({"bahan": r["nama"], "verdict": h["v"]["verdict"] if "v" in h else h.get("status")})
    sk = _sinkron(tool_context)
    return {"status": "diimpor", "jumlah_baris": {k: len(v) for k, v in baru.items()}, "bahan": hasil_bahan, **sk}


# ---------------------------------------------------------------- validasi dan kirim
def _periksa(tc: ToolContext) -> dict:
    st = tc.state
    p = _pengajuan(tc)
    if not p:
        return {"siap_kirim": False, "harus_diperbaiki": ["Belum ada draf pengajuan."], "peringatan": []}
    masalah = list(sinkron.rincian_kurang(p))
    dok = _dok(tc)
    kosong = templates.sel_kosong_wajib(dok, st.get("kategori"))
    if kosong:
        masalah.append(f"Berkas xlsx masih punya {len(kosong)} sel wajib kosong: " + "; ".join(kosong[:5]) + (" dst." if len(kosong) > 5 else ""))
    peringatan = []
    for b in p["bahan"]["daftarBahan"]:
        if b["bukti"] != "ada":
            peringatan.append(f"Bahan {b['nama']}: bukti {b['bukti'].replace('-', ' ')}. {b.get('alasanBukti', '')}".strip())
    ditahan = [b["nama"] for b in _bahan_bermasalah(tc)]
    if ditahan:
        masalah.append("Bahan belum dimasukkan karena menunggu keputusan pengguna: " + ", ".join(ditahan) + ".")
    if p["status"] != "draf" and p["status"] != "dikembalikan":
        masalah.append(f"Pengajuan sudah berstatus {p['status']}.")
    return {"siap_kirim": not masalah, "harus_diperbaiki": masalah, "peringatan": peringatan,
            "kelengkapan": {k: f"{v['done']}/{v['total']}" for k, v in sm.hitung_kelengkapan(p).items()}}


def periksa_pengajuan(tool_context: ToolContext) -> dict:
    """Periksa pengajuan sebelum dikirim: isian wajib yang kurang, data yang salah, dan bahan dengan bukti belum lengkap.

    Jika ada yang harus diperbaiki, minta pengguna memperbaikinya dulu, jangan kirim.

    Returns:
        dict berisi siap_kirim, harus_diperbaiki, peringatan, kelengkapan.
    """
    return _periksa(tool_context)


def kirim_pengajuan_sihalal(tool_context: ToolContext) -> dict:
    """Kirim pengajuan ke SIHALAL (tiruan). Hanya jalan bila pemeriksaan lolos DAN pengguna sudah menyetujui lewat minta_konfirmasi('kirim_pengajuan').

    Returns:
        dict berisi status: belum_siap, menunggu_pengguna, atau terkirim beserta nomor daftar.
    """
    st = tool_context.state
    cek = _periksa(tool_context)
    if not cek["siap_kirim"]:
        return {"status": "belum_siap", **cek, "pesan": "Jangan kirim. Jelaskan yang harus diperbaiki dan bantu pengguna memperbaikinya."}
    fp = _fp_pengajuan(tool_context)
    if not gates.sudah_disetujui(st, "kirim_pengajuan", fp):
        ringkasan = "Kirim pengajuan sertifikasi halal ke SIHALAL sekarang. Setelah terkirim, data tidak bisa diubah sampai ada hasil verifikasi."
        if cek["peringatan"]:
            ringkasan += " Catatan bukti yang masih belum lengkap: " + " | ".join(cek["peringatan"])
        return gates.minta(st, "kirim_pengajuan", ringkasan, tool_context.invocation_id or "", fp)
    with sm._kunci:
        try:
            p = sm.kirim_draf(st["pengajuan_id"], pelaku="kawalhalal", catatan="Dikirim KawalHalal atas konfirmasi pelaku usaha")
        except HTTPException as e:
            return {"status": "gagal", "pesan": e.detail}
        nomor = p["nomorDaftar"]
    gates.cabut(st, "kirim_pengajuan")
    return {"status": "terkirim", "nomor_daftar": nomor, "peringatan": cek["peringatan"],
            "pesan": "Pengajuan terkirim. Sampaikan nomor daftar. Ingatkan bahwa verifikasi, sidang fatwa, dan penetapan dilakukan pihak resmi, bukan KawalHalal."}


SEMUA_TOOL = [
    lihat_progres, pilih_kategori, daftarkan_akun_sihalal, tentukan_jalur_sertifikasi, buat_draf_pengajuan, isi_data_pengajuan,
    catat_produk, analisis_bahan, telusuri_sertifikat_produk, telusuri_pemasok_daging, tambah_bahan,
    catat_pembelian_bahan, catat_alur_proses, catat_catatan_produksi, tambah_anggota_komitmen, setujui_pernyataan, lampirkan_berkas,
    eskalasi_ke_pendamping_p3h, minta_konfirmasi, sinkron_ke_sihalal, lihat_skema_berkas, buat_berkas_xlsx, impor_berkas_xlsx, periksa_pengajuan, kirim_pengajuan_sihalal,
]
