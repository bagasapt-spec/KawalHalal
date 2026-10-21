"""Tool fungsi untuk KawalHalal."""
import re

from mock_data import INGREDIENT_ALIASES, MOCK_INGREDIENTS, MOCK_PRODUCTS


def cek_sertifikat_bpjph(nomor_sertifikat: str) -> dict:
    """Validasi nomor sertifikat halal ke database BPJPH (mock).

    Args:
        nomor_sertifikat: Nomor sertifikat halal, contoh ID3111000012345.

    Returns:
        dict berisi 'ditemukan', 'status', dan detail produk bila ada.
    """
    nomor = re.sub(r"[\s\-]", "", (nomor_sertifikat or "")).upper()
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
    # Pencocokan substring (kunci terpanjang lebih dulu)
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
