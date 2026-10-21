import hashlib
import hmac
import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Header, Query, Request, Response
import httpx

from agent import process_in_background
import db
from services.storage import upload_media

logger = logging.getLogger("kawalhalal.meta")

router = APIRouter()


def get_meta_config() -> Dict[str, str]:
    """Retrieve and sanitize Meta environment variables."""
    return {
        "access_token": os.environ.get("META_ACCESS_TOKEN", "").strip(),
        "phone_number_id": os.environ.get("META_PHONE_NUMBER_ID", "").strip(),
        "verify_token": os.environ.get("META_VERIFY_TOKEN", "").strip(),
        "graph_version": (os.environ.get("META_GRAPH_VERSION", "v25.0") or "v25.0").strip(),
        "app_secret": os.environ.get("META_APP_SECRET", "").strip(),
    }


def verify_signature(raw_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Verify X-Hub-Signature-256 if META_APP_SECRET is set.
    Skips verification silently if META_APP_SECRET is not configured.
    """
    config = get_meta_config()
    app_secret = config["app_secret"]
    if not app_secret or app_secret == "your-meta-app-secret-optional":
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 header")
        return False

    expected_sig = signature_header.split("sha256=")[1].strip()
    computed_sig = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_sig, computed_sig)


async def send_text(to: str, text: str) -> Optional[Dict[str, Any]]:
    """
    Send an outgoing WhatsApp text message via Meta Cloud API:
    POST https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages
    """
    config = get_meta_config()
    access_token = config["access_token"]
    phone_number_id = config["phone_number_id"]
    graph_version = config["graph_version"]

    if not access_token or not phone_number_id:
        logger.warning("Meta send_text skipped: META_ACCESS_TOKEN or META_PHONE_NUMBER_ID not set.")
        return None

    clean_to = to.replace("whatsapp:", "").lstrip("+").strip()
    url = f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_to,
        "type": "text",
        "text": {"body": text},
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            logger.info(f"Meta send_text response ({resp.status_code}): {resp.text}")
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"Meta send_text failed ({resp.status_code}): {resp.text}")
                return None
    except Exception as e:
        logger.error(f"Meta send_text exception: {e}")
        return None


async def _download_meta_media(media_id: str) -> tuple[Optional[bytes], Optional[str]]:
    """
    Download media from Meta Cloud API in two steps:
    1. GET https://graph.facebook.com/{version}/{media_id} -> retrieve media URL and MIME type
    2. GET media_url with same Bearer token and follow_redirects=True -> retrieve raw bytes
    """
    config = get_meta_config()
    access_token = config["access_token"]
    graph_version = config["graph_version"]

    if not access_token:
        logger.error("Meta media download failed: META_ACCESS_TOKEN is not configured.")
        return None, None

    headers = {"Authorization": f"Bearer {access_token}"}
    info_url = f"https://graph.facebook.com/{graph_version}/{media_id}"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            # Step 1: Get media URL
            info_resp = await client.get(info_url, headers=headers)
            if info_resp.status_code != 200:
                logger.error(f"Meta get media info failed ({info_resp.status_code}): {info_resp.text}")
                return None, None

            info_data = info_resp.json()
            media_url = info_data.get("url")
            mime_type = info_data.get("mime_type", "image/jpeg")

            if not media_url:
                logger.error(f"Meta media info missing 'url': {info_data}")
                return None, None

            # Step 2: Download raw binary bytes
            download_resp = await client.get(media_url, headers=headers)
            if download_resp.status_code != 200:
                logger.error(
                    f"Meta download media bytes failed ({download_resp.status_code}) for media_id={media_id}"
                )
                return None, None

            return download_resp.content, mime_type
    except Exception as e:
        logger.error(f"Meta download exception for media_id {media_id}: {e}")
        return None, None


async def process_single_meta_message(msg: Dict[str, Any]):
    """
    Process an individual WhatsApp message received from Meta Cloud API.
    Handles text, image, and other types, saving to Supabase and triggering the agent.
    """
    msg_id = msg.get("id", "")
    sender = msg.get("from", "").strip()
    msg_type = msg.get("type", "unknown")

    logger.info(f"Processing Meta message id={msg_id}, sender={sender}, type={msg_type}")

    warung = db.get_or_create_warung(sender)
    session = db.get_or_create_session(warung["id"])

    body_text = ""
    media_url: Optional[str] = None
    media_status: Optional[str] = None
    media_type: Optional[str] = None

    if msg_type == "text":
        body_text = msg.get("text", {}).get("body", "")
        media_url = None
        media_status = None
        media_type = None

    elif msg_type == "image":
        img_info = msg.get("image", {})
        media_id = img_info.get("id")
        body_text = img_info.get("caption", "")

        if media_id:
            raw_bytes, detected_mime = await _download_meta_media(media_id)
            if raw_bytes:
                try:
                    media_type = detected_mime or img_info.get("mime_type", "image/jpeg")
                    media_url = upload_media(
                        content=raw_bytes,
                        content_type=media_type,
                        message_id=msg_id,
                    )
                    media_status = "ok"
                except Exception as e:
                    logger.error(f"Failed to upload Meta image to Supabase Storage: {e}")
                    media_url = None
                    media_status = "failed"
            else:
                media_url = None
                media_status = "failed"
        else:
            media_url = None
            media_status = "failed"

    else:
        # Handle audio, video, document, contacts, location, interactive, etc. gracefully
        payload_data = msg.get(msg_type, {})
        caption = payload_data.get("caption") if isinstance(payload_data, dict) else None
        body_text = caption or f"[{msg_type} message]"
        media_url = None
        media_status = None
        media_type = None

    # Save to Supabase using standard pipeline
    db.save_message(
        session_id=session["id"],
        direction="in",
        body=body_text,
        media_url=media_url,
        media_type=media_type,
        twilio_sid=msg_id,
        media_status=media_status,
    )

    # Trigger background agent loop
    process_in_background(session["id"], warung["id"])


async def process_meta_payload(payload: Dict[str, Any]):
    """Background task to unpack all messages in the Meta webhook payload."""
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    await process_single_meta_message(msg)
    except Exception as e:
        logger.error(f"Error in process_meta_payload: {e}", exc_info=True)


@router.get("/api/webhook/meta")
async def meta_webhook_verification(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Meta Cloud API Webhook Verification.
    Validates hub.mode == 'subscribe' and hub.verify_token == META_VERIFY_TOKEN.
    Returns hub.challenge as plain text.
    """
    config = get_meta_config()
    expected_verify_token = config["verify_token"]

    if hub_mode == "subscribe" and hub_verify_token and hub_verify_token == expected_verify_token:
        logger.info("Meta webhook verification successful.")
        return Response(content=hub_challenge or "", media_type="text/plain", status_code=200)

    logger.warning("Meta webhook verification failed: token mismatch or invalid mode.")
    return Response(content="Forbidden", status_code=403)


@router.post("/api/webhook/meta")
async def meta_webhook_receive(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
):
    """
    Meta Cloud API Webhook Event Receiver.
    Parses JSON payload, prints raw body for debug, delegates message processing
    to BackgroundTasks, and immediately responds with 200 {'status': 'ok'}.
    """
    raw_body = await request.body()

    # Optional signature check
    if not verify_signature(raw_body, x_hub_signature_256):
        logger.warning("Meta webhook signature verification failed.")
        return Response(content="Forbidden", status_code=403)

    try:
        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        body = {}

    # Print raw body for debugging as requested
    print(f"Meta webhook raw body: {json.dumps(body) if isinstance(body, dict) else body}")

    # Dispatch processing asynchronously to ensure immediate 200 return to Meta
    background_tasks.add_task(process_meta_payload, body)

    return {"status": "ok"}
