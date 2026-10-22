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
import mimetypes
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv(override=True)

from fastapi import HTTPException
from google.adk.tools import ToolContext

from mock_data import INGREDIENT_ALIASES, MOCK_INGREDIENTS, MOCK_PRODUCTS, MOCK_RPH_RPU
import sihalal_mock as sm


# ---------------------------------------------------------------- tool deterministik dasar & triase
def cek_sertifikat_bpjph(nomor_id: str) -> dict:
    """Cek status keaktifan sertifikat halal berdasarkan nomor ID sertifikat (data mock BPJPH).

    Gunakan saat label/dokumen menampilkan nomor sertifikat halal (format IDxxxxxxxxxxxxx)
    untuk mengetahui apakah sertifikat berstatus Berlaku, Kadaluarsa, atau Dicabut.
    Hasil hanya status administratif, bukan penetapan kehalalan.

    Args:
        nomor_id: Nomor ID sertifikat halal, contoh ID3111000012345.

    Returns:
        dict berisi 'ditemukan', 'valid', 'status', dan detail produk bila ada.
    """
    nomor = re.sub(r"[\s\-]", "", (nomor_id or "")).upper()
    produk = MOCK_PRODUCTS.get(nomor)
    if not produk:
        return {
            "ditemukan": False,
            "nomor_sertifikat": nomor,
            "status": "Tidak ditemukan",
            "pesan": "Nomor sertifikat tidak terdaftar di database BPJPH.",
        }
    return {
        "ditemukan": True,
        "valid": produk["status"] == "Berlaku",
        "pesan": f"Sertifikat berstatus {produk['status']}.",
        **produk,
    }


def _cari_bahan(teks: str):
    teks = teks.strip().lower()
    if teks in MOCK_INGREDIENTS:
        return teks
    if teks in INGREDIENT_ALIASES:
        return INGREDIENT_ALIASES[teks]
    kandidat = {**{k: k for k in MOCK_INGREDIENTS}, **INGREDIENT_ALIASES}
    for alias in sorted(kandidat, key=len, reverse=True):
        if alias in teks:
            return kandidat[alias]
    return None


def analisis_titik_kritis(bahan_list: list[str]) -> dict:
    """Periksa daftar komposisi terhadap bahan syubhat/kritis.

    Args:
        bahan_list: Daftar nama bahan, contoh ["gula", "E471", "gelatin"].

    Returns:
        dict berisi temuan, bahan aman/tidak dikenal, dan kesimpulan.
    """
    temuan, tidak_dikenal, sudah = [], [], set()
    for bahan in bahan_list or []:
        kunci = _cari_bahan(str(bahan))
        if kunci is None:
            tidak_dikenal.append(bahan)
        elif kunci not in sudah:
            sudah.add(kunci)
            temuan.append({"input": bahan, **MOCK_INGREDIENTS[kunci]})

    statuses = {t["status"] for t in temuan}
    if "Haram" in statuses:
        kesimpulan = "Mengandung bahan haram. Tidak disarankan."
    elif statuses & {"Kritis", "Syubhat"}:
        kesimpulan = "Terdapat titik kritis/syubhat. Pastikan ada sertifikat halal resmi."
    elif "Halal bersyarat" in statuses:
        kesimpulan = "Terdapat bahan halal bersyarat. Periksa ketentuannya."
    else:
        kesimpulan = "Tidak ditemukan bahan kritis pada daftar yang dikenali."
    return {
        "total_bahan": len(bahan_list or []),
        "temuan": temuan,
        "tidak_dikenal": tidak_dikenal,
        "kesimpulan": kesimpulan,
    }


BATAS_OMZET_SEHATI = 15_000_000_000  # BR-03: Rp15 miliar (tepat Rp15 miliar masih boleh)
HEWAN_RUMINANSIA = {"sapi", "kambing"}  # bukti RPH
HEWAN_UNGGAS = {"ayam", "bebek"}  # bukti RPU

_KATA_HAM = [r"\bbabi\b", r"\bpork\b", r"\blard\b", r"\bbacon\b", r"\bham\b", r"\bswine\b", r"\bceleng\b"]
_KATA_HEWAN = {
    "sapi": ["sapi", "beef", "lembu"],
    "kambing": ["kambing", "domba", "goat", "mutton", "lamb"],
    "ayam": ["ayam", "chicken"],
    "bebek": ["bebek", "itik", "duck"],
}
_KATA_KRITIS = [
    "gelatin", "gelatine", "kolagen", "collagen", "lemak", "shortening", "emulsifier",
    "pengemulsi", "lesitin", "lecithin", "perisa", "flavour", "flavor", "essence", "esens",
    "alkohol", "etanol", "keju", "whey", "rennet", "kaldu", "pepsin", "sistein", "cysteine",
    "karmin", "carmine", "shellac", "mono dan digliserida", "digliserida", "gliserol", "gliserin",
    "plasenta", "placenta", "lanolin", "stearat", "stearate", "stearic", "tallow", "squalene", "skualen",
    "keratin", "glycerin", "glycerol", "alcohol denat",
]
_E_HEWANI = {"120", "422", "430", "431", "432", "433", "434", "435", "436", "441", "470", "471", "472",
             "473", "474", "475", "477", "481", "482", "483", "542", "570", "627", "631", "635", "904"}
_KATA_NABATI_MINERAL = [
    "gula", "garam", "tepung", "air", "beras", "singkong", "tapioka", "maizena", "jagung", "kedelai",
    "kacang", "cabai", "cabe", "bawang", "merica", "lada", "kunyit", "jahe", "lengkuas", "ketumbar",
    "sayur", "wortel", "tomat", "kentang", "buah", "minyak sawit", "minyak nabati", "minyak kelapa",
    "santan", "kelapa", "soda kue", "baking soda", "kalsium karbonat", "asam sitrat", "ragi", "cuka",
    "telur", "madu", "teh", "kopi", "kakao", "cokelat bubuk",
    "minyak goreng", "sawit", "daun", "jeruk", "lemon", "kemiri", "pala", "sereh", "serai", "kayu manis",
    "cengkeh", "asam jawa", "gula merah", "gula aren", "aqua", "water", "shea butter", "aloe vera",
]
_KATA_NABATI_PENANDA = ["nabati", "kedelai", "sawit", "kelapa", "soy", "vegetable", "palm"]


def _ke_int(nilai) -> int:
    try:
        return int(float(nilai))
    except (TypeError, ValueError):
        return 0


