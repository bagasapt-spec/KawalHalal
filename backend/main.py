"""FastAPI app KawalHalal."""
from dotenv import load_dotenv

load_dotenv()

from typing import List, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import CATATAN_DISCLAIMER, KawalHalalAgent
from sihalal_mock import router as sihalal_router

from tools import cek_sertifikat_bpjph

app = FastAPI(title="KawalHalal API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sihalal_router)

agent = KawalHalalAgent()


class ChatRequest(BaseModel):
    message: str


class VerifyRequest(BaseModel):
    nomor_sertifikat: str


class ScanResponse(BaseModel):
    mode: str
    filename: Optional[str] = None
    status_kesiapan: Literal["lengkap", "butuh_tindak_lanjut", "kritis"]
    rekomendasi_jalur: Optional[Literal["SEHATI", "Reguler", "Perlu NIB Dulu"]] = Field(
        None, description="Null bila profil usaha (outlet, NIB, omzet) belum diberikan."
    )
    alasan_jalur: List[str] = []
    daftar_bahan: List[str] = []
    celah_bukti_ditemukan: List[str] = []
    bahan_perlu_konfirmasi: List[str] = []
    alat_yang_dieksekusi: List[str] = []
    catatan_disclaimer: str = CATATAN_DISCLAIMER
    ringkasan: Optional[str] = None
    guardrail_terpicu: bool = False
    data_titik_kritis: List[dict] = []
    error: Optional[str] = None


@app.get("/")
def health():
    return {"status": "ok", "service": "KawalHalal", "mode": agent.mode}


@app.post("/api/chat")
def chat(req: ChatRequest):
    return agent.proses_pertanyaan(req.message)


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # FR-005: 10 MB


def _kosong_ke_none(v: Optional[str]) -> Optional[str]:
    return v.strip() if v and v.strip() else None


@app.post("/api/scan", response_model=ScanResponse)
async def scan(
    file: UploadFile = File(...),
    jumlah_outlet: Optional[int] = Form(None, description="Jumlah outlet/fasilitas produksi"),
    punya_nib: Optional[bool] = Form(None, description="Sudah punya NIB mikro/kecil?"),
    omzet_tahunan: Optional[int] = Form(None, description="Penjualan tahunan (Rp)"),
    jenis_hewan: Optional[str] = Form(None, description="sapi, kambing, ayam, atau bebek"),
    nama_rph_rpu: Optional[str] = Form(None, description="Nama RPH/RPU/pemasok"),
    nomor_sertifikat: Optional[str] = Form(None, description="Nomor sertifikat halal RPH/RPU/produsen"),
    pertanyaan: Optional[str] = Form(None, description="Pesan tambahan pengguna (opsional)"),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Tipe file tidak didukung. Gunakan image/jpeg, image/png, atau image/webp.",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File kosong.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran gambar melebihi batas 10 MB.")

    profil = {
        "jumlah_outlet": jumlah_outlet,
        "punya_nib": punya_nib,
        "omzet_tahunan": omzet_tahunan,
        "jenis_hewan": _kosong_ke_none(jenis_hewan),
        "nama_rph_rpu": _kosong_ke_none(nama_rph_rpu),
        "nomor_sertifikat": _kosong_ke_none(nomor_sertifikat),
    }
    hasil = await run_in_threadpool(
        agent.analisis_gambar_label, data, file.content_type, profil, _kosong_ke_none(pertanyaan)
    )
    return ScanResponse(filename=file.filename, **hasil)


@app.post("/api/verify")
def verify(req: VerifyRequest):
    return cek_sertifikat_bpjph(req.nomor_sertifikat)
