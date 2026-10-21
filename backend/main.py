import logging
import os
from typing import Optional
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx

import db

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


def twiml_response(text: Optional[str] = None) -> Response:
    """Return TwiML XML response. If text is None or empty, returns an empty <Response></Response>."""
    if text:
        content = f"<Message>{escape(text)}</Message>"
    else:
        content = ""
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response>{content}</Response>'
    return Response(content=xml, media_type="application/xml")


def process_in_background(session_id: str, warung_id: str):
    # STUB: nanti diganti process_event(...) dari agen Bagas
    # lalu balasan dikirim lewat Twilio REST API
    pass


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
    wa_number = From.replace("whatsapp:", "")
    warung = db.get_or_create_warung(wa_number)
    session = db.get_or_create_session(warung["id"])

    # Handle incoming media (download via httpx with Twilio HTTP Basic Auth & upload raw bytes to Supabase Storage)
    media_url_to_save: Optional[str] = None
    if NumMedia > 0 and MediaUrl0:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                media_resp = await client.get(
                    MediaUrl0,
                    auth=(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"]),
                )
                if media_resp.status_code == 200:
                    content_type = MediaContentType0 or media_resp.headers.get("content-type")
                    media_url_to_save = db.upload_media(media_resp.content, content_type)
                elif media_resp.status_code == 401:
                    logger.error(
                        f"Twilio Auth Failed: Check SID and Token ({media_resp.status_code}): {MediaUrl0}"
                    )
                    media_url_to_save = MediaUrl0
                else:
                    logger.warning(
                        f"Failed to fetch media from Twilio ({media_resp.status_code}): {MediaUrl0}"
                    )
                    media_url_to_save = MediaUrl0
        except Exception as e:
            logger.error(f"Error downloading/uploading media: {e}")
            media_url_to_save = MediaUrl0

    db.save_message(
        session["id"],
        "in",
        Body,
        media_url_to_save,
        MediaContentType0 if NumMedia > 0 else None,
        MessageSid,
    )

    background_tasks.add_task(process_in_background, session["id"], warung["id"])

    # Return empty TwiML response; outgoing agent responses are dispatched asynchronously via Twilio REST API
    return twiml_response()


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