import mimetypes
import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

MIME_EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "audio/ogg": ".ogg",
    "audio/amr": ".amr",
    "audio/aac": ".aac",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "application/pdf": ".pdf",
}


def get_extension_from_mime(mime_type: Optional[str]) -> str:
    """Extract file extension from MIME content type."""
    if not mime_type:
        return ""
    base_mime = mime_type.split(";")[0].strip().lower()
    return MIME_EXTENSION_MAP.get(base_mime) or mimetypes.guess_extension(base_mime) or ""


def upload_media(file_bytes: bytes, content_type: Optional[str] = None) -> str:
    """
    Upload raw media byte content to the Supabase Storage 'media' bucket
    using a unique UUID filename and return the public URL.
    """
    ext = get_extension_from_mime(content_type)
    filename = f"{uuid.uuid4()}{ext}"

    file_options = {"upsert": "true"}
    if content_type:
        file_options["content-type"] = content_type

    supabase.storage.from_("media").upload(
        path=filename,
        file=file_bytes,
        file_options=file_options,
    )
    return supabase.storage.from_("media").get_public_url(filename)


def get_or_create_warung(wa_number: str) -> dict:
    res = supabase.table("warung").select("*").eq("wa_number", wa_number).limit(1).execute()
    if res.data:
        return res.data[0]
    created = supabase.table("warung").insert(
        {"nama": "Warung baru", "wa_number": wa_number}
    ).execute()
    return created.data[0]


def get_or_create_session(warung_id: str) -> dict:
    res = (
        supabase.table("sessions")
        .select("*")
        .eq("warung_id", warung_id)
        .neq("state", "selesai")
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]
    created = supabase.table("sessions").insert({"warung_id": warung_id}).execute()
    return created.data[0]


def save_message(session_id, direction, body, media_url, media_type, twilio_sid):
    # twilio_sid unik: kalau Twilio kirim ulang webhook yang sama, tidak tersimpan dobel
    supabase.table("messages").upsert(
        {
            "session_id": session_id,
            "direction": direction,
            "body": body,
            "media_url": media_url,
            "media_type": media_type,
            "twilio_sid": twilio_sid,
        },
        on_conflict="twilio_sid",
        ignore_duplicates=True,
    ).execute()


def get_dossier_by_wa_number(wa_number: str) -> Optional[dict]:
    """
    Query warung, sessions, approvals, and ingredients for a given WhatsApp number.
    Handles optional '+' or 'whatsapp:' prefix formatting.
    """
    clean_wa = wa_number.replace("whatsapp:", "").strip()
    res = supabase.table("warung").select("*").eq("wa_number", clean_wa).limit(1).execute()
    warung = res.data[0] if res.data else None

    if not warung:
        alt_wa = f"+{clean_wa}" if not clean_wa.startswith("+") else clean_wa.lstrip("+")
        res_alt = supabase.table("warung").select("*").eq("wa_number", alt_wa).limit(1).execute()
        warung = res_alt.data[0] if res_alt.data else None

    if not warung:
        return None

    warung_id = warung["id"]

    sessions_res = (
        supabase.table("sessions")
        .select("*")
        .eq("warung_id", warung_id)
        .order("updated_at", desc=True)
        .execute()
    )

    approvals_res = (
        supabase.table("approvals")
        .select("*")
        .eq("warung_id", warung_id)
        .order("created_at", desc=True)
        .execute()
    )

    ingredients_res = (
        supabase.table("ingredients")
        .select("*")
        .eq("warung_id", warung_id)
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "warung": warung,
        "sessions": sessions_res.data or [],
        "approvals": approvals_res.data or [],
        "ingredients": ingredients_res.data or [],
    }