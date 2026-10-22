"""Mock SIHALAL: penyimpanan pengajuan di memori server dan endpoint /api/sihalal.

Bentuk data mengikuti kontrak frontend/src/api/types.ts. Data awal dibaca dari
fixture frontend (frontend/src/mocks/fixtures) supaya mode mock dan mode http sama.
Agen menulis lewat fungsi isi_sihalal_* di bawah; tombol Kirim hanya lewat endpoint
yang dipanggil dari klik pengguna di web (human gate).
"""
import copy
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Body, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

WIB = timezone(timedelta(hours=7))
# Urutan: env var -> salinan lokal backend/fixtures (dipakai di container, build context = backend/)
# -> fixture frontend (dev lokal dari monorepo).
_BACKEND_DIR = Path(__file__).resolve().parent
_LOCAL_FIXTURES = _BACKEND_DIR / "fixtures"
_FRONTEND_FIXTURES = _BACKEND_DIR.parent / "frontend" / "src" / "mocks" / "fixtures"

_DEFAULT_FIXTURES_DIR = _LOCAL_FIXTURES if (_LOCAL_FIXTURES / "pelaku-usaha.json").exists() else _FRONTEND_FIXTURES
FIXTURES_DIR = Path(os.getenv("SIHALAL_FIXTURES_DIR", str(_DEFAULT_FIXTURES_DIR)))

BAGIAN = ("data", "komitmen", "bahan", "produk", "proses", "pemetaan", "pemantauan")
BAGIAN_LIST = {"produk", "pemetaan"}

NAMA_BAGIAN = {
    "data": "data pengajuan",
    "komitmen": "komitmen dan tanggung jawab",
    "bahan": "daftar bahan",
    "produk": "daftar produk",
    "proses": "proses produksi",
    "pemetaan": "pemetaan produk dan pabrik",
    "pemantauan": "pemantauan dan evaluasi",
}

LABEL_TAB = {
    "data": "Data Pengajuan",
    "komitmen": "Komitmen dan Tanggung Jawab",
    "bahan": "Bahan",
    "proses": "Proses",
    "produk": "Produk",
    "pemantauan": "Pemantauan dan Evaluasi",
}

_kunci = threading.RLock()
_pelaku_usaha: dict = {}
_pengajuan: list[dict] = []
_nomor_berikutnya = 143


def _sekarang() -> str:
    return datetime.now(WIB).isoformat(timespec="seconds")


