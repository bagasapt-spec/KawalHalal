"""Tool fungsi untuk KawalHalal."""
import re

from mock_data import INGREDIENT_ALIASES, MOCK_INGREDIENTS, MOCK_PRODUCTS, MOCK_RPH_RPU


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


# ======================================================================
# Tool agentic (PRD KawalHalal): triase jalur, bedah titik kritis, bukti sembelihan.
# Semua hasil adalah KEMUNGKINAN/KESIAPAN, bukan keputusan kehalalan (BR-07, BR-16).
# ======================================================================
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
]
_E_HEWANI = {"120", "422", "430", "431", "432", "433", "434", "435", "436", "441", "470", "471", "472",
             "473", "474", "475", "477", "481", "482", "483", "542", "570", "627", "631", "635", "904"}
_KATA_NABATI_MINERAL = [
    "gula", "garam", "tepung", "air", "beras", "singkong", "tapioka", "maizena", "jagung", "kedelai",
    "kacang", "cabai", "cabe", "bawang", "merica", "lada", "kunyit", "jahe", "lengkuas", "ketumbar",
    "sayur", "wortel", "tomat", "kentang", "buah", "minyak sawit", "minyak nabati", "minyak kelapa",
    "santan", "kelapa", "soda kue", "baking soda", "kalsium karbonat", "asam sitrat", "ragi", "cuka",
    "telur", "madu", "teh", "kopi", "kakao", "cokelat bubuk",
]
_KATA_NABATI_PENANDA = ["nabati", "kedelai", "sawit", "kelapa", "soy", "vegetable", "palm"]


def _ke_int(nilai) -> int:
    try:
        return int(float(nilai))
    except (TypeError, ValueError):
        return 0


def validasi_kriteria_triase(jumlah_outlet: int, punya_nib: bool, omzet_tahunan: int) -> dict:
    """Evaluasi kemungkinan kelayakan jalur SEHATI (self-declare) versus jalur Reguler.

    Aturan (BR-01 s.d. BR-03): SEHATI tidak direkomendasikan bila outlet/fasilitas lebih dari 1,
    bila penjualan tahunan di atas Rp15 miliar, dan pengguna tanpa NIB disarankan mengurus NIB
    lebih dulu. Hasil berupa kemungkinan, bukan keputusan kelayakan akhir BPJPH.

    Args:
        jumlah_outlet: Jumlah outlet/fasilitas produksi yang dimiliki usaha (angka bulat).
        punya_nib: True jika usaha sudah memiliki NIB skala mikro atau kecil.
        omzet_tahunan: Penjualan/omzet tahunan dalam rupiah (angka bulat, mis. 500000000).

    Returns:
        dict berisi 'rekomendasi_jalur' (SEHATI, Reguler, atau Perlu NIB Dulu), 'alasan' (list
        yang merujuk kriteria), dan 'catatan'.
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

    Klasifikasi: 'aman_exempt' (nabati/mineral), 'kritis_hewani' (gelatin, lemak, emulsifier,
    kolagen, perisa, E-number turunan hewani, alkohol, dll. yang butuh bukti sumber),
    'hewani_sembelihan' (daging sapi/kambing/ayam/bebek yang butuh bukti RPH/RPU),
    'haram' (turunan babi, BR-14), atau 'tidak_dikenal' (perlu konfirmasi pengguna).
    Hasil bukan penetapan kehalalan.

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

    # Bahan kritis (basis pengetahuan mock + kata kunci + E-number)
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

    Jalur bukti mengikuti jenis hewan (BR-13): ruminansia (sapi, kambing) memakai RPH, unggas
    (ayam, bebek) memakai RPU. Status 'ada' = sertifikat ditemukan, berlaku, jenisnya sesuai, dan
    nama cocok; 'kurang' = bukti tidak ada/tidak berlaku; 'tidak_jelas' = nama berbeda atau
    sertifikat tak terverifikasi (BR-08). Yang dinilai hanya KELENGKAPAN bukti; kehalalan
    diperiksa LPH dan ditetapkan Komite Fatwa (BR-16).

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
