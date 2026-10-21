from dotenv import load_dotenv

load_dotenv()

import logging
import os
from typing import Optional

logger = logging.getLogger("kawalhalal.db")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY")

supabase = None
if SUPABASE_URL and SUPABASE_SECRET_KEY:
    try:
        from supabase import create_client

        supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
    except Exception as e:
        logger.warning("Gagal inisialisasi Supabase client (%s). supabase = None.", e)
        print(f"[WARNING] Gagal inisialisasi Supabase client: {e}. supabase = None.")
else:
    logger.warning("SUPABASE_URL atau SUPABASE_SECRET_KEY belum diisi. supabase = None.")
    print("[WARNING] SUPABASE_URL atau SUPABASE_SECRET_KEY belum diisi. supabase = None.")

def require_supabase():
    """Return the Supabase client or raise a clear error if it is not configured."""
    if supabase is None:
        raise RuntimeError(
            "Supabase belum dikonfigurasi: isi SUPABASE_URL dan SUPABASE_SECRET_KEY di backend/.env."
        )
    return supabase


# Export storage helpers for backwards compatibility
from services.storage import get_extension, upload_media  # noqa: E402


def get_or_create_warung(wa_number: str) -> dict:
    clean_number = wa_number.replace("whatsapp:", "").strip()
    res = require_supabase().table("warung").select("*").eq("wa_number", clean_number).limit(1).execute()
    if res.data:
        return res.data[0]

    # Check with/without '+' so both Twilio (+62...) and Meta (62...) match the same warung
    alt_number = f"+{clean_number}" if not clean_number.startswith("+") else clean_number.lstrip("+")
    res_alt = require_supabase().table("warung").select("*").eq("wa_number", alt_number).limit(1).execute()
    if res_alt.data:
        return res_alt.data[0]

    created = require_supabase().table("warung").insert(
        {"nama": "Warung baru", "wa_number": clean_number}
    ).execute()
    return created.data[0]


def get_or_create_session(warung_id: str) -> dict:
    res = (
        require_supabase().table("sessions")
        .select("*")
        .eq("warung_id", warung_id)
        .neq("state", "selesai")
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]
    created = require_supabase().table("sessions").insert({"warung_id": warung_id}).execute()
    return created.data[0]


def save_message(
    session_id: str,
    direction: str,
    body: str,
    media_url: Optional[str],
    media_type: Optional[str],
    twilio_sid: str,
    media_status: Optional[str] = None,
) -> dict:
    # twilio_sid unik: kalau Twilio atau Meta kirim ulang webhook yang sama, tidak tersimpan dobel
    payload = {
        "session_id": session_id,
        "direction": direction,
        "body": body,
        "media_url": media_url,
        "media_type": media_type,
        "twilio_sid": twilio_sid,
    }
    if media_status is not None:
        payload["media_status"] = media_status

    try:
        res = (
            require_supabase().table("messages")
            .upsert(
                payload,
                on_conflict="twilio_sid",
                ignore_duplicates=True,
            )
            .execute()
        )
        return res.data[0] if res.data else {}
    except Exception as e:
        # Fallback if media_status column is not yet created in Supabase
        if "media_status" in payload and "media_status" in str(e):
            logger.warning(
                "media_status column does not exist yet in Supabase messages table. Retrying save without it."
            )
            payload.pop("media_status", None)
            res = (
                require_supabase().table("messages")
                .upsert(
                    payload,
                    on_conflict="twilio_sid",
                    ignore_duplicates=True,
                )
                .execute()
            )
            return res.data[0] if res.data else {}
        raise


def get_dossier_by_wa_number(wa_number: str) -> Optional[dict]:
    """
    Query warung, sessions, approvals, and ingredients for a given WhatsApp number.
    Handles optional '+' or 'whatsapp:' prefix formatting.
    """
    clean_wa = wa_number.replace("whatsapp:", "").strip()
    res = require_supabase().table("warung").select("*").eq("wa_number", clean_wa).limit(1).execute()
    warung = res.data[0] if res.data else None

    if not warung:
        alt_wa = f"+{clean_wa}" if not clean_wa.startswith("+") else clean_wa.lstrip("+")
        res_alt = require_supabase().table("warung").select("*").eq("wa_number", alt_wa).limit(1).execute()
        warung = res_alt.data[0] if res_alt.data else None

    if not warung:
        return None

    warung_id = warung["id"]

    sessions_res = (
        require_supabase().table("sessions")
        .select("*")
        .eq("warung_id", warung_id)
        .order("updated_at", desc=True)
        .execute()
    )

    approvals_res = (
        require_supabase().table("approvals")
        .select("*")
        .eq("warung_id", warung_id)
        .order("created_at", desc=True)
        .execute()
    )

    ingredients_res = (
        require_supabase().table("ingredients")
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