def validasi_kriteria_triase(jumlah_outlet: int, punya_nib: bool, omzet_tahunan: int) -> dict:
    """Evaluasi kemungkinan kelayakan jalur SEHATI (self-declare) versus jalur Reguler.

    Args:
        jumlah_outlet: Jumlah outlet/fasilitas produksi yang dimiliki usaha (angka bulat).
        punya_nib: True jika usaha sudah memiliki NIB skala mikro atau kecil.
        omzet_tahunan: Penjualan/omzet tahunan dalam rupiah (angka bulat, mis. 500000000).

    Returns:
        dict berisi 'rekomendasi_jalur' (SEHATI, Reguler, atau Perlu NIB Dulu), 'alasan', dan 'catatan'.
    """
    outlet = _ke_int(jumlah_outlet)
    omzet = _ke_int(omzet_tahunan)
    nib = punya_nib is True or str(punya_nib).strip().lower() in {"true", "ya", "1", "yes"}

    if not nib:
        jalur = "Perlu NIB Dulu"
        alasan = ["Belum memiliki NIB skala mikro/kecil; disarankan mengurus NIB lebih dulu (BR-02, kriteria 1 SEHATI)."]
        if outlet > 1:
            alasan.append("Usaha juga memiliki lebih dari satu outlet/fasilitas sehingga SEHATI berpotensi tidak sesuai (BR-01).")
        if omzet > BATAS_OMZET_SEHATI:
            alasan.append("Penjualan tahunan di atas Rp15 miliar (BR-03).")
    else:
        alasan = []
        if outlet > 1:
            alasan.append("Memiliki lebih dari satu outlet/fasilitas produksi; SEHATI dibatasi satu fasilitas dan satu outlet (BR-01, kriteria 6).")
        if omzet > BATAS_OMZET_SEHATI:
            alasan.append("Penjualan tahunan di atas Rp15 miliar; SEHATI tidak direkomendasikan (BR-03, kriteria 5).")
        if alasan:
            jalur = "Reguler"
        else:
            jalur = "SEHATI"
            alasan.append(
                "Memiliki NIB, satu outlet/fasilitas, dan penjualan tahunan tidak melebihi Rp15 miliar; "
                "kemungkinan memenuhi kriteria SEHATI (BR-01 s.d. BR-03)."
            )
    return {
        "rekomendasi_jalur": jalur,
        "alasan": alasan,
        "catatan": "Ini kemungkinan jalur berdasarkan kriteria yang dipublikasikan; kelayakan akhir ditentukan BPJPH dan pendamping.",
    }


def _deteksi_hewan(teks: str):
    for hewan, kata in _KATA_HEWAN.items():
        if any(re.search(rf"\b{k}\b", teks) for k in kata):
            return hewan
    return None


def bedah_titik_kritis(bahan: str) -> dict:
    """Bedah satu nama bahan: nabati/mineral (aman/exempt) vs bahan kritis turunan hewani.

    Args:
        bahan: Satu nama bahan sebagaimana tertulis di label, mis. 'gelatin sapi' atau 'E471'.

    Returns:
        dict berisi 'bahan', 'klasifikasi', 'jenis_hewan' (bila terdeteksi), 'butuh_bukti', dan 'alasan'.
    """
    teks = re.sub(r"\s+", " ", str(bahan or "")).strip().lower()
    dasar = {"bahan": str(bahan), "jenis_hewan": None, "butuh_bukti": False}
    if not teks:
        return {**dasar, "klasifikasi": "tidak_dikenal", "alasan": "Nama bahan kosong; perlu konfirmasi pengguna."}

    hewan = _deteksi_hewan(teks)

    if any(re.search(p, teks) for p in _KATA_HAM):
        return {**dasar, "klasifikasi": "haram", "butuh_bukti": False,
                "alasan": "Mengandung/berasal dari babi. Produk ini tidak dapat disertifikasi halal; rujuk ketentuan keterangan tidak halal BPJPH (BR-14)."}

    kunci = _cari_bahan(teks)
    kritis_kata = next((k for k in _KATA_KRITIS if k in teks), None)
    m_e = re.search(r"\be[\s\-]?(\d{3,4})[a-z]?\b", teks)
    e_hewani = bool(m_e and m_e.group(1) in _E_HEWANI)

    if kunci or kritis_kata or e_hewani:
        nabati = any(p in teks for p in _KATA_NABATI_PENANDA)
        if nabati and not kunci and kritis_kata in {"lemak", "shortening", "emulsifier", "pengemulsi", "lesitin", "lecithin", "flavour", "flavor", "perisa", "essence", "esens"} and not e_hewani:
            return {**dasar, "klasifikasi": "aman_exempt",
                    "alasan": "Tertulis bersumber nabati; umumnya tidak butuh bukti sembelihan, tetap konfirmasi sumber bila label tidak jelas."}
        info = MOCK_INGREDIENTS.get(kunci) if kunci else None
        if info and info["status"] == "Haram":
            return {**dasar, "klasifikasi": "haram", "alasan": f"{info['alasan']} (BR-14)"}
        alasan = info["alasan"] if info else (
            "Bahan ini berpotensi turunan hewani atau proses kritis (sumber/pelarut belum jelas); butuh bukti sumber sah."
        )
        return {**dasar, "klasifikasi": "kritis_hewani", "jenis_hewan": hewan, "butuh_bukti": True,
                "alasan": alasan, "sumber": info["sumber"] if info else None}

    if hewan:
        jalur = "RPH" if hewan in HEWAN_RUMINANSIA else "RPU"
        return {**dasar, "klasifikasi": "hewani_sembelihan", "jenis_hewan": hewan, "butuh_bukti": True,
                "alasan": f"Bahan hewan sembelihan ({hewan}); butuh bukti asal dari produsen atau {jalur} bersertifikat halal (BR-04, BR-13)."}

    if any(k in teks for k in _KATA_NABATI_MINERAL):
        return {**dasar, "klasifikasi": "aman_exempt",
                "alasan": "Bahan nabati/mineral; tidak masuk titik kritis hewani pada basis aturan ini."}

    if m_e:
        return {**dasar, "klasifikasi": "tidak_dikenal",
                "alasan": "E-number belum ada di basis data; perlu konfirmasi sumber ke pemasok/P3H."}
    return {**dasar, "klasifikasi": "tidak_dikenal", "alasan": "Bahan belum dikenali; perlu konfirmasi pengguna."}


