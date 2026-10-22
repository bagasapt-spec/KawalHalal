"""Template berkas xlsx pengajuan halal: dibuat dari data pengguna, dan dibaca balik bila pengguna mengisi sendiri.

Aturan FR-016: sel yang tidak diberikan pengguna ditulis BELUM DIISI dan diberi warna kuning,
tidak pernah diisi karangan. Dokumen ini bukan dokumen resmi BPJPH.
"""
from pathlib import Path
from typing import Any, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

BELUM_DIISI = "BELUM DIISI"

# (kunci, label kolom, wajib)
SHEETS: list[dict] = [
    {
        "id": "produk",
        "judul": "Produk",
        "kolom": [("nama", "Nama Produk", True), ("merek", "Merek", True), ("rincian", "Rincian Produk", True)],
    },
    {
        "id": "bahan",
        "judul": "Bahan",
        "kolom": [
            ("nama", "Nama Bahan", True),
            ("jenis", "Jenis (bahan, kemasan, cleaning-agent)", True),
            ("produsen", "Produsen atau Merek", False),
            ("nomor_sertifikat", "No. Sertifikat Halal", False),
            ("pemasok", "Pemasok atau Tempat Beli", False),
            ("status_verifikasi", "Status Verifikasi (diisi sistem)", False),
        ],
    },
    {
        "id": "pembelian",
        "judul": "Pembelian dan Pemeriksaan",
        "kolom": [
            ("bahan", "Nama Bahan", True),
            ("jumlah", "Jumlah", True),
            ("satuan", "Satuan", True),
            ("tanggal", "Tanggal Pembelian (YYYY-MM-DD)", True),
            ("lokasi_periksa", "Lokasi Pemeriksaan", True),
            ("tanggal_periksa", "Tanggal Pemeriksaan (YYYY-MM-DD)", True),
        ],
    },
    {
        "id": "proses",
        "judul": "Proses Produksi",
        "kolom": [("judul", "Nama Proses", True), ("langkah", "Langkah (pisahkan dengan titik koma)", True)],
    },
    {
        "id": "penyimpanan",
        "judul": "Penyimpanan",
        "kolom": [
            ("item", "Nama Bahan atau Produk", True),
            ("jenis", "Jenis (bahan atau produk)", True),
            ("jumlah", "Jumlah", True),
            ("tanggal_masuk", "Tanggal Masuk (YYYY-MM-DD)", True),
        ],
    },
    {
        "id": "hasil",
        "judul": "Hasil Produksi",
        "kolom": [
            ("produk", "Nama Produk", True),
            ("jumlah", "Jumlah", True),
            ("tanggal_produksi", "Tanggal Produksi (YYYY-MM-DD)", True),
        ],
    },
    {
        "id": "distribusi",
        "judul": "Distribusi",
        "kolom": [("tujuan", "Tujuan atau Pembeli", True), ("produk", "Nama Produk", False), ("jumlah", "Jumlah", False)],
    },
]

# Penyesuaian per kategori: label sheet/kolom dan kolom tambahan.
VARIAN_KATEGORI: dict[str, dict] = {
    "jasa": {"produk": {"judul": "Layanan", "label": {"nama": "Nama Layanan", "merek": "Nama Usaha/Merek", "rincian": "Jenis Layanan"}}},
    "kosmetik": {
        "bahan": {
            "tambahan": [("fungsi", "Fungsi Bahan", False), ("asal", "Asal Bahan (nabati, hewani, sintetis)", True)],
        }
    },
}

KUNCI_BAGIAN = {s["id"]: s for s in SHEETS}


def _sheet(sheet_id: str, kategori: Optional[str]) -> dict:
    s = KUNCI_BAGIAN[sheet_id]
    varian = VARIAN_KATEGORI.get(kategori or "", {}).get(sheet_id, {})
    kolom = list(s["kolom"]) + list(varian.get("tambahan", []))
    labels = varian.get("label", {})
    kolom = [(k, labels.get(k, label), wajib) for k, label, wajib in kolom]
    return {"id": sheet_id, "judul": varian.get("judul", s["judul"]), "kolom": kolom}


def skema_kolom(kategori: Optional[str] = None) -> dict[str, list[dict]]:
    """Kolom tiap sheet untuk kategori tertentu, dipakai agen untuk tahu isian apa yang masih dibutuhkan."""
    out = {}
    for s in SHEETS:
        sh = _sheet(s["id"], kategori)
        out[s["id"]] = [{"kunci": k, "label": label, "wajib": wajib} for k, label, wajib in sh["kolom"]]
    return out


def dok_kosong() -> dict[str, list[dict]]:
    return {s["id"]: [] for s in SHEETS}


def bagian_kosong(dok: dict, kategori: Optional[str] = None) -> list[str]:
    """Daftar sheet wajib yang belum punya baris sama sekali."""
    return [_sheet(s["id"], kategori)["judul"] for s in SHEETS if s["id"] != "distribusi" and not dok.get(s["id"])]


