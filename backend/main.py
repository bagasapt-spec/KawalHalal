import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx

from agent import process_in_background
import db
from routers.dev_ingest import router as dev_router
from routers.meta_webhook import router as meta_router
from routers.mockup import router as mockup_router
from services.storage import upload_media

load_dotenv()

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

logger = logging.getLogger("kawalhalal")

app = FastAPI(title="KawalHalal Backend API", version="1.0.0")

# Enable CORS for all origins (hackathon demo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Webhook, Dev & Mockup routers
app.include_router(meta_router)
app.include_router(dev_router)
app.include_router(mockup_router)


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
    dossier = db.get_dossier_by_wa_number(wa_number)
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
def health():
    return {"ok": True}