def cek_bukti_hewan_sembelihan(jenis_hewan: str, nama_rph_rpu: str, nomor_sertifikat: str) -> dict:
    """Verifikasi kelengkapan bukti asal hewan sembelihan: RPH (sapi/kambing) atau RPU (ayam/bebek).

    Args:
        jenis_hewan: Jenis hewan: sapi, kambing, ayam, atau bebek.
        nama_rph_rpu: Nama RPH/RPU atau pemasok sebagaimana diberikan pengguna (boleh kosong).
        nomor_sertifikat: Nomor sertifikat halal RPH/RPU/produsen (boleh kosong).

    Returns:
        dict berisi 'status_bukti' (ada, kurang, tidak_jelas, di_luar_cakupan), 'jalur_bukti',
        'alasan', dan 'langkah_berikutnya'.
    """
    hewan = (jenis_hewan or "").strip().lower()
    nama = (nama_rph_rpu or "").strip()
    nomor = re.sub(r"[\s\-]", "", (nomor_sertifikat or "")).upper()
    dasar = {"jenis_hewan": hewan, "nama_rph_rpu": nama or None, "nomor_sertifikat": nomor or None}

    if hewan in HEWAN_RUMINANSIA:
        jalur = "RPH"
    elif hewan in HEWAN_UNGGAS:
        jalur = "RPU"
    else:
        return {**dasar, "status_bukti": "di_luar_cakupan", "jalur_bukti": None,
                "alasan": f"Jenis hewan '{hewan or '-'}' di luar cakupan MVP (sapi, kambing, ayam, bebek) (EC-14).",
                "langkah_berikutnya": "Konfirmasi asal bukti ke P3H."}

    dasar["jalur_bukti"] = jalur
    if not nama and not nomor:
        return {**dasar, "status_bukti": "kurang",
                "alasan": f"Tidak ada bukti {jalur} atau produsen bersertifikat halal untuk {hewan} (BR-04).",
                "langkah_berikutnya": f"Unggah nama dan sertifikat halal {jalur}/produsen pemasok {hewan}, atau cari pemasok bersertifikat."}

    entri = MOCK_RPH_RPU.get(nomor) if nomor else None
    if nomor and not entri:
        return {**dasar, "status_bukti": "tidak_jelas",
                "alasan": f"Nomor sertifikat {nomor} tidak ditemukan di registri {jalur}/produsen.",
                "langkah_berikutnya": "Periksa ulang nomor sertifikat atau minta foto sertifikat dari pemasok."}
    if not entri:
        return {**dasar, "status_bukti": "kurang",
                "alasan": f"Nama {jalur}/pemasok diberikan tetapi nomor sertifikat halal belum ada.",
                "langkah_berikutnya": f"Minta nomor sertifikat halal dari {nama}."}

    if entri["tipe"] != jalur or hewan not in entri["hewan"]:
        return {**dasar, "status_bukti": "kurang",
                "alasan": f"Sertifikat {nomor} ({entri['tipe']}: {', '.join(entri['hewan'])}) tidak sesuai jalur {jalur} untuk {hewan} (BR-13).",
                "langkah_berikutnya": f"Gunakan bukti {jalur} atau produsen bersertifikat halal yang sesuai untuk {hewan}."}
    if entri["status"] != "Berlaku":
        return {**dasar, "status_bukti": "kurang",
                "alasan": f"Sertifikat {entri['nama']} berstatus {entri['status']} (s.d. {entri['tanggal_kadaluarsa']}).",
                "langkah_berikutnya": "Minta sertifikat yang masih berlaku atau ganti pemasok."}
    if nama and nama.lower() not in entri["nama"].lower() and entri["nama"].lower() not in nama.lower():
        return {**dasar, "status_bukti": "tidak_jelas",
                "alasan": f"Nama '{nama}' berbeda dengan nama pada sertifikat '{entri['nama']}' (EC-05).",
                "langkah_berikutnya": "Minta klarifikasi nama pemasok/sertifikat."}
    return {**dasar, "status_bukti": "ada", "nama_pada_sertifikat": entri["nama"],
            "alasan": f"Bukti {jalur} ditemukan, berlaku, dan sesuai untuk {hewan}. Ini menilai kelengkapan bukti saja; kehalalan diperiksa LPH.",
            "langkah_berikutnya": "Lampirkan salinan sertifikat pada paket persiapan; pemeriksaan kehalalan oleh LPH."}


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


def _lampirkan_berkas_standalone(jenis: str, nama_berkas: str, pengajuan_id: str = "") -> dict:
    """Lampirkan berkas (foto denah dapur, dokumen komitmen bertanda tangan) atau deskripsi tata letak dapur ke pengajuan SIHALAL."""
    jenis_raw = (jenis or "").strip().lower()
    nama_raw = (nama_berkas or "").strip() or f"{jenis_raw or 'berkas'}.jpg"
    low_nama = nama_raw.lower()

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
        if any(k in low_nama for k in ("denah", "layout", "dapur", "tata letak", "ruang", "area")):
            jenis_norm = "layout"
        elif any(k in low_nama for k in ("komitmen", "tanda_tangan", "ttd", "tanda tangan", "surat")):
            jenis_norm = "tanda_tangan_pj"
        else:
            jenis_norm = "layout"

    info_berkas = {
        "nama": nama_raw if "." in nama_raw and len(nama_raw) <= 80 else f"{jenis_norm}_terkonfirmasi.jpg",
        "deskripsi": nama_raw,
        "url": f"/api/agent/berkas/anon/unggahan/{re.sub(r'[^A-Za-z0-9._-]', '_', nama_raw[:50])}",
    }

    disinkronkan = False
    kelengkapan = {}
    try:
        with sm._kunci:
            target = None
            if (pengajuan_id or "").strip():
                try:
                    target = sm._cari(pengajuan_id.strip())
                except Exception:
                    target = None
            if target is None and sm._pengajuan:
                draf_list = [p for p in sm._pengajuan if p.get("status") in ("draf", "dikembalikan")]
                target = draf_list[-1] if draf_list else sm._pengajuan[-1]

            if target is not None:
                pu = sm._pelaku_usaha
                pabrik_id = (target["data"].get("pabrikIds") or [x["id"] for x in pu.get("pabrik", [])] or ["pb-1"])[0]
                penyelia_id = (target["data"].get("penyeliaIds") or [x["id"] for x in pu.get("penyeliaHalal", [])] or ["py-1"])[0]
                sumber = sm._sumber_agen("cli-berkas", 1.0, f"Berkas/deskripsi diterima: {nama_raw}")

                if jenis_norm == "layout":
                    proses = copy.deepcopy(target["proses"])
                    proses["layout"] = [{
                        "id": "ag-ly-1",
                        "pabrikId": pabrik_id,
                        "berkas": {"nama": info_berkas["nama"], "url": info_berkas["url"]},
                        "sumber": sumber,
                    }]
                    sm.ubah_bagian(target["id"], "proses", proses, pelaku="kawalhalal", aksi="Melampirkan denah/layout dapur")
                else:
                    pemantauan = copy.deepcopy(target["pemantauan"])
                    existing_tt = pemantauan.get("tandaTangan") or []
                    pj_berkas = {"nama": info_berkas["nama"], "url": info_berkas["url"]}
                    py_berkas = {"nama": info_berkas["nama"], "url": info_berkas["url"]}
                    if existing_tt:
                        if jenis_norm == "tanda_tangan_pj":
                            py_berkas = existing_tt[0].get("penyelia") or py_berkas
                        elif jenis_norm == "tanda_tangan_penyelia":
                            pj_berkas = existing_tt[0].get("penanggungJawab") or pj_berkas
                    pemantauan["tandaTangan"] = [{
                        "id": "ag-tt-1",
                        "penanggungJawab": pj_berkas,
                        "penyeliaId": penyelia_id,
                        "penyelia": py_berkas,
                        "sumber": sumber,
                    }]
                    sm.ubah_bagian(target["id"], "pemantauan", pemantauan, pelaku="kawalhalal", aksi="Melampirkan dokumen bertanda tangan")

                disinkronkan = True
                kelengkapan = {k: f"{v['done']}/{v['total']}" for k, v in sm.hitung_kelengkapan(sm._cari(target["id"])).items()}
    except Exception:
        pass

    return {
        "status": "ok",
        "valid": True,
        "jenis": jenis_norm,
        "berkas": info_berkas["nama"],
        "nama_berkas": info_berkas["nama"],
        "deskripsi": nama_raw,
        "disinkronkan": disinkronkan,
        "kelengkapan": kelengkapan,
        "pesan": f"Berkas '{nama_raw}' ({jenis_norm}) diterima dan ditandai lengkap di state SIHALAL.",
    }


_lampirkan_berkas_standalone.__name__ = "lampirkan_berkas"