def _waktu(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _id(awalan: str) -> str:
    return f"{awalan}-{int(time.time() * 1000)}"


def muat_seed() -> None:
    """Kembalikan data ke isi fixture (dipakai saat start dan reset demo)."""
    global _pelaku_usaha, _pengajuan, _nomor_berikutnya
    pelaku_file = FIXTURES_DIR / "pelaku-usaha.json"
    pengajuan_file = FIXTURES_DIR / "pengajuan.json"

    # Fallback aman jika path FIXTURES_DIR tidak memuat file
    if not pelaku_file.exists() or not pengajuan_file.exists():
        if (_LOCAL_FIXTURES / "pelaku-usaha.json").exists() and (_LOCAL_FIXTURES / "pengajuan.json").exists():
            pelaku_file = _LOCAL_FIXTURES / "pelaku-usaha.json"
            pengajuan_file = _LOCAL_FIXTURES / "pengajuan.json"
        elif (_FRONTEND_FIXTURES / "pelaku-usaha.json").exists() and (_FRONTEND_FIXTURES / "pengajuan.json").exists():
            pelaku_file = _FRONTEND_FIXTURES / "pelaku-usaha.json"
            pengajuan_file = _FRONTEND_FIXTURES / "pengajuan.json"

    with open(pelaku_file, encoding="utf-8") as f:
        _pelaku_usaha = json.load(f)
    with open(pengajuan_file, encoding="utf-8") as f:
        _pengajuan = json.load(f)
    _nomor_berikutnya = 143


muat_seed()


def _cari(pengajuan_id: str) -> dict:
    for p in _pengajuan:
        if p["id"] == pengajuan_id:
            return p
    raise HTTPException(404, "Pengajuan tidak ditemukan. Kembali ke daftar pengajuan lalu pilih lagi.")


def _bisa_diubah(p: dict) -> bool:
    return p["status"] in ("draf", "dikembalikan")


def _catat(p: dict, pelaku: str, aksi: str, bagian: str | None = None, ref: str | None = None) -> None:
    entri = {"id": _id("au"), "waktu": _sekarang(), "pelaku": pelaku, "aksi": aksi}
    if bagian:
        entri["bagian"] = bagian
    if ref:
        entri["ref"] = ref
    p["audit"].append(entri)
    p["diperbarui"] = entri["waktu"]


# ---------- Kelengkapan (aturan sama dengan frontend/src/lib/kelengkapan.ts) ----------


def _skor(cek: list[bool]) -> dict:
    return {"done": sum(cek), "total": len(cek)}


def hitung_kelengkapan(p: dict) -> dict[str, dict]:
    data, komitmen, bahan, produk = p["data"], p["komitmen"], p["bahan"], p["produk"]
    proses, pemetaan, pemantauan = p["proses"], p["pemetaan"], p["pemantauan"]
    bahan_ids = [b["id"] for b in bahan["daftarBahan"]]

    def semua_tercatat(daftar: list[dict]) -> bool:
        return bool(bahan_ids) and all(any(x["bahanId"] == i for x in daftar) for i in bahan_ids)

    return {
        "data": _skor([
            data["nomorSurat"] != "",
            data["tanggalSurat"] != "",
            data["jenisProduk"] != "",
            data["merek"] != "",
            data["jenisPendaftaran"] == "mandiri" or bool(data.get("kodeFasilitasi")),
            len(data["pabrikIds"]) > 0,
            len(data["penyeliaIds"]) > 0,
        ]),
        "komitmen": _skor([
            komitmen["kebijakanHalal"] is not None,
            komitmen["pengertianHalalHaram"] is not None,
            komitmen["praktikSjph"] is not None,
            len(komitmen["anggota"]) > 0,
        ]),
        "bahan": _skor([
            len(bahan["daftarBahan"]) > 0,
            len(produk) > 0,
            len(produk) > 0 and all(len(x["bahanIds"]) > 0 for x in produk),
            semua_tercatat(bahan["catatanPembelian"]),
            semua_tercatat(bahan["pemeriksaan"]),
        ]),
        "proses": _skor([
            proses["pernyataanBebasBabi"] is not None,
            len(proses["layout"]) > 0,
            len(proses["penyimpanan"]) > 0,
            len(proses["alurProses"]) > 0,
            len(proses["hasilProduksi"]) > 0,
            len(proses["distribusi"]) > 0,
        ]),
        "produk": _skor([len(produk) > 0 and all(any(m["produkId"] == x["id"] for m in pemetaan) for x in produk)]),
        "pemantauan": _skor([len(pemantauan["tandaTangan"]) > 0]),
    }


def _ringkas(p: dict) -> dict:
    k = hitung_kelengkapan(p)
    return {
        "id": p["id"],
        "nomorDaftar": p["nomorDaftar"],
        "jalur": p["jalur"],
        "jenisLayanan": p["jenisLayanan"],
        "status": p["status"],
        "namaUsaha": p["namaUsaha"],
        "jenisProduk": p["data"]["jenisProduk"],
        "jumlahProduk": len(p["produk"]),
        "dibuat": p["dibuat"],
        "diperbarui": p["diperbarui"],
        "kelengkapan": {
            "done": sum(s["done"] for s in k.values()),
            "total": sum(s["total"] for s in k.values()),
        },
    }


# ---------- Operasi inti (dipakai endpoint dan agen) ----------


def buat_draf(jalur: str, jenis_layanan: str, pelaku: str = "pengguna", ref: str | None = None) -> dict:
    waktu = _sekarang()
    baru = {
        "id": _id("pj"),
        "nomorDaftar": None,
        "jalur": jalur,
        "jenisLayanan": jenis_layanan,
        "status": "draf",
        "namaUsaha": _pelaku_usaha["namaUsaha"],
        "dibuat": waktu,
        "diperbarui": waktu,
        "data": {
            "nomorSurat": "",
            "tanggalSurat": "",
            "jenisProduk": "",
            "merek": "",
            "areaPemasaran": "kabupaten-kota",
            "jenisPendaftaran": "mandiri",
            "pabrikIds": [],
            "outletIds": [],
            "penyeliaIds": [],
            "sumberField": {},
        },
        "komitmen": {"kebijakanHalal": None, "pengertianHalalHaram": None, "praktikSjph": None, "anggota": []},
        "bahan": {"daftarBahan": [], "catatanPembelian": [], "pemeriksaan": []},
        "produk": [],
        "proses": {
            "pernyataanBebasBabi": None,
            "layout": [],
            "penyimpanan": [],
            "alurProses": [],
            "hasilProduksi": [],
            "distribusi": [],
        },
        "pemetaan": [],
        "pemantauan": {"dokumenLain": [], "tandaTangan": []},
        "riwayat": [{"status": "draf", "waktu": waktu}],
        "audit": [],
    }
    nama_jalur = "Self Declare" if jalur == "self-declare" else "Reguler"
    _catat(baru, pelaku, f"Membuat draf pengajuan {nama_jalur}", ref=ref)
    _pengajuan.append(baru)
    return baru


def ubah_bagian(
    pengajuan_id: str,
    bagian: str,
    isi: Any,
    pelaku: str = "pengguna",
    aksi: str | None = None,
    ref: str | None = None,
) -> dict:
    """Ganti seluruh isi satu bagian pengajuan lalu catat di audit."""
    if bagian not in BAGIAN:
        raise HTTPException(404, f"Bagian {bagian} tidak dikenal.")
    if not isinstance(isi, list if bagian in BAGIAN_LIST else dict):
        raise HTTPException(422, f"Isi bagian {NAMA_BAGIAN[bagian]} tidak sesuai format. Muat ulang halaman lalu coba lagi.")
    p = _cari(pengajuan_id)
    if not _bisa_diubah(p):
        raise HTTPException(409, "Pengajuan sudah dikirim sehingga tidak bisa diubah. Tunggu hasil verifikasi.")
    p[bagian] = copy.deepcopy(isi)
    _catat(p, pelaku, aksi or f"Mengubah {NAMA_BAGIAN[bagian]}", bagian=bagian, ref=ref)
    return p


# ---------- Akun pelaku usaha (pendaftaran lewat agen) ----------

_akun: dict[str, dict] = {}  # username -> {"password", "email"}


def _slug_username(nama_usaha: str) -> str:
    dasar = re.sub(r"[^a-z0-9]+", ".", nama_usaha.lower()).strip(".")
    return dasar or "pelaku.usaha"


def daftarkan_akun(
    nama_usaha: str,
    nama_pj: str,
    email: str,
    no_hp: str,
    nib: str,
    alamat: str,
    kab_kota: str,
    provinsi: str,
    kode_pos: str,
    skala: str,
) -> dict:
    """Buat akun pelaku usaha tiruan dan ganti profil pelaku usaha aktif (mock satu penyewa).

    Pabrik, outlet, dan penyelia halal diisi dari data penanggung jawab dan alamat usaha supaya
    pengajuan bisa langsung memilihnya. Nomor KTP penyelia sengaja dikosongkan (tidak disimpan di MVP).
    Mengembalikan username dan password sementara; password hanya ditampilkan sekali.
    """
    global _pelaku_usaha
    with _kunci:
        username = _slug_username(nama_usaha)
        if username in _akun and _akun[username]["email"] != email:
            username = f"{username}.{secrets.token_hex(2)}"
        password = secrets.token_urlsafe(6)
        _akun[username] = {"password": password, "email": email}
        tgl = datetime.now(WIB).date().isoformat()
        alamat_usaha = {"alamat": alamat, "provinsi": provinsi, "kabKota": kab_kota, "kodePos": kode_pos}
        _pelaku_usaha = {
            "id": _id("pu"),
            "namaUsaha": nama_usaha,
            "nib": nib,
            "skala": skala,
            **alamat_usaha,
            "penanggungJawab": {"nama": nama_pj, "noHp": no_hp, "email": email},
            "aspekLegal": [{"id": _id("al"), "jenis": "NIB", "nomor": nib, "tanggal": tgl, "instansiPenerbit": "OSS (BKPM)"}]
            if nib
            else [],
            "pabrik": [{"id": _id("pb"), "nama": f"Dapur {nama_usaha}", **alamat_usaha, "status": "milik-sendiri"}],
            "outlet": [{"id": _id("ot"), "nama": nama_usaha, **alamat_usaha}],
            "penyeliaHalal": [{"id": _id("py"), "nama": nama_pj, "noKtp": "", "agama": "Islam"}],
        }
        return {"username": username, "password": password, "pelaku_usaha": copy.deepcopy(_pelaku_usaha)}


def cek_masuk(pengguna: str, password: str) -> bool:
    id_ = pengguna.strip().lower()
    for username, a in _akun.items():
        if id_ in (username, a["email"].lower()) and password == a["password"]:
            return True
    return False


def pelaku_usaha_aktif() -> dict:
    with _kunci:
        return copy.deepcopy(_pelaku_usaha)


# ---------- Endpoint ----------

router = APIRouter()


class MasukAkun(BaseModel):
    pengguna: str
    password: str


@router.post("/api/sihalal/akun/masuk")
def masuk_akun(body: MasukAkun):
    """Cek akun yang didaftarkan lewat agen. Akun demo bawaan tetap dicek di browser."""
    return {"berhasil": cek_masuk(body.pengguna, body.password)}


class BuatPengajuan(BaseModel):
    jalur: Literal["self-declare", "reguler"]
    jenisLayanan: Literal["baru", "pengembangan"]


@router.get("/api/sihalal/pelaku-usaha")
def get_pelaku_usaha():
    return _pelaku_usaha


@router.patch("/api/sihalal/pelaku-usaha")
def patch_pelaku_usaha(isi: dict = Body(...)):
    global _pelaku_usaha
    with _kunci:
        _pelaku_usaha = copy.deepcopy(isi)
        return _pelaku_usaha


@router.get("/api/sihalal/pengajuan")
def daftar_pengajuan():
    with _kunci:
        urut = sorted(_pengajuan, key=lambda p: _waktu(p["dibuat"]), reverse=True)
        return [_ringkas(p) for p in urut]


@router.post("/api/sihalal/pengajuan")
def post_pengajuan(body: BuatPengajuan):
    with _kunci:
        return buat_draf(body.jalur, body.jenisLayanan)


@router.get("/api/sihalal/pengajuan/{pengajuan_id}")
def get_pengajuan(pengajuan_id: str):
    with _kunci:
        return _cari(pengajuan_id)


@router.patch("/api/sihalal/pengajuan/{pengajuan_id}/{bagian}")
def patch_bagian(pengajuan_id: str, bagian: str, isi: Any = Body(...)):
    with _kunci:
        return ubah_bagian(pengajuan_id, bagian, isi)


def kirim_draf(pengajuan_id: str, pelaku: str = "pengguna", catatan: str = "Dikirim oleh pelaku usaha") -> dict:
    """Kirim pengajuan bila semua tab lengkap. Dipanggil endpoint kirim dan tool agen (setelah konfirmasi)."""
    global _nomor_berikutnya
    p = _cari(pengajuan_id)
    if not _bisa_diubah(p):
        raise HTTPException(409, "Pengajuan ini sudah dikirim.")
    kurang = [LABEL_TAB[t] for t, s in hitung_kelengkapan(p).items() if s["done"] < s["total"]]
    if kurang:
        raise HTTPException(422, f"Pengajuan belum lengkap di tab {', '.join(kurang)}. Lengkapi isian lalu kirim lagi.")
    if not p["nomorDaftar"]:
        p["nomorDaftar"] = f"SH2026-1-{_nomor_berikutnya:06d}"
        _nomor_berikutnya += 1
    p["status"] = "terkirim"
    p["riwayat"].append({"status": "terkirim", "waktu": _sekarang(), "catatan": catatan})
    _catat(p, pelaku, "Mengirim pengajuan")
    return p


@router.post("/api/sihalal/pengajuan/{pengajuan_id}/kirim")
def kirim_pengajuan(pengajuan_id: str):
    with _kunci:
        return kirim_draf(pengajuan_id)


@router.get("/api/sihalal/pengajuan/{pengajuan_id}/dokumen/{jenis}")
def unduh_dokumen(pengajuan_id: str, jenis: Literal["surat-permohonan", "sjph"]):
    with _kunci:
        p = copy.deepcopy(_cari(pengajuan_id))
        pu = copy.deepcopy(_pelaku_usaha)
    html = _surat_permohonan(p, pu) if jenis == "surat-permohonan" else _manual_sjph(p, pu)
    nama = f"{jenis}-{p['nomorDaftar'] or p['id']}.html"
    return HTMLResponse(html, headers={"Content-Disposition": f'attachment; filename="{nama}"'})


@router.post("/api/demo/reset", status_code=204)
def reset_demo():
    with _kunci:
        muat_seed()
    return Response(status_code=204)


# ---------- Dokumen (HTML sederhana, bisa dicetak ke PDF dari browser) ----------

_GAYA = (
    "<style>body{font-family:sans-serif;max-width:720px;margin:32px auto;line-height:1.5;color:#1f1a24}"
    "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:6px;text-align:left}"
    "h1{font-size:20px}h2{font-size:16px;margin-top:24px}</style>"
)


def _surat_permohonan(p: dict, pu: dict) -> str:
    pj, d = pu["penanggungJawab"], p["data"]
    produk = "".join(f"<li>{escape(x['nama'])}</li>" for x in p["produk"]) or "<li>-</li>"
    return f"""<!doctype html><html lang="id"><meta charset="utf-8"><title>Surat Permohonan</title>{_GAYA}
<p>Nomor: {escape(d['nomorSurat'] or '-')}<br>Tanggal: {escape(d['tanggalSurat'] or '-')}</p>
<p>Hal: Permohonan Sertifikat Halal dengan pernyataan pelaku usaha</p>
<p>Yth. Kepala BPJPH<br>di Jakarta</p>
<table>
<tr><th>Nama</th><td>{escape(pj['nama'])}</td></tr>
<tr><th>Jabatan</th><td>Penanggung jawab usaha</td></tr>
<tr><th>Nomor kontak</th><td>{escape(pj['noHp'])}</td></tr>
<tr><th>Nama usaha</th><td>{escape(pu['namaUsaha'])}</td></tr>
<tr><th>NIB</th><td>{escape(pu['nib'])}</td></tr>
<tr><th>Alamat usaha</th><td>{escape(pu['alamat'])}, {escape(pu['kabKota'])}</td></tr>
</table>
<p>Dengan ini kami mengajukan permohonan sertifikat halal untuk produk berikut:</p><ul>{produk}</ul>
<p>Bersama surat ini kami lampirkan formulir pendaftaran, salinan izin usaha, surat penetapan penyelia halal,
daftar produk dan bahan, proses pengolahan produk, dan manual Sistem Jaminan Produk Halal.</p>
<p>Hormat kami,<br><br><br>{escape(pj['nama'])}</p>
<p style="color:#888;font-size:12px">Dokumen tiruan untuk demo KawalHalal, bukan dokumen resmi SIHALAL.</p></html>"""


def _manual_sjph(p: dict, pu: dict) -> str:
    bahan = "".join(
        f"<tr><td>{escape(b['nama'])}</td><td>{escape(b.get('produsen') or '-')}</td><td>{escape(b.get('noSertifikat') or '-')}</td></tr>"
        for b in p["bahan"]["daftarBahan"]
    )
    alur = "".join(
        f"<h3>{escape(a['judul'])}</h3><ol>{''.join(f'<li>{escape(x)}</li>' for x in a['langkah'])}</ol>"
        for a in p["proses"]["alurProses"]
    )
    anggota = "".join(
        f"<tr><td>{escape(a['nama'])}</td><td>{escape(a['jabatan'])}</td><td>{escape(a['posisi'])}</td></tr>"
        for a in p["komitmen"]["anggota"]
    )
    return f"""<!doctype html><html lang="id"><meta charset="utf-8"><title>Manual SJPH</title>{_GAYA}
<h1>Manual Sistem Jaminan Produk Halal</h1>
<p>{escape(pu['namaUsaha'])} Â· NIB {escape(pu['nib'])}</p>
<h2>1. Komitmen dan tanggung jawab</h2><table><tr><th>Nama</th><th>Jabatan</th><th>Posisi</th></tr>{anggota}</table>
<h2>2. Bahan</h2><table><tr><th>Nama bahan</th><th>Produsen</th><th>No. sertifikat halal</th></tr>{bahan}</table>
<h2>3. Proses produk halal</h2>{alur or '<p>-</p>'}
<p style="color:#888;font-size:12px">Dokumen tiruan untuk demo KawalHalal, bukan dokumen resmi SIHALAL.</p></html>"""


# ---------- Tool agen KawalHalal ----------
# Dipanggil agen setelah pengguna mengonfirmasi data di WhatsApp (human gate 1).
# Setiap isian diberi sumber oleh "kawalhalal" supaya web menampilkan penanda asal data.
# Agen tidak punya tool untuk mengirim pengajuan.


def _sumber_agen(ref_pesan: str, keyakinan: float, catatan: str) -> dict:
    s = {"oleh": "kawalhalal", "waktu": _sekarang(), "keyakinan": round(max(0.0, min(1.0, keyakinan)), 2)}
    if ref_pesan:
        s["ref"] = ref_pesan
    if catatan:
        s["catatan"] = catatan
    return s


def _hasil_tool(p: dict, pesan: str) -> dict:
    r = _ringkas(p)
    return {"pengajuan_id": p["id"], "pesan": pesan, "kelengkapan": r["kelengkapan"]}


def isi_sihalal_buat_draf(jalur: str = "self-declare", jenis_layanan: str = "baru", ref_pesan: str = "") -> dict:
    """Buat draf pengajuan sertifikasi halal baru di SIHALAL (mock) untuk pelaku usaha.

    Args:
        jalur: "self-declare" untuk usaha mikro/kecil, atau "reguler".
        jenis_layanan: "baru" atau "pengembangan".
        ref_pesan: Id pesan WhatsApp yang memicu, contoh "wa-msg-01".

    Returns:
        dict berisi pengajuan_id draf baru dan kelengkapannya.
    """
    if jalur not in ("self-declare", "reguler") or jenis_layanan not in ("baru", "pengembangan"):
        return {"error": "jalur harus self-declare/reguler dan jenis_layanan harus baru/pengembangan."}
    with _kunci:
        p = buat_draf(jalur, jenis_layanan, pelaku="kawalhalal", ref=ref_pesan or None)
        return _hasil_tool(p, "Draf dibuat.")


def isi_sihalal_data(
    pengajuan_id: str, field: str, nilai: str, ref_pesan: str = "", keyakinan: float = 0.9, catatan: str = ""
) -> dict:
    """Isi satu field Data Pengajuan, misalnya merek atau jenis produk.

    Args:
        pengajuan_id: Id pengajuan, contoh "pj-1".
        field: Salah satu dari nomorSurat, tanggalSurat, jenisProduk, merek, areaPemasaran,
            jenisPendaftaran, kodeFasilitasi, pendampingPph.
        nilai: Nilai yang diisikan.
        ref_pesan: Id pesan WhatsApp asal data.
        keyakinan: Keyakinan ekstraksi 0 sampai 1.
        catatan: Penjelasan singkat asal data, contoh "Dari nama usaha di chat".

    Returns:
        dict berisi pesan dan kelengkapan terbaru.
    """
    boleh = {"nomorSurat", "tanggalSurat", "jenisProduk", "merek", "areaPemasaran", "jenisPendaftaran", "kodeFasilitasi", "pendampingPph"}
    if field not in boleh:
        return {"error": f"Field {field} tidak bisa diisi agen."}
    with _kunci:
        try:
            p = _cari(pengajuan_id)
            data = copy.deepcopy(p["data"])
            data[field] = nilai
            data["sumberField"][field] = _sumber_agen(ref_pesan, keyakinan, catatan)
            ubah_bagian(pengajuan_id, "data", data, pelaku="kawalhalal", aksi=f"Mengisi {field} dari WhatsApp", ref=ref_pesan or None)
        except HTTPException as e:
            return {"error": e.detail}
        return _hasil_tool(p, f"{field} terisi.")


def isi_sihalal_tambah_bahan(
    pengajuan_id: str,
    nama: str,
    jenis: str = "bahan",
    produsen: str = "",
    nomor_sertifikat: str = "",
    foto_bukti: str = "",
    ref_pesan: str = "",
    keyakinan: float = 0.9,
    catatan: str = "",
) -> dict:
    """Tambahkan bahan atau kemasan hasil membaca foto label/nota ke tab Bahan.

    Args:
        pengajuan_id: Id pengajuan.
        nama: Nama bahan, contoh "Tepung tapioka".
        jenis: "bahan", "kemasan", atau "cleaning-agent".
        produsen: Nama produsen atau merek di kemasan.
        nomor_sertifikat: Nomor sertifikat halal di kemasan, kosongkan bila tidak terbaca.
        foto_bukti: Nama berkas foto asal, contoh "label-tapioka.jpg".
        ref_pesan: Id pesan WhatsApp asal foto.
        keyakinan: Keyakinan pembacaan 0 sampai 1.
        catatan: Penjelasan singkat, contoh "Dibaca dari foto label".

    Returns:
        dict berisi pesan dan kelengkapan terbaru.
    """
    if jenis not in ("bahan", "kemasan", "cleaning-agent"):
        jenis = "bahan"
    if nomor_sertifikat and keyakinan >= 0.75:
        bukti, alasan = "ada", "Nomor sertifikat terbaca dari foto." if foto_bukti else "Nomor sertifikat disebut pengguna."
    elif nomor_sertifikat:
        bukti, alasan = "tidak-jelas", "Nomor sertifikat kurang terbaca. Kirim ulang foto label yang lebih jelas."
    elif jenis == "kemasan":
        bukti, alasan = "ada", "Kemasan, foto terunggah." if foto_bukti else "Kemasan dicatat dari chat."
    else:
        bukti, alasan = "kurang", "Nomor sertifikat belum diketahui. Kirim foto kemasan yang menampilkan logo halal."
    item = {
        "id": _id("b"),
        "tipe": "bersertifikat" if nomor_sertifikat else "tidak-bersertifikat",
        "jenis": jenis,
        "nama": nama,
        "bukti": bukti,
        "alasanBukti": alasan,
        "konfirmasi": "perlu-konfirmasi",
        "sumber": _sumber_agen(ref_pesan, keyakinan, catatan),
    }
    if produsen:
        item["produsen"] = produsen
    if nomor_sertifikat:
        item["noSertifikat"] = nomor_sertifikat.upper()
    if foto_bukti:
        item["fotoSumber"] = {"nama": foto_bukti}
    with _kunci:
        try:
            p = _cari(pengajuan_id)
            isi = copy.deepcopy(p["bahan"])
            isi["daftarBahan"].append(item)
            ubah_bagian(pengajuan_id, "bahan", isi, pelaku="kawalhalal", aksi=f"Menambahkan bahan {nama}", ref=ref_pesan or None)
        except HTTPException as e:
            return {"error": e.detail}
        return _hasil_tool(p, f"Bahan {nama} ditambahkan dengan bukti {bukti}.")


def isi_sihalal_tambah_produk(
    pengajuan_id: str,
    nama: str,
    klasifikasi: str = "Makanan",
    rincian: str = "",
    ref_pesan: str = "",
    keyakinan: float = 0.9,
    catatan: str = "",
) -> dict:
    """Tambahkan produk yang ingin disertifikasi, beserta semua bahan yang sudah tercatat.

    Args:
        pengajuan_id: Id pengajuan.
        nama: Nama produk, contoh "Bakso Sapi Halus".
        klasifikasi: "Makanan" atau "Minuman".
        rincian: Rincian produk, contoh "Produk olahan daging".
        ref_pesan: Id pesan WhatsApp asal.
        keyakinan: Keyakinan 0 sampai 1.
        catatan: Penjelasan singkat, contoh "Dari daftar menu di chat".

    Returns:
        dict berisi pesan dan kelengkapan terbaru.
    """
    with _kunci:
        try:
            p = _cari(pengajuan_id)
            produk = copy.deepcopy(p["produk"])
            produk.append({
                "id": _id("pr"),
                "klasifikasi": klasifikasi,
                "rincian": rincian or "Makanan siap saji",
                "nama": nama,
                "merek": p["data"]["merek"],
                "bahanIds": [b["id"] for b in p["bahan"]["daftarBahan"]],
                "sumber": _sumber_agen(ref_pesan, keyakinan, catatan),
            })
            ubah_bagian(pengajuan_id, "produk", produk, pelaku="kawalhalal", aksi=f"Menambahkan produk {nama}", ref=ref_pesan or None)
        except HTTPException as e:
            return {"error": e.detail}
        return _hasil_tool(p, f"Produk {nama} ditambahkan.")


TOOLS_SIHALAL = [isi_sihalal_buat_draf, isi_sihalal_data, isi_sihalal_tambah_bahan, isi_sihalal_tambah_produk]


@router.post("/api/demo/agen/{nama_tool}", include_in_schema=False)
def jalankan_tool_agen(nama_tool: str, args: dict = Body(default={})):
    """Jalankan tool agen lewat HTTP untuk latihan demo dan pengujian, tanpa lewat Gemini."""
    from kawal_agent.tools import TOOL_REGISTRY

    daftar_tool = {**{f.__name__: f for f in TOOLS_SIHALAL}, **TOOL_REGISTRY}
    fn = daftar_tool.get(nama_tool)
    if fn is None:
        raise HTTPException(404, f"Tool {nama_tool} tidak ada. Pilihan: {', '.join(daftar_tool.keys())}.")
    try:
        return fn(**(args or {}))
    except TypeError as e:
        raise HTTPException(422, f"Argumen tool tidak sesuai: {e}")
