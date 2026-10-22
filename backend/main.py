"""FastAPI app KawalHalal."""
from dotenv import load_dotenv

load_dotenv(override=True)

import logging
import os
import httpx

from typing import Any, Dict, List, Literal, Optional

from fastapi import BackgroundTasks, Body, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
from kawal_agent.agent import CATATAN_DISCLAIMER, KawalHalalAgent, process_in_background
from kawal_agent.tools import TOOL_REGISTRY, cek_sertifikat_bpjph
from routers.agent_chat import router as agent_router
from routers.dev_ingest import router as dev_router
from routers.meta_webhook import router as meta_router
from routers.mockup import router as mockup_router
from services.storage import upload_media
from sihalal_mock import TOOLS_SIHALAL, router as sihalal_router

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

logger = logging.getLogger("kawalhalal")

app = FastAPI(title="KawalHalal API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sihalal_router)
app.include_router(meta_router)
app.include_router(dev_router)
app.include_router(mockup_router)
app.include_router(agent_router)

agent = KawalHalalAgent()


class ChatRequest(BaseModel):
    session_id: str = Field(default="sesi-umkm-001", description="ID sesi percakapan UMKM")
    pesan: str = Field(default="", description="Pesan teks dari pelaku usaha UMKM")
    berkas: Optional[str] = Field(default=None, description="Opsional: path atau nama berkas lampiran (nota/label/denah)")
    message: Optional[str] = Field(default=None, exclude=True, description="Alias kompatibilitas mundur untuk pesan")


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


@app.post("/api/demo/agen/{nama_tool}")
def jalankan_tool_agen_demo(nama_tool: str, args: Dict[str, Any] = Body(default={})):
    """Eksekusi langsung tool dari TOOL_REGISTRY (backend/tools.py) maupun TOOLS_SIHALAL lewat Swagger UI."""
    daftar_tool = {**{f.__name__: f for f in TOOLS_SIHALAL}, **TOOL_REGISTRY}
    fn = daftar_tool.get(nama_tool)
    if fn is None:
        raise HTTPException(
            status_code=404,
            detail=f"Tool {nama_tool} tidak ada. Pilihan: {', '.join(daftar_tool.keys())}.",
        )
    try:
        return fn(**(args or {}))
    except TypeError as e:
        raise HTTPException(status_code=422, detail=f"Argumen tool tidak sesuai: {e}")


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Jalankan percakapan KawalHalalAgent dan kembalikan balasan agen beserta status tool yang dipicu."""
    teks = (req.pesan if req.pesan else (req.message or "")).strip()
    if not teks and not req.berkas:
        raise HTTPException(status_code=422, detail="Field 'pesan' atau 'berkas' tidak boleh kosong.")
    return agent.proses_pertanyaan(
        prompt=teks,
        session_id=req.session_id,
        berkas=req.berkas,
    )


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


def twiml_response(text: Optional[str] = None) -> Response:
    """Return valid TwiML XML response."""
    return Response(content="<Response></Response>", media_type="application/xml")


@app.post("/api/webhook/whatsapp")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(""),
    NumMedia: int = Form(0),
    MessageSid: str = Form(...),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
):
    """
    Twilio WhatsApp Webhook:
    Receives incoming WhatsApp messages from Twilio Sandbox.
    Handles text and media fallback gracefully and always returns a valid XML TwiML response.
    """
    try:
        wa_number = From.replace("whatsapp:", "")
        warung = db.get_or_create_warung(wa_number)
        session = db.get_or_create_session(warung["id"])

        media_url_to_save: Optional[str] = None
        media_status: Optional[str] = None

        if NumMedia > 0:
            if MediaUrl0:
                try:
                    twilio_auth = (
                        (os.environ.get("TWILIO_ACCOUNT_SID", "").strip(), os.environ.get("TWILIO_AUTH_TOKEN", "").strip())
                        if os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN")
                        else None
                    )
                    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
                        media_resp = await client.get(
                            MediaUrl0,
                            auth=twilio_auth,
                        )
                        if media_resp.status_code == 200:
                            content_type = MediaContentType0 or media_resp.headers.get("content-type", "image/jpeg")
                            media_url_to_save = upload_media(
                                content=media_resp.content,
                                content_type=content_type,
                                message_id=MessageSid,
                            )
                            media_status = "ok"
                        elif media_resp.status_code == 401:
                            logger.error(
                                f"Twilio Auth Failed (401) for MessageSid {MessageSid}: {MediaUrl0}"
                            )
                            media_url_to_save = None
                            media_status = "failed"
                        else:
                            logger.error(
                                f"Twilio media download failed for MessageSid {MessageSid} with status {media_resp.status_code}: {MediaUrl0}"
                            )
                            media_url_to_save = None
                            media_status = "failed"
                except Exception as media_err:
                    logger.error(
                        f"Exception during Twilio media download for MessageSid {MessageSid}: {media_err}"
                    )
                    media_url_to_save = None
                    media_status = "failed"
            else:
                logger.error(f"NumMedia > 0 but MediaUrl0 is missing for MessageSid {MessageSid}")
                media_url_to_save = None
                media_status = "failed"
        else:
            media_status = None

        # Save message to Supabase (preserves existing text & adds media_status)
        db.save_message(
            session_id=session["id"],
            direction="in",
            body=Body,
            media_url=media_url_to_save,
            media_type=MediaContentType0 if NumMedia > 0 else None,
            twilio_sid=MessageSid,
            media_status=media_status,
        )

        # Trigger background agent loop
        background_tasks.add_task(process_in_background, session["id"], warung["id"])

    except Exception as err:
        logger.error(f"Error handling Twilio webhook: {err}", exc_info=True)

    # Always return HTTP 200 with valid TwiML on all paths, never raise error 12300 to Twilio
    return Response(content="<Response></Response>", media_type="application/xml")


@app.get("/api/dossier/{wa_number}")
def get_sihalal_dossier(wa_number: str):
    """
    Mock SIHALAL Dossier Endpoint:
    Returns structured summary of warung profile, session state, P3H approvals, and approved ingredients.
    """
    try:
        dossier = db.get_dossier_by_wa_number(wa_number)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if not dossier:
        raise HTTPException(
            status_code=404,
            detail=f"Warung dengan nomor WhatsApp '{wa_number}' tidak ditemukan.",
        )

    warung = dossier["warung"]
    sessions = dossier["sessions"]
    approvals = dossier["approvals"]
    ingredients = dossier["ingredients"]

    # Filter approved ingredients (supporting various status casing/variants: lolos, approved, verified, exempt)
    approved_ingredients = [
        ing
        for ing in ingredients
        if str(ing.get("status", "")).strip().lower() in ["lolos", "approved", "verified", "terverifikasi", "exempt"]
        or str(ing.get("override_status", "")).strip().lower() in ["lolos", "approved", "verified", "terverifikasi"]
    ]

    return {
        "status": "success",
        "warung": {
            "id": warung.get("id"),
            "nama": warung.get("nama"),
            "pemilik": warung.get("pemilik"),
            "wa_number": warung.get("wa_number"),
            "pasar": warung.get("pasar"),
            "tier": warung.get("tier"),
            "status_berkas": warung.get("status_berkas"),
            "created_at": warung.get("created_at"),
        },
        "latest_session": sessions[0] if sessions else None,
        "total_sessions": len(sessions),
        "approvals": approvals,
        "summary": {
            "total_ingredients": len(ingredients),
            "approved_count": len(approved_ingredients),
            "pending_count": len(ingredients) - len(approved_ingredients),
            "is_ready_for_sihalal": len(ingredients) > 0 and (len(approved_ingredients) == len(ingredients)),
        },
        "approved_ingredients": approved_ingredients,
        "all_ingredients": ingredients,
    }


@app.get("/health")
def health_check():
    return {"ok": True}