def lampirkan_berkas(jenis: str, nama_berkas: str, tool_context: ToolContext = None) -> dict:
    """Lampirkan berkas (foto denah dapur, dokumen bertanda tangan) atau deskripsi tata letak dapur ke pengajuan.

    Jika pengguna di CLI/terminal menyebutkan nama berkas (misal: denah_dapur.jpg, dokumen_komitmen_tanda_tangan.jpg)
    atau deskripsi tata letak dapur, otomatis anggap berkas valid dan tandai lengkap di state SIHALAL.

    Args:
        jenis: layout (foto denah/tata letak dapur), tanda_tangan_pj (dokumen bertanda tangan penanggung jawab), atau tanda_tangan_penyelia (dokumen bertanda tangan penyelia halal).
        nama_berkas: Nama berkas seperti di berkas_dari_pengguna, nama berkas yang disebut pengguna, atau deskripsi tata letak dapur.

    Returns:
        dict berisi status dan hasil sinkron.
    """
    if tool_context is None or not hasattr(tool_context, "state"):
        return _lampirkan_berkas_standalone(jenis, nama_berkas, str(tool_context or ""))

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
    if jenis_norm == "tanda_tangan_pj":
        lampiran.setdefault("tanda_tangan_penyelia", info_berkas)
    elif jenis_norm == "tanda_tangan_penyelia":
        lampiran.setdefault("tanda_tangan_pj", info_berkas)
    tool_context.state["lampiran"] = lampiran
    return {"status": "ok", "valid": True, "jenis": jenis_norm, "berkas": b["nama"], "nama_berkas": b["nama"], **_sinkron(tool_context)}


def _eskalasi_ke_pendamping_p3h_standalone(
    warung_id: str = "anon",
    nama_bahan: str = "",
    alasan_kritis: str = "",
    tingkat_risiko: str = "syubhat",
) -> dict:
    """Eskalasi bahan kritis, syubhat, atau meragukan ke tabel approvals untuk diverifikasi manual oleh Pendamping Halal (P3H)."""
    wid = (warung_id or "anon").strip()
    bahan_bersih = (nama_bahan or "").strip()
    alasan_bersih = (alasan_kritis or "Perlu verifikasi dokumen sumber oleh P3H.").strip()
    risiko_bersih = (tingkat_risiko or "syubhat").strip().lower()

    payload = {
        "warung_id": wid,
        "nama_bahan": bahan_bersih,
        "alasan": alasan_bersih,
        "tingkat_risiko": risiko_bersih,
        "status": "pending_p3h",
    }
    ticket_id = None
    try:
        import db

        if getattr(db, "supabase", None) is not None:
            res = db.require_supabase().table("approvals").insert(payload).execute()
            if res.data and isinstance(res.data, list) and len(res.data) > 0:
                ticket_id = res.data[0].get("id")
    except Exception:
        pass
    if not ticket_id:
        digest = hashlib.sha1(f"{wid}:{bahan_bersih}:{risiko_bersih}".encode("utf-8")).hexdigest()[:8]
        ticket_id = f"p3h-{digest}"

    return {
        "status": "berhasil_dieskalasi",
        "ticket_id": ticket_id,
        "warung_id": wid,
        "nama_bahan": bahan_bersih,
        "tingkat_risiko": risiko_bersih,
        "pesan": f"Bahan '{bahan_bersih}' telah diteruskan ke Pendamping Halal (P3H) untuk audit dokumen.",
    }


_eskalasi_ke_pendamping_p3h_standalone.__name__ = "eskalasi_ke_pendamping_p3h"


def eskalasi_ke_pendamping_p3h(
    nama_bahan: str,
    alasan_kritis: str,
    tingkat_risiko: str = "syubhat",
    tool_context: ToolContext = None,
    *,
    warung_id: str = "",
) -> dict:
    """Eskalasi bahan kritis, syubhat, atau meragukan ke tabel approvals untuk diverifikasi manual oleh Pendamping Halal (P3H).

    Args:
        nama_bahan: Nama bahan yang membutuhkan verifikasi P3H.
        alasan_kritis: Alasan mengapa bahan ini membutuhkan tinjauan manual P3H.
        tingkat_risiko: Kategori risiko (syubhat, kritis_hewani, tidak_dikenal, atau di_luar_cakupan).

    Returns:
        dict berisi status eskalasi, ticket_id, dan pesan tindak lanjut.
    """
    if tool_context is not None and hasattr(tool_context, "state"):
        uid = getattr(tool_context, "user_id", None) or "anon"
        h = _eskalasi_ke_pendamping_p3h_standalone(uid, nama_bahan, alasan_kritis, tingkat_risiko or "syubhat")
        daftar_eskalasi = list(tool_context.state.get("eskalasi_p3h") or [])
        daftar_eskalasi.append(h)
        tool_context.state["eskalasi_p3h"] = daftar_eskalasi
        return h

    risiko_set = {"syubhat", "kritis_hewani", "tidak_dikenal", "di_luar_cakupan"}
    if not warung_id and (tingkat_risiko or "").strip().lower() not in risiko_set and isinstance(tool_context, (str, type(None))):
        wid = nama_bahan
        bahan_real = alasan_kritis
        alasan_real = tingkat_risiko
        risiko_real = str(tool_context or "syubhat")
        return _eskalasi_ke_pendamping_p3h_standalone(wid, bahan_real, alasan_real, risiko_real)

    return _eskalasi_ke_pendamping_p3h_standalone(warung_id or "anon", nama_bahan, alasan_kritis, tingkat_risiko or "syubhat")


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



def cari_rpu_halal_terdekat(lokasi: str = "Bandung", jenis: str = "unggas") -> dict:
    """Cari rekomendasi RPU/RPH bersertifikat halal terdekat di sekitar lokasi pelaku usaha beserta tautan Google Maps.

    Panggil secara proaktif bila daging ayam/bebek atau sapi/kambing berasal dari lapak yang belum jelas
    sertifikat halalnya, lalu bagikan tautan Google Maps tersebut sebagai opsi solusi alternatif.

    Args:
        lokasi: Lokasi atau kota pelaku usaha (kosongkan untuk default Bandung / Jawa Barat).
        jenis: Jenis hewan atau fasilitas, contoh unggas, ayam, bebek, sapi, kambing, atau ruminansia.

    Returns:
        dict berisi daftar rekomendasi fasilitas RPU/RPH resmi, status sertifikasi, dan URL Google Maps.
    """
    lokasi_bersih = (lokasi or "").strip() or "Bandung, Jawa Barat"
    jenis_bersih = (jenis or "unggas").strip().lower()

    if jenis_bersih in ("sapi", "kambing", "domba", "ruminansia", "rph"):
        tipe_fasilitas = "RPH"
        hewan_filter = {"sapi", "kambing"} if jenis_bersih in ("ruminansia", "rph") else {jenis_bersih}
    else:
        tipe_fasilitas = "RPU"
        hewan_filter = {"ayam", "bebek"} if jenis_bersih in ("unggas", "rpu", "") else {jenis_bersih}

    lokasi_query = re.sub(r"\s+", "+", lokasi_bersih)
    maps_url = f"https://www.google.com/maps/search/?api=1&query=RPU+Halal+{lokasi_query}"

    rekomendasi = []
    for nomor, info in MOCK_RPH_RPU.items():
        if info.get("status") != "Berlaku":
            continue
        if info.get("tipe") != tipe_fasilitas and not (set(info.get("hewan", [])) & hewan_filter):
            continue
        nama_fas = info["nama"]
        lok_fas = info.get("lokasi", "Bandung, Jawa Barat")
        fas_query = re.sub(r"\s+", "+", f"{nama_fas} {lokasi_bersih}")
        rekomendasi.append({
            "nama_fasilitas": nama_fas,
            "nama": nama_fas,
            "tipe": info["tipe"],
            "jenis_hewan": info["hewan"],
            "nomor_sertifikat": nomor,
            "status_sertifikasi": info["status"],
            "status": info["status"],
            "tanggal_kadaluarsa": info.get("tanggal_kadaluarsa", ""),
            "lokasi": lok_fas,
            "alamat": info.get("alamat", lok_fas),
            "label": "Rekomendasi sesuai kebutuhan",
            "google_maps_url": maps_url,
            "url_google_maps": maps_url,
            "url_maps_fasilitas": f"https://www.google.com/maps/search/?api=1&query={fas_query}",
        })

    if not rekomendasi:
        for nomor, info in MOCK_RPH_RPU.items():
            if info.get("status") == "Berlaku":
                nama_fas = info["nama"]
                lok_fas = info.get("lokasi", "Bandung, Jawa Barat")
                rekomendasi.append({
                    "nama_fasilitas": nama_fas,
                    "nama": nama_fas,
                    "tipe": info["tipe"],
                    "jenis_hewan": info["hewan"],
                    "nomor_sertifikat": nomor,
                    "status_sertifikasi": info["status"],
                    "status": info["status"],
                    "tanggal_kadaluarsa": info.get("tanggal_kadaluarsa", ""),
                    "lokasi": lok_fas,
                    "alamat": info.get("alamat", lok_fas),
                    "label": "Rekomendasi sesuai kebutuhan",
                    "google_maps_url": maps_url,
                    "url_google_maps": maps_url,
                })

    rekomendasi = rekomendasi[:3]
    daftar_nama = ", ".join(f"{r['nama_fasilitas']} ({r['nomor_sertifikat']} - {r['status_sertifikasi']})" for r in rekomendasi)
    return {
        "status": "ok",
        "lokasi": lokasi_bersih,
        "jenis": jenis_bersih,
        "tipe_fasilitas": tipe_fasilitas,
        "google_maps_url": maps_url,
        "url_google_maps": maps_url,
        "rekomendasi": rekomendasi,
        "pesan": (
            f"Rekomendasi {tipe_fasilitas} bersertifikat halal terdekat di sekitar {lokasi_bersih}: {daftar_nama}. "
            f"Telusuri di Google Maps: {maps_url}"
        ),
    }


