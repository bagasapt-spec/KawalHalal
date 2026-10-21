"""FastAPI app KawalHalal."""
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import KawalHalalAgent
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


@app.get("/")
def health():
    return {"status": "ok", "service": "KawalHalal", "mode": agent.mode}


@app.post("/api/chat")
def chat(req: ChatRequest):
    return agent.proses_pertanyaan(req.message)


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@app.post("/api/scan")
async def scan(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Tipe file tidak didukung. Gunakan image/jpeg, image/png, atau image/webp.",
        )
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="File kosong.")
    hasil = await run_in_threadpool(agent.analisis_gambar_label, data, file.content_type)
    return {
        "mode": hasil["mode"],
        "filename": file.filename,
        "hasil_analisis": hasil.get("hasil_analisis"),
        "data_titik_kritis": hasil.get("data_titik_kritis"),
        **({"error": hasil["error"]} if "error" in hasil else {}),
    }


@app.post("/api/verify")
def verify(req: VerifyRequest):
    return cek_sertifikat_bpjph(req.nomor_sertifikat)
