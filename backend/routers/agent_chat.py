"""Endpoint agen: chat web/demo (cadangan bila WhatsApp bermasalah, NFR-006), unduh berkas, dan reset sesi."""
import os
import re
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse

from kawal_agent import operator_ui, tautan
from kawal_agent.agent import di_loop_agen, hapus_sesi, jalankan_di_loop_agen, lihat_state
from kawal_agent.tools import GENERATED_DIR

router = APIRouter(prefix="/api/agent", tags=["Agen KawalHalal"])

BATAS_BYTES = 15 * 1024 * 1024
UKURAN_MAKS_JUMLAH = 6
JENIS = {
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"), ".jpeg": ("image/jpeg", b"\xff\xd8\xff"), ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".webp": ("image/webp", b"RIFF"), ".pdf": ("application/pdf", b"%PDF-"),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK\x03\x04"),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK\x03\x04"),
}


def _kunci(x_dev_key: Optional[str]) -> None:
    kunci = os.environ.get("DEV_INGEST_KEY", "").strip()
    if not kunci:
        raise HTTPException(404, "Endpoint dinonaktifkan.")
    if not x_dev_key or x_dev_key.strip() != kunci:
        raise HTTPException(403, "X-Dev-Key tidak valid.")


async def _baca(f: UploadFile) -> dict:
    nama = os.path.basename(f.filename or "").strip()
    ext = Path(nama).suffix.lower()
    if ext not in JENIS:
        raise HTTPException(415, f"Format '{ext}' tidak didukung. Gunakan foto (jpg, png, webp) atau dokumen (pdf, docx, xlsx).")
    data = await f.read(BATAS_BYTES + 1)
    if not data:
        raise HTTPException(400, f"Berkas {nama} kosong.")
    if len(data) > BATAS_BYTES:
        raise HTTPException(413, f"Berkas {nama} melebihi 15 MB.")
    mime, magic = JENIS[ext]
    if not data.startswith(magic) or (ext == ".webp" and data[8:12] != b"WEBP"):
        raise HTTPException(400, f"Isi berkas {nama} tidak sesuai ekstensinya.")
    return {"nama": nama, "mime": mime, "data": data}


@router.post("/chat")
async def chat(
    user_id: str = Form(..., description="Nomor WhatsApp atau id pengguna demo"),
    pesan: str = Form(""),
    files: List[UploadFile] = File(default=[]),
    x_dev_key: Optional[str] = Header(None, alias="X-Dev-Key"),
):
    _kunci(x_dev_key)
    if not re.sub(r"\D", "", user_id):
        raise HTTPException(422, "user_id harus memuat nomor telepon.")
    if len(files) > UKURAN_MAKS_JUMLAH:
        raise HTTPException(413, f"Maksimal {UKURAN_MAKS_JUMLAH} berkas per pesan.")
    lampiran = [await _baca(f) for f in files]
    if not pesan.strip() and not lampiran:
        raise HTTPException(422, "Kirim pesan teks atau lampiran.")
    return await jalankan_di_loop_agen(re.sub(r"\D", "", user_id), pesan, lampiran)


@router.get("/berkas/{path:path}")
def unduh(path: str, t: str = ""):
    if not tautan.valid(path, t):
        raise HTTPException(403, "Tautan tidak valid.")
    akar = GENERATED_DIR.resolve()
    f = (akar / path).resolve()
    if akar not in f.parents or not f.is_file():
        raise HTTPException(404, "Berkas tidak ditemukan.")
    return FileResponse(f, filename=f.name)


@router.get("/state/{user_id}")
async def state(user_id: str, x_dev_key: Optional[str] = Header(None, alias="X-Dev-Key")):
    _kunci(x_dev_key)
    st = await di_loop_agen(lihat_state(re.sub(r"\D", "", user_id)))
    return {k: v for k, v in st.items() if k != "berkas_masuk"}


@router.delete("/sesi/{user_id}")
async def reset(user_id: str, x_dev_key: Optional[str] = Header(None, alias="X-Dev-Key")):
    _kunci(x_dev_key)
    return {"dihapus": await di_loop_agen(hapus_sesi(re.sub(r"\D", "", user_id)))}


@router.get("/operator/{pengajuan_id}")
def operator(pengajuan_id: str, x_dev_key: Optional[str] = Header(None, alias="X-Dev-Key")):
    """Log aksi operator Kala untuk satu pengajuan: apa yang dibuka, diisi, dan disimpan lewat formulir."""
    _kunci(x_dev_key)
    return {"aktif": operator_ui.aktif(), "sibuk": operator_ui.sibuk(pengajuan_id), "log": operator_ui.riwayat(pengajuan_id)}
