import logging
import mimetypes
from typing import Optional

from db import supabase

logger = logging.getLogger("kawalhalal.storage")

MIME_EXTENSION_MAP = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "audio/ogg": "ogg",
    "audio/amr": "amr",
    "audio/aac": "aac",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "application/pdf": "pdf",
}


def get_extension(content_type: Optional[str]) -> str:
    """Derive file extension without leading dot from content_type, defaulting to 'jpg'."""
    if not content_type:
        return "jpg"
    base_mime = content_type.split(";")[0].strip().lower()
    if base_mime in MIME_EXTENSION_MAP:
        return MIME_EXTENSION_MAP[base_mime]
    guessed = mimetypes.guess_extension(base_mime)
    if guessed:
        clean = guessed.lstrip(".").lower()
        if clean == "jpe":
            return "jpg"
        return clean
    return "jpg"


def upload_media(content: bytes, content_type: str, message_id: str) -> str:
    """
    Upload media bytes to Supabase Storage 'media' bucket at path 'whatsapp/{message_id}.{ext}'.
    Uses upsert and returns the public URL.
    """
    ext = get_extension(content_type)
    file_path = f"whatsapp/{message_id}.{ext}"

    file_options = {
        "upsert": "true",
        "content-type": content_type or "application/octet-stream",
    }

    supabase.storage.from_("media").upload(
        path=file_path,
        file=content,
        file_options=file_options,
    )

    public_url = supabase.storage.from_("media").get_public_url(file_path)
    return public_url
