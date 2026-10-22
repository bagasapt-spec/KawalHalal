"""Penelusuran sertifikat halal produk dan pemasok daging (data simulasi, lihat data/registri_mock.json).

Semua hasil adalah status administratif registri, bukan penetapan kehalalan (BR-07, BR-16).
"""
import json
import re
from pathlib import Path
from typing import Optional

SUMBER_DATA = "Registri simulasi demo (bukan data resmi BPJPH)"
_BERKAS = Path(__file__).resolve().parent.parent / "data" / "registri_mock.json"

with open(_BERKAS, encoding="utf-8") as f:
    _DATA = json.load(f)

PRODUK: list[dict] = _DATA["produk"]
PEMASOK_DAGING: list[dict] = _DATA["pemasok_daging"]

_STOP = {"dan", "cap", "merek", "produk", "pt", "cv", "rasa", "instan"}


def _token(teks: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (teks or "").lower()) if t not in _STOP and len(t) > 1}


def cari_produk(query: str, kategori: Optional[str] = None, batas: int = 3) -> list[dict]:
    """Cari produk bersertifikat berdasarkan nama, merek, atau produsen. Urut dari kecocokan terbaik."""
    q = _token(query)
    if not q:
        return []
    hasil = []
    for p in PRODUK:
        if kategori and p["kategori"] != kategori:
            continue
        bahan = _token(f"{p['nama_produk']} {p['merek']} {p['produsen']}")
        irisan = q & bahan
        if not irisan:
            continue
        skor = len(irisan) / len(q)
        if _token(p["merek"]) & q:
            skor += 0.5
        hasil.append((skor, p))
    hasil.sort(key=lambda x: x[0], reverse=True)
    return [{**p, "skor_kecocokan": round(min(s, 1.5) / 1.5, 2)} for s, p in hasil[:batas]]


def cari_nomor(nomor: str) -> Optional[dict]:
    n = re.sub(r"[\s\-]", "", nomor or "").upper()
    return next((p for p in PRODUK if p["nomor_sertifikat"] == n), None)


# Kata umum pada nama lapak tidak boleh dianggap identitas: "Lapak Ayam" cocok dengan semua lapak ayam.
_UMUM_LAPAK = _STOP | {"lapak", "toko", "kios", "pasar", "daging", "ayam", "sapi", "kambing", "bebek", "segar", "pak", "bu", "ibu", "haji", "bapak", "mitra"}


def cari_pemasok_daging(nama_lapak: str, pasar: str = "", jenis_hewan: str = "") -> list[dict]:
    """Cocokkan nama lapak ke registri. Hanya kata identitas (nama orang/lapak) yang dihitung.

    Hasil diurutkan dari yang terbaik; tiap item punya 'skor'. Bila dua lapak sama kuat, pemanggil
    harus menganggapnya ambigu dan tidak memilih otomatis.
    """
    q = _token(nama_lapak) - _UMUM_LAPAK
    hasil = []
    for p in PEMASOK_DAGING:
        if jenis_hewan and jenis_hewan.lower() not in p["hewan"]:
            continue
        irisan = q & (_token(p["lapak"]) - _UMUM_LAPAK)
        if not irisan:
            continue
        skor = len(irisan) / len(q)
        if pasar and _token(pasar) & _token(p["pasar"]):
            skor += 0.3
        hasil.append((skor, p))
    hasil.sort(key=lambda x: x[0], reverse=True)
    return [{**p, "skor": round(s, 2)} for s, p in hasil[:3]]