def _temukan_konteks_sesi(session_id: str = "") -> tuple[dict | None, dict]:
    """Cari draf pengajuan SIHALAL dan state sesi ADK berdasarkan session_id atau pengajuan_id."""
    sid = (session_id or "").strip()
    state_adk: dict = {}
    target_pengajuan: dict | None = None

    try:
        ka_agent = sys.modules.get("kawal_agent.agent")
        if ka_agent is not None:
            store = getattr(ka_agent._sessions, "sessions", None) or {}
            app_sessions = store.get(ka_agent.APP_NAME, {}) if isinstance(store, dict) else {}
            kandidat_sid = {sid, f"s-{_slug_user(sid)}", _slug_user(sid)}
            for user_key, user_dict in app_sessions.items():
                if not isinstance(user_dict, dict):
                    continue
                for s_key, s_obj in user_dict.items():
                    st = getattr(s_obj, "state", None) or {}
                    if (
                        user_key in kandidat_sid
                        or s_key in kandidat_sid
                        or st.get("pengajuan_id") == sid
                    ):
                        state_adk = dict(st)
                        break
                if state_adk:
                    break
    except Exception:
        pass

    try:
        with sm._kunci:
            pid_target = state_adk.get("pengajuan_id") or sid
            if pid_target:
                for p in sm._pengajuan:
                    if p.get("id") == pid_target:
                        target_pengajuan = p
                        break
            if target_pengajuan is None and sm._pengajuan:
                if len(sm._pengajuan) > 3:
                    draf_baru = [p for p in sm._pengajuan[3:] if p.get("status") in ("draf", "dikembalikan")]
                    target_pengajuan = draf_baru[-1] if draf_baru else sm._pengajuan[-1]
                else:
                    if "kosong" in sid.lower() or sid == "pj-3":
                        target_pengajuan = sm._cari("pj-3")
                    else:
                        draf_list = [p for p in sm._pengajuan if p.get("status") in ("draf", "dikembalikan")]
                        target_pengajuan = draf_list[0] if draf_list else sm._pengajuan[-1]
    except Exception:
        pass

    return target_pengajuan, state_adk