def sel_kosong_wajib(dok: dict, kategori: Optional[str] = None) -> list[str]:
    """Rincian sel wajib yang kosong, misalnya 'Bahan baris 2: Pemasok atau Tempat Beli'."""
    hasil = []
    for s in SHEETS:
        sh = _sheet(s["id"], kategori)
        for i, baris in enumerate(dok.get(s["id"], []), start=1):
            for kunci, label, wajib in sh["kolom"]:
                if wajib and _kosong(baris.get(kunci)):
                    hasil.append(f"{sh['judul']} baris {i}: {label}")
    return hasil


def _kosong(v: Any) -> bool:
    return v is None or str(v).strip() == "" or str(v).strip().upper() == BELUM_DIISI


def buat_xlsx(dok: dict, kategori: Optional[str], pelaku: dict, tujuan: Path) -> dict:
    wb = Workbook()
    petunjuk = wb.active
    petunjuk.title = "Petunjuk"
    baris_petunjuk = [
        ("Berkas Persiapan Pengajuan Sertifikasi Halal", True),
        (f"Usaha: {pelaku.get('namaUsaha', '-')}", False),
        (f"NIB: {pelaku.get('nib') or BELUM_DIISI}", False),
        (f"Kategori: {kategori or BELUM_DIISI}", False),
        ("", False),
        ("Sel berwarna kuning bertuliskan BELUM DIISI berarti data itu belum Anda berikan. Lengkapi lewat KawalHalal atau isi langsung di berkas ini.", False),
        ("Berkas ini disusun dari data yang Anda berikan. KawalHalal tidak menetapkan kehalalan dan tidak menandatangani apa pun atas nama Anda.", False),
        ("Penetapan kehalalan dilakukan lewat proses BPJPH, LPH, dan Komite Fatwa. Berkas ini bukan dokumen resmi BPJPH.", False),
    ]
    for i, (teks, tebal) in enumerate(baris_petunjuk, start=1):
        c = petunjuk.cell(row=i, column=1, value=teks)
        c.font = Font(bold=tebal, size=14 if tebal else 11)
        c.alignment = Alignment(wrap_text=True, vertical="top")
    petunjuk.column_dimensions["A"].width = 110

    kuning = PatternFill("solid", fgColor="FFF59D")
    header_fill = PatternFill("solid", fgColor="1B5E20")
    jumlah_kosong = 0
    for s in SHEETS:
        sh = _sheet(s["id"], kategori)
        ws = wb.create_sheet(title=sh["judul"][:31])
        for j, (_, label, wajib) in enumerate(sh["kolom"], start=1):
            c = ws.cell(row=1, column=j, value=label + (" *" if wajib else ""))
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = header_fill
            c.alignment = Alignment(wrap_text=True, vertical="center")
            ws.column_dimensions[get_column_letter(j)].width = 30
        for i, baris in enumerate(dok.get(s["id"], []), start=2):
            for j, (kunci, _, wajib) in enumerate(sh["kolom"], start=1):
                nilai = baris.get(kunci)
                if isinstance(nilai, list):
                    nilai = "; ".join(str(x) for x in nilai)
                if _kosong(nilai):
                    if wajib:
                        c = ws.cell(row=i, column=j, value=BELUM_DIISI)
                        c.fill = kuning
                        jumlah_kosong += 1
                    continue
                ws.cell(row=i, column=j, value=nilai).alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    wb.save(tujuan)
    return {"sel_belum_diisi": jumlah_kosong, "bagian_kosong": bagian_kosong(dok, kategori)}


def impor_xlsx(path: Path, kategori: Optional[str] = None) -> dict[str, list[dict]]:
    """Baca berkas hasil buat_xlsx (atau salinan yang diisi pengguna) kembali menjadi data kerja."""
    wb = load_workbook(path, data_only=True)
    dok = dok_kosong()
    for s in SHEETS:
        sh = _sheet(s["id"], kategori)
        if sh["judul"][:31] not in wb.sheetnames:
            continue
        ws = wb[sh["judul"][:31]]
        peta = {}  # indeks kolom -> kunci, dicocokkan lewat label tanpa tanda bintang
        for j, c in enumerate(ws[1], start=0):
            if c.value:
                label = str(c.value).replace(" *", "").strip()
                for kunci, lab, _ in sh["kolom"]:
                    if lab == label:
                        peta[j] = kunci
        for baris in ws.iter_rows(min_row=2, values_only=True):
            if not any(v not in (None, "") for v in baris):
                continue
            item = {}
            for j, v in enumerate(baris):
                kunci = peta.get(j)
                if kunci is None or _kosong(v):
                    continue
                item[kunci] = v if isinstance(v, (int, float)) else str(v).strip()
            if item:
                dok[s["id"]].append(item)
    return dok
