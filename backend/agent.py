import logging

logger = logging.getLogger("kawalhalal.agent")


def process_in_background(session_id: str, warung_id: str):
    """
    Background worker stub:
    Dispatches agent execution loop (e.g. process_event) and sends replies
    via Meta WhatsApp Cloud API (send_text) or Twilio REST API.
    """
    logger.info(f"Triggered background agent processing for session={session_id}, warung={warung_id}")
    # STUB: nanti diganti process_event(...) dari agen Bagas
    pass