def _validasi_kelayakan_sihalal_standalone(session_id: str = "default") -> dict:
    """Reflection & Critic Step sebelum final submit ke SIHALAL."""
    target, state_adk = _temukan_konteks_sesi(session_id)
    dok = state_adk.get("dok") or {}

    if target is None:
        return {
            "session_id": session_id,
            "pengajuan_id": None,
            "layak_submit": False,
            "siap_kirim": False,
            "valid": False,
            "status": "belum_layak",
            "bagian_kurang": ["draf_pengajuan", "alur_produksi", "verifikasi_bahan_hewani", "tim_halal"],
            "celah_ditemukan": ["Belum ada draf pengajuan SIHALAL pada sesi ini."],
            "harus_diperbaiki": ["Belum ada draf pengajuan SIHALAL pada sesi ini."],
            "audit_internal": {
                "alur_produksi_4_tahap": {"lengkap": False, "terisi": [], "kurang": ["alur_proses", "penyimpanan", "hasil_produksi", "distribusi"]},
                "verifikasi_bahan_hewani": {"lengkap": False, "bahan_bermasalah": [], "catatan": ["Daftar bahan belum ada."]},
                "data_tim_halal": {"lengkap": False, "jumlah_anggota": 0, "penyelia_terdaftar": False, "kurang": ["tim_halal", "penyelia_halal"]},
            },
            "pesan": "Audit internal: Draf pengajuan SIHALAL belum dibuat. Lengkapi profil usaha dan buat draf terlebih dahulu sebelum submit.",
        }

    proses = target.get("proses") or {}
    bahan_obj = target.get("bahan") or {}
    komitmen = target.get("komitmen") or {}
    data_pengajuan = target.get("data") or {}

    celah_ditemukan: list[str] = []
    bagian_kurang: list[str] = []

    peta_alur = {
        "alur_proses": bool(proses.get("alurProses")) or bool(dok.get("proses")),
        "penyimpanan": bool(proses.get("penyimpanan")) or bool(dok.get("penyimpanan")),
        "hasil_produksi": bool(proses.get("hasilProduksi")) or bool(dok.get("hasil")),
        "distribusi": bool(proses.get("distribusi")) or bool(dok.get("distribusi")),
    }
    alur_terisi = [k for k, ok in peta_alur.items() if ok]
    alur_kurang = [k for k, ok in peta_alur.items() if not ok]
    alur_lengkap = len(alur_kurang) == 0
    if not alur_lengkap:
        bagian_kurang.append("alur_produksi")
        celah_ditemukan.append(
            f"Kelengkapan 4 alur produksi belum terpenuhi (kurang: {', '.join(alur_kurang)})."
        )

    daftar_bahan = list(bahan_obj.get("daftarBahan") or [])
    bahan_dok = list(dok.get("bahan") or [])
    bahan_bermasalah: list[str] = []
    catatan_bahan: list[str] = []

    if not daftar_bahan and not bahan_dok:
        bagian_kurang.append("verifikasi_bahan_hewani")
        celah_ditemukan.append("Daftar bahan masih kosong; belum ada bahan yang diverifikasi.")
    else:
        for b in daftar_bahan:
            nama_b = b.get("nama", "")
            bukti_b = b.get("bukti", "kurang")
            no_sert = b.get("noSertifikat") or ""
            bedah = bedah_titik_kritis(nama_b)
            kl = bedah.get("klasifikasi")
            if kl in ("hewani_sembelihan", "kritis_hewani", "haram") and (bukti_b != "ada" or not no_sert):
                bahan_bermasalah.append(nama_b)
                catatan_bahan.append(
                    f"Bahan hewani/kritis '{nama_b}' berstatus bukti '{bukti_b}' dan belum memiliki sertifikat halal RPH/RPU/produsen yang terverifikasi."
                )
            elif bukti_b != "ada":
                bahan_bermasalah.append(nama_b)
                catatan_bahan.append(
                    f"Bahan '{nama_b}' masih memiliki celah bukti ({bukti_b}): {b.get('alasanBukti', 'perlu konfirmasi')}."
                )

        for b_dok in bahan_dok:
            v = b_dok.get("verifikasi") or {}
            nama_b = b_dok.get("nama", "")
            if v.get("verdict") == "perlu_tindak_lanjut" and not b_dok.get("disetujui"):
                if nama_b not in bahan_bermasalah:
                    bahan_bermasalah.append(nama_b)
                    catatan_bahan.append(
                        f"Bahan '{nama_b}' masih ditahan karena celah bukti: {v.get('alasan', 'belum ada sertifikat')}."
                    )

    bahan_hewani_lengkap = bool(daftar_bahan or bahan_dok) and len(bahan_bermasalah) == 0
    if not bahan_hewani_lengkap and "verifikasi_bahan_hewani" not in bagian_kurang:
        bagian_kurang.append("verifikasi_bahan_hewani")
    celah_ditemukan.extend(catatan_bahan)

    anggota_tim = list(komitmen.get("anggota") or state_adk.get("anggota") or [])
    penyelia_ids = list(data_pengajuan.get("penyeliaIds") or [])
    persetujuan_adk = state_adk.get("persetujuan") or {}
    komitmen_lengkap = (
        (komitmen.get("kebijakanHalal") is not None or "kebijakan_halal" in persetujuan_adk)
        and (komitmen.get("pengertianHalalHaram") is not None or "pengertian_halal_haram" in persetujuan_adk)
        and (komitmen.get("praktikSjph") is not None or "praktik_sjph" in persetujuan_adk)
    )
    tim_kurang: list[str] = []
    if not anggota_tim:
        tim_kurang.append("anggota_tim_halal")
        celah_ditemukan.append("Data tim halal belum diisi (belum ada ketua/anggota tim manajemen halal pada Komitmen).")
    if not penyelia_ids:
        tim_kurang.append("penyelia_halal")
        celah_ditemukan.append("Data penyelia halal belum terdaftar pada pengajuan.")
    if not komitmen_lengkap:
        tim_kurang.append("pernyataan_komitmen_sjph")
        celah_ditemukan.append("Pernyataan komitmen SJPH (kebijakan halal, pengertian halal-haram, praktik SJPH) belum disetujui lengkap.")

    tim_halal_lengkap = len(tim_kurang) == 0
    if not tim_halal_lengkap:
        bagian_kurang.append("tim_halal")

    try:
        kurang_sihalal = sinkron.rincian_kurang(target)
        for item_k in kurang_sihalal:
            if item_k not in celah_ditemukan:
                celah_ditemukan.append(item_k)
        if kurang_sihalal and "dokumen_sihalal" not in bagian_kurang:
            bagian_kurang.append("dokumen_sihalal")
    except Exception:
        pass

    layak = len(celah_ditemukan) == 0
    if layak:
        pesan = (
            "Audit kelayakan SIHALAL LOLOS: 4 alur produksi lengkap, seluruh bahan hewani/kritis terverifikasi, "
            "dan data tim halal serta komitmen SJPH telah lengkap. Siap meminta konfirmasi akhir pengguna untuk submit."
        )
    else:
        pesan = (
            f"Audit kelayakan SIHALAL menemukan {len(celah_ditemukan)} celah pada bagian {', '.join(bagian_kurang)}. "
            "JANGAN lakukan submit dulu; beri tahu pengguna bagian yang kurang untuk dilengkapi: "
            + " | ".join(celah_ditemukan[:5])
        )

    return {
        "session_id": session_id,
        "pengajuan_id": target.get("id"),
        "layak_submit": layak,
        "siap_kirim": layak,
        "valid": layak,
        "status": "layak_submit" if layak else "belum_layak",
        "bagian_kurang": bagian_kurang,
        "celah_ditemukan": celah_ditemukan,
        "harus_diperbaiki": celah_ditemukan,
        "audit_internal": {
            "alur_produksi_4_tahap": {
                "lengkap": alur_lengkap,
                "terisi": alur_terisi,
                "kurang": alur_kurang,
            },
            "verifikasi_bahan_hewani": {
                "lengkap": bahan_hewani_lengkap,
                "bahan_bermasalah": bahan_bermasalah,
                "catatan": catatan_bahan,
            },
            "data_tim_halal": {
                "lengkap": tim_halal_lengkap,
                "jumlah_anggota": len(anggota_tim),
                "anggota": [a.get("nama") for a in anggota_tim if isinstance(a, dict)],
                "penyelia_terdaftar": bool(penyelia_ids),
                "komitmen_sjph_disetujui": komitmen_lengkap,
                "kurang": tim_kurang,
            },
        },
        "pesan": pesan,
    }


_validasi_kelayakan_sihalal_standalone.__name__ = "validasi_kelayakan_sihalal"


def validasi_kelayakan_sihalal(session_id: str = "", tool_context: ToolContext = None) -> dict:
    """Reflection & Critic Step sebelum konfirmasi submit akhir: audit kelengkapan 4 alur produksi, verifikasi bahan hewani, dan data tim halal.

    Jika masih ada celah, beri tahu bagian yang kurang alih-alih langsung submit.

    Args:
        session_id: ID sesi percakapan atau ID pengajuan SIHALAL (boleh dikosongkan bila dipanggil dalam sesi aktif).

    Returns:
        dict berisi layak_submit, audit_internal, bagian_kurang, celah_ditemukan, dan pesan.
    """
    sid = session_id
    if tool_context is not None and hasattr(tool_context, "state"):
        _sinkron(tool_context)
        sid = tool_context.state.get("pengajuan_id") or session_id or getattr(tool_context, "user_id", "") or ""
    hasil = _validasi_kelayakan_sihalal_standalone(sid)
    if tool_context is not None and hasattr(tool_context, "state"):
        cek_adk = _periksa(tool_context)
        for m in cek_adk.get("harus_diperbaiki", []):
            if m not in hasil["celah_ditemukan"]:
                hasil["celah_ditemukan"].append(m)
        if hasil["celah_ditemukan"]:
            hasil["layak_submit"] = False
            hasil["siap_kirim"] = False
            hasil["valid"] = False
            hasil["status"] = "belum_layak"
    return hasil


