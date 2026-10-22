"""Kategori produk yang bisa diajukan dan pertanyaan kunci per kategori.

Data-driven: menambah kategori cukup menambah satu entri di KATEGORI.
"""
from typing import Optional

KATEGORI: dict[str, dict] = {
    "makanan": {
        "label": "Makanan",
        "klasifikasi": "Makanan",
        "rincian": ["Produk olahan daging", "Makanan siap saji", "Roti dan kue", "Makanan ringan", "Bumbu dan saus"],
        "contoh": "bakso, soto, nasi goreng, kue, bumbu",
        "pertanyaan_kunci": [
            "Nama produk dan merek yang mau didaftarkan",
            "Daftar bahan baku dan kemasan (bisa kirim foto label)",
            "Apakah memakai daging atau unggas (sapi, kambing, ayam, bebek)? Dari lapak/pemasok mana",
            "Cara memasak singkat dan tempat menyimpan bahan",
        ],
        "titik_kritis": "daging dan unggas (perlu RPH/RPU bersertifikat), gelatin, lemak, perisa, emulsifier, alkohol",
    },
    "minuman": {
        "label": "Minuman",
        "klasifikasi": "Minuman",
        "rincian": ["Minuman berbasis teh", "Minuman berbasis kopi", "Minuman sari buah", "Minuman lainnya"],
        "contoh": "es teh, kopi, jus, sirup, minuman kemasan",
        "pertanyaan_kunci": [
            "Nama minuman dan merek",
            "Bahan baku: gula, perisa, pewarna, susu, topping (bisa kirim foto label)",
            "Apakah ada bahan beralkohol atau perisa/esens",
            "Cara membuat dan menyimpan",
        ],
        "titik_kritis": "perisa dan esens, pewarna (karmin), gelatin pada jelly/topping, alkohol, susu dan olahannya",
    },
    "kosmetik": {
        "label": "Kosmetik",
        "klasifikasi": "Kosmetik",
        "rincian": ["Perawatan kulit", "Perawatan rambut", "Tata rias", "Parfum dan wewangian"],
        "contoh": "krim wajah, sabun, lipstik, sampo, parfum",
        "pertanyaan_kunci": [
            "Nama produk dan merek",
            "Daftar komposisi (INCI) dari kemasan, bisa kirim foto",
            "Apakah ada bahan asal hewan (kolagen, plasenta, lanolin, gelatin) atau alkohol",
            "Nomor notifikasi BPOM bila ada",
        ],
        "titik_kritis": "kolagen, plasenta, lanolin, gliserin dan stearat dari lemak hewan, karmin, alkohol",
    },
    "barang_gunaan": {
        "label": "Barang gunaan",
        "klasifikasi": "Barang Gunaan",
        "rincian": ["Peralatan rumah tangga", "Kemasan dan wadah", "Pakaian dan aksesori", "Barang gunaan lainnya"],
        "contoh": "sabun cuci, kemasan, peralatan dapur, pakaian",
        "pertanyaan_kunci": [
            "Nama barang dan merek",
            "Bahan pembuat dan bahan penolong (bisa kirim foto label)",
            "Apakah ada unsur dari kulit, bulu, atau lemak hewan",
        ],
        "titik_kritis": "bahan dari kulit/bulu/lemak hewan, bahan penolong dan pelumas",
    },
    "jasa": {
        "label": "Jasa",
        "klasifikasi": "Jasa",
        "rincian": ["Penyembelihan", "Pengolahan", "Penyimpanan", "Pengemasan", "Distribusi", "Penjualan", "Penyajian"],
        "contoh": "katering, restoran, jasa penyembelihan, penyimpanan, distribusi",
        "pertanyaan_kunci": [
            "Jenis layanan yang ditawarkan",
            "Fasilitas dan peralatan yang dipakai, dan apakah terpisah dari yang non-halal",
            "Bahan yang dipakai dalam layanan (kalau ada)",
            "Untuk jasa penyembelihan: ada 2 juru sembelih halal bersertifikat?",
        ],
        "titik_kritis": "pemisahan fasilitas dan alat dari non-halal, bahan yang dipakai, juru sembelih halal",
    },
}


def daftar_kategori() -> list[dict]:
    return [{"kode": k, "label": v["label"], "contoh": v["contoh"]} for k, v in KATEGORI.items()]


def cari_kategori(teks: str) -> Optional[str]:
    """Cocokkan jawaban bebas pengguna (kode, label, atau nomor pilihan) ke kode kategori."""
    t = (teks or "").strip().lower()
    kode = list(KATEGORI)
    if t.isdigit() and 1 <= int(t) <= len(kode):
        return kode[int(t) - 1]
    for k, v in KATEGORI.items():
        if t in (k, v["label"].lower(), v["klasifikasi"].lower()):
            return k
    for k, v in KATEGORI.items():
        if k.replace("_", " ") in t or v["label"].lower() in t:
            return k
    return None
