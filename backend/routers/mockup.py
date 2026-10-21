import logging
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from services.mock_service import get_mock_dossier, mock_upload_document

logger = logging.getLogger("kawalhalal.mockup")

router = APIRouter(prefix="/api/mockup", tags=["Mockup SiHalal"])


@router.get("/dossier/{wa_number}")
async def get_mockup_dossier_endpoint(wa_number: str):
    """
    Return comprehensive mock dossier data for a given WhatsApp number.
    Used by the Frontend SiHalal Mockup to automatically populate forms.
    """
    logger.info(f"Serving mock dossier for wa_number: {wa_number}")
    return get_mock_dossier(wa_number)


@router.post("/upload-document")
async def mock_upload_document_endpoint(
    file: Optional[UploadFile] = File(None),
    doc_type: Optional[str] = Form(None),
    wa_number: Optional[str] = Form(None),
):
    """
    Simulate document upload for Frontend SiHalal mockup.
    Does NOT write to the database or storage.
    """
    filename = file.filename if file else None
    content_type = file.content_type if file else None
    file_size = 0

    if file:
        content = await file.read()
        file_size = len(content)

    logger.info(
        f"Simulating mock document upload: filename={filename}, doc_type={doc_type}, size={file_size} bytes"
    )

    return mock_upload_document(
        filename=filename,
        content_type=content_type,
        file_size=file_size if file_size > 0 else None,
    )
