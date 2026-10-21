from xml.sax.saxutils import escape

from fastapi import FastAPI, Form, BackgroundTasks, Response
from typing import Optional
import db

app = FastAPI()


def twiml_reply(text: str) -> Response:
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escape(text)}</Message></Response>"
    )
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

    db.save_message(
        session["id"],
        "in",
        Body,
        MediaUrl0 if NumMedia > 0 else None,
        MediaContentType0 if NumMedia > 0 else None,
        MessageSid,
    )

    background_tasks.add_task(process_in_background, session["id"], warung["id"])
    return twiml_reply("Pesan diterima. Agen KawalHalal akan segera memproses.")


@app.get("/health")
def health():
    return {"ok": True}