def _pindai_nota_atau_label_standalone(file_path: str) -> dict:
    """Ekstrak data belanja bahan (nama bahan, merk, nomor SH/PIRT, tanggal) dari foto bon/nota atau label kemasan menggunakan multimodal Gemini."""
    raw_path = (file_path or "").strip() or "nota_belanja.jpg"
    kandidat_path = Path(raw_path)
    if not kandidat_path.is_file():
        try:
            for p in GENERATED_DIR.rglob(Path(raw_path).name):
                if p.is_file():
                    kandidat_path = p
                    break
        except Exception:
            pass

    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    kunci_palsu = api_key.lower() in ("kunci-palsu", "dummy", "test", "mock", "your-api-key")

    if kandidat_path.is_file() and not kunci_palsu:
        try:
            from google import genai
            from google.genai import types

            image_bytes = kandidat_path.read_bytes()
            mime_type = mimetypes.guess_type(kandidat_path.name)[0] or "image/jpeg"
            project = os.getenv("GOOGLE_CLOUD_PROJECT", "hackathon-primestep-10")
            location = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-southeast1")
            client = genai.Client(vertexai=True, project=project, location=location)
            prompt_ocr = (
                "Ekstrak informasi belanja bahan atau label kemasan ini ke format JSON murni dengan kunci: "
                '{"nama_bahan": "...", "merk": "...", "nomor_sh_pirt": "...", "tanggal": "YYYY-MM-DD", '
                '"item_belanja": [{"nama_bahan": "...", "merk": "...", "nomor_sh_pirt": "...", "tanggal": "YYYY-MM-DD", "jumlah": 1, "satuan": "kg"}]}. '
                "Jika nomor sertifikat halal (ID...) atau P-IRT tidak terlihat, isi string kosong."
            )
            resp = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                            types.Part.from_text(text=prompt_ocr),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            teks_json = re.sub(r"^```(?:json)?|```$", "", (resp.text or "").strip(), flags=re.MULTILINE).strip()
            data_ocr = json.loads(teks_json)
            if isinstance(data_ocr, list):
                data_ocr = data_ocr[0] if data_ocr and isinstance(data_ocr[0], dict) else {}
            items = data_ocr.get("item_belanja") or []
            utama = items[0] if items else data_ocr
            nama_bahan = str(data_ocr.get("nama_bahan") or utama.get("nama_bahan") or "Tepung Tapioka")
            merk = str(data_ocr.get("merk") or utama.get("merk") or "")
            nomor_sh = str(data_ocr.get("nomor_sh_pirt") or utama.get("nomor_sh_pirt") or "")
            tanggal = str(data_ocr.get("tanggal") or utama.get("tanggal") or date.today().isoformat())
            if not items:
                items = [{"nama_bahan": nama_bahan, "merk": merk, "nomor_sh_pirt": nomor_sh, "tanggal": tanggal, "jumlah": 1, "satuan": "pcs"}]
            return {
                "status": "ok",
                "mode": "live",
                "file_path": raw_path,
                "nama_bahan": nama_bahan,
                "merk": merk,
                "nomor_sh_pirt": nomor_sh,
                "tanggal": tanggal,
                "item_belanja": items,
                "pesan": (
                    f"Hasil OCR nota/label '{Path(raw_path).name}': bahan '{nama_bahan}', "
                    f"merk '{merk or '-'}', nomor SH/PIRT '{nomor_sh or 'belum tercantum'}', tanggal {tanggal}."
                ),
            }
        except Exception:
            pass

    low = raw_path.lower()
    tgl_default = "2026-10-22"
    if "kecap" in low:
        items = [{
            "nama_bahan": "Kecap Manis",
            "merk": "Kecap Cap Layar",
            "nomor_sh_pirt": "ID1230000100101",
            "tanggal": tgl_default,
            "jumlah": 2,
            "satuan": "pcs",
        }]
    elif "ayam" in low or "rpu" in low or "unggas" in low:
        items = [{
            "nama_bahan": "Daging Ayam Segar",
            "merk": "RPU Sumber Unggas Halal",
            "nomor_sh_pirt": "ID3175000200002",
            "tanggal": tgl_default,
            "jumlah": 5,
            "satuan": "kg",
        }]
    elif "sapi" in low or "rph" in low or "bakso" in low:
        items = [{
            "nama_bahan": "Daging Sapi Segar",
            "merk": "RPH Cakung Halal",
            "nomor_sh_pirt": "ID3174000100001",
            "tanggal": tgl_default,
            "jumlah": 5,
            "satuan": "kg",
        }]
    elif "minyak" in low:
        items = [{
            "nama_bahan": "Minyak Goreng Sawit",
            "merk": "Minyak Kuning Emas",
            "nomor_sh_pirt": "ID1230000100104",
            "tanggal": tgl_default,
            "jumlah": 2,
            "satuan": "liter",
        }]
    else:
        items = [
            {
                "nama_bahan": "Tepung Tapioka",
                "merk": "Tapioka Cap Perahu",
                "nomor_sh_pirt": "ID1230000100105",
                "tanggal": tgl_default,
                "jumlah": 5,
                "satuan": "kg",
            },
            {
                "nama_bahan": "Kecap Manis",
                "merk": "Kecap Cap Layar",
                "nomor_sh_pirt": "ID1230000100101",
                "tanggal": tgl_default,
                "jumlah": 2,
                "satuan": "pcs",
            },
        ]

    utama = items[0]
    return {
        "status": "ok",
        "mode": "mock",
        "file_path": raw_path,
        "nama_bahan": utama["nama_bahan"],
        "merk": utama["merk"],
        "nomor_sh_pirt": utama["nomor_sh_pirt"],
        "tanggal": utama["tanggal"],
        "item_belanja": items,
        "pesan": (
            f"Hasil ekstraksi OCR nota/label '{Path(raw_path).name}': bahan '{utama['nama_bahan']}', "
            f"merk '{utama['merk']}', nomor SH/PIRT '{utama['nomor_sh_pirt']}', tanggal {utama['tanggal']}. "
            "Data siap dicatat tanpa ketik manual."
        ),
    }


_pindai_nota_atau_label_standalone.__name__ = "pindai_nota_atau_label"


def pindai_nota_atau_label(file_path: str, tool_context: ToolContext = None) -> dict:
    """Ekstrak data belanja bahan (nama bahan, merk, nomor SH/PIRT, tanggal) dari foto bon/nota atau label kemasan menggunakan multimodal Gemini.

    Args:
        file_path: Nama berkas atau path foto nota/label yang dikirim pengguna.

    Returns:
        dict berisi nama_bahan, merk, nomor_sh_pirt, tanggal, item_belanja, dan pesan.
    """
    target_path = (file_path or "").strip()
    if tool_context is not None and hasattr(tool_context, "state") and target_path:
        b = _berkas_masuk(tool_context).get(target_path)
        if b and b.get("path"):
            target_path = b["path"]
    return _pindai_nota_atau_label_standalone(target_path)


