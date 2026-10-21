import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])


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