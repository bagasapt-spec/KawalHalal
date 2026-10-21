"""Data mock untuk KawalHalal (simulasi database BPJPH & basis pengetahuan bahan kritis)."""

MOCK_PRODUCTS = {
    "ID3111000012345": {
        "nama_produk": "Mie Instan Goreng Original",
        "produsen": "PT Sumber Pangan Nusantara",
        "nomor_sertifikat": "ID3111000012345",
        "tanggal_kadaluarsa": "2027-08-15",
        "status": "Berlaku",
    },
    "ID0011000000001": {
        "nama_produk": "Susu UHT Cokelat",
        "produsen": "PT Nusantara Dairy Indonesia",
        "nomor_sertifikat": "ID0011000000001",
        "tanggal_kadaluarsa": "2028-01-30",
        "status": "Berlaku",
    },
    "ID2210000067890": {
        "nama_produk": "Biskuit Krim Vanila",
        "produsen": "PT Manis Lestari",
        "nomor_sertifikat": "ID2210000067890",
        "tanggal_kadaluarsa": "2024-03-10",
        "status": "Kadaluarsa",
    },
    "ID4410000054321": {
        "nama_produk": "Permen Jelly Buah",
        "produsen": "PT Kenyal Sejahtera",
        "nomor_sertifikat": "ID4410000054321",
        "tanggal_kadaluarsa": "2025-05-20",
        "status": "Dicabut",
    },
}

MOCK_INGREDIENTS = {
    "e471": {
        "nama": "E471 (Mono- dan digliserida asam lemak)",
        "status": "Syubhat",
        "alasan": "Dapat bersumber dari lemak hewani (termasuk babi) atau nabati. Perlu sertifikat halal atau penelusuran sumber.",
        "sumber": "Fatwa MUI & panduan LPPOM MUI tentang bahan emulsifier",
    },
    "e120": {
        "nama": "E120 (Karmin / Cochineal)",
        "status": "Halal bersyarat",
        "alasan": "Pewarna dari serangga cochineal. Menurut MUI dibolehkan (halal) dengan syarat tidak membahayakan dan tidak menjijikkan bagi konsumen; ulama berbeda pendapat.",
        "sumber": "Fatwa MUI No. 33 Tahun 2011 tentang penggunaan serangga cochineal",
    },
    "gelatin": {
        "nama": "Gelatin",
        "status": "Kritis",
        "alasan": "Umumnya berasal dari kulit/tulang babi atau sapi. Halal hanya jika dari hewan halal yang disembelih secara syar'i.",
        "sumber": "Fatwa MUI No. 26 Tahun 2013 tentang standar kehalalan gelatin",
    },
    "alkohol": {
        "nama": "Alkohol (Etanol)",
        "status": "Kritis",
        "alasan": "Haram bila berasal dari industri khamar. Etanol dari non-khamar dengan kadar tertentu dapat dibolehkan; perlu verifikasi sumber.",
        "sumber": "Fatwa MUI No. 10 Tahun 2018 tentang produk makanan/minuman mengandung alkohol/etanol",
    },
    "e904": {
        "nama": "E904 (Shellac)",
        "status": "Syubhat",
        "alasan": "Resin dari serangga lac; kehalalan perlu dikonfirmasi proses pelarut dan pengolahannya.",
        "sumber": "Panduan LPPOM MUI bahan tambahan pangan",
    },
    "lemak babi": {
        "nama": "Lemak babi",
        "status": "Haram",
        "alasan": "Berasal dari babi, haram secara tegas (QS. Al-Baqarah: 173).",
        "sumber": "QS. Al-Baqarah: 173",
    },
}

# Alias nama umum -> kunci MOCK_INGREDIENTS
INGREDIENT_ALIASES = {
    "e-471": "e471",
    "e 471": "e471",
    "mono dan digliserida": "e471",
    "emulsifier e471": "e471",
    "e-120": "e120",
    "e 120": "e120",
    "karmin": "e120",
    "carmine": "e120",
    "cochineal": "e120",
    "gelatine": "gelatin",
    "gelatin sapi": "gelatin",
    "etanol": "alkohol",
    "ethanol": "alkohol",
    "alcohol": "alkohol",
    "e-904": "e904",
    "shellac": "e904",
    "lard": "lemak babi",
}