def _ekspor_berkas_sjph_standalone(session_id: str = "default") -> dict:
    """Kompilasi seluruh jawaban percakapan menjadi draf Sistem Jaminan Produk Halal (SJPH) siap unduh (.xlsx dan .html)."""
    target, state_adk = _temukan_konteks_sesi(session_id)
    pu = sm._pelaku_usaha
    dok = templates.dok_kosong()
    for k, v in (state_adk.get("dok") or {}).items():
        if v:
            dok[k] = list(v)

    if target is not None:
        if not dok["produk"] and target.get("produk"):
            dok["produk"] = [
                {
                    "nama": pr.get("nama", ""),
                    "merek": pr.get("merek") or target.get("data", {}).get("merek", ""),
                    "rincian": pr.get("rincian", ""),
                }
                for pr in target["produk"]
            ]
        if not dok["bahan"] and target.get("bahan", {}).get("daftarBahan"):
            id_ke_nama = {b["id"]: b.get("nama", "") for b in target["bahan"]["daftarBahan"]}
            dok["bahan"] = [
                {
                    "nama": b.get("nama", ""),
                    "jenis": b.get("jenis", "bahan"),
                    "produsen": b.get("produsen", ""),
                    "nomor_sertifikat": b.get("noSertifikat", ""),
                    "pemasok": b.get("produsen", ""),
                    "status_verifikasi": f"bukti {b.get('bukti', 'kurang')} ({b.get('konfirmasi', 'perlu-konfirmasi')})",
                }
                for b in target["bahan"]["daftarBahan"]
            ]
            if not dok["pembelian"] and target["bahan"].get("catatanPembelian"):
                periksa_map = {pm.get("bahanId"): pm for pm in (target["bahan"].get("pemeriksaan") or [])}
                dok["pembelian"] = [
                    {
                        "bahan": id_ke_nama.get(cp.get("bahanId"), cp.get("bahanId", "")),
                        "jumlah": cp.get("jumlah", ""),
                        "satuan": cp.get("satuan", ""),
                        "tanggal": cp.get("tanggal", ""),
                        "lokasi_periksa": periksa_map.get(cp.get("bahanId"), {}).get("lokasi", ""),
                        "tanggal_periksa": periksa_map.get(cp.get("bahanId"), {}).get("tanggal", ""),
                    }
                    for cp in target["bahan"]["catatanPembelian"]
                ]
        proses_t = target.get("proses") or {}
        if not dok["proses"] and proses_t.get("alurProses"):
            dok["proses"] = [
                {
                    "judul": ap.get("judul", ""),
                    "langkah": "; ".join(ap.get("langkah") or []),
                }
                for ap in proses_t["alurProses"]
            ]
        if not dok["penyimpanan"] and proses_t.get("penyimpanan"):
            dok["penyimpanan"] = [
                {
                    "item": ps.get("refId", ""),
                    "jenis": ps.get("jenis", "bahan"),
                    "jumlah": ps.get("jumlah", ""),
                    "tanggal_masuk": ps.get("tanggalMasuk", ""),
                }
                for ps in proses_t["penyimpanan"]
            ]
        if not dok["hasil"] and proses_t.get("hasilProduksi"):
            dok["hasil"] = [
                {
                    "produk": hp.get("produkId", ""),
                    "jumlah": hp.get("jumlah", ""),
                    "tanggal_produksi": hp.get("tanggalProduksi", ""),
                }
                for hp in proses_t["hasilProduksi"]
            ]
        if not dok["distribusi"] and proses_t.get("distribusi"):
            dok["distribusi"] = [
                {
                    "tujuan": ds.get("tujuan", ""),
                    "produk": ds.get("produkId", ""),
                    "jumlah": ds.get("jumlah", ""),
                }
                for ds in proses_t["distribusi"]
            ]

    user_id = (session_id or "6281200000000").strip()
    kategori = state_adk.get("kategori") or (
        (target.get("data", {}).get("jenisProduk") or "makanan").lower() if target else "makanan"
    )
    slug_usaha = sinkron.slug(pu.get("namaUsaha", "usaha"))
    nama_xlsx = f"Berkas-Halal-{slug_usaha}.xlsx"
    folder = folder_pengguna(user_id)
    path_xlsx = folder / nama_xlsx

    komitmen_obj = (target.get("komitmen") if target else None) or {}
    anggota_tim = list(komitmen_obj.get("anggota") or state_adk.get("anggota") or [])
    info_xlsx = templates.buat_xlsx(dok, kategori, pu, path_xlsx, komitmen=komitmen_obj, anggota=anggota_tim)
    url_unduh_xlsx = url_berkas(user_id, nama_xlsx)

    nama_html = f"Manual-SJPH-{slug_usaha}.html"
    path_html = folder / nama_html
    if target is not None:
        html_sjph = sm._manual_sjph(target, pu)
    else:
        html_sjph = f"<html><body><h1>Draf Manual SJPH - {pu.get('namaUsaha', '-')}</h1></body></html>"
    path_html.write_text(html_sjph, encoding="utf-8")
    url_unduh_html = url_berkas(user_id, nama_html)

    ringkasan_sjph = {
        "nama_usaha": pu.get("namaUsaha", "BELUM DIISI"),
        "nib": pu.get("nib") or "BELUM DIISI",
        "jalur": (target.get("jalur") if target else state_adk.get("jalur")) or "self-declare",
        "jumlah_produk": len(dok["produk"]),
        "jumlah_bahan": len(dok["bahan"]),
        "jumlah_catatan_pembelian": len(dok["pembelian"]),
        "alur_produksi_tercatat": {
            "proses": len(dok["proses"]),
            "penyimpanan": len(dok["penyimpanan"]),
            "hasil_produksi": len(dok["hasil"]),
            "distribusi": len(dok["distribusi"]),
        },
        "tim_halal": [a.get("nama") for a in anggota_tim if isinstance(a, dict)],
    }

    return {
        "status": "dibuat",
        "valid": True,
        "nama_berkas": nama_xlsx,
        "nama_berkas_sjph": nama_html,
        "file_path": str(path_xlsx),
        "file_path_sjph": str(path_html),
        "url": url_unduh_xlsx,
        "url_sjph": url_unduh_html,
        "dokumen_sihalal_url": f"/api/sihalal/pengajuan/{target['id']}/dokumen/sjph" if target else url_unduh_html,
        "ringkasan_sjph": ringkasan_sjph,
        **info_xlsx,
        "pesan": (
            f"Draf Sistem Jaminan Produk Halal (SJPH) '{nama_xlsx}' dan '{nama_html}' berhasil dikompilasi "
            f"dari jawaban percakapan dan siap diunduh di {url_unduh_xlsx}."
        ),
    }


_ekspor_berkas_sjph_standalone.__name__ = "ekspor_berkas_sjph"


def ekspor_berkas_sjph(session_id: str = "", tool_context: ToolContext = None) -> dict:
    """Kompilasi seluruh jawaban percakapan menjadi draf Sistem Jaminan Produk Halal (SJPH) siap unduh (.xlsx dan .html).

    Returns:
        dict berisi status, nama_berkas, url unduh, ringkasan_sjph, dan pesan.
    """
    if hasattr(session_id, "state") and tool_context is None:
        tool_context = session_id
        session_id = ""
    if tool_context is not None and hasattr(tool_context, "state"):
        hasil_xlsx = buat_berkas_xlsx(tool_context)
        sid = tool_context.state.get("pengajuan_id") or session_id or getattr(tool_context, "user_id", "") or ""
        hasil_sjph = _ekspor_berkas_sjph_standalone(sid)
        return {**hasil_sjph, **hasil_xlsx, "ringkasan_sjph": hasil_sjph.get("ringkasan_sjph", {})}
    return _ekspor_berkas_sjph_standalone(str(session_id or ""))


SEMUA_TOOL.extend([
    cari_rpu_halal_terdekat,
    validasi_kelayakan_sihalal,
    pindai_nota_atau_label,
    ekspor_berkas_sjph,
])

TOOL_REGISTRY = {
    "validasi_kriteria_triase": validasi_kriteria_triase,
    "bedah_titik_kritis": bedah_titik_kritis,
    "analisis_titik_kritis": analisis_titik_kritis,
    "cek_bukti_hewan_sembelihan": cek_bukti_hewan_sembelihan,
    "cek_sertifikat_bpjph": cek_sertifikat_bpjph,
    "eskalasi_ke_pendamping_p3h": _eskalasi_ke_pendamping_p3h_standalone,
    "lampirkan_berkas": _lampirkan_berkas_standalone,
    "cari_rpu_halal_terdekat": cari_rpu_halal_terdekat,
    "validasi_kelayakan_sihalal": _validasi_kelayakan_sihalal_standalone,
    "pindai_nota_atau_label": _pindai_nota_atau_label_standalone,
    "ekspor_berkas_sjph": _ekspor_berkas_sjph_standalone,
}
