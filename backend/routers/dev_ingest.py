import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from agent import process_in_background
import db
from services.storage import upload_media

logger = logging.getLogger("kawalhalal.dev")

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def verify_dev_key(x_dev_key: Optional[str] = Header(None, alias="X-Dev-Key")) -> str:
    """
    Validate the dev key against DEV_INGEST_KEY.
    Returns 404 if DEV_INGEST_KEY is unset (endpoint disabled).
    Returns 403 if key is missing or invalid.
    Never logs the key.
    """
    dev_key = os.environ.get("DEV_INGEST_KEY", "").strip()
    if not dev_key:
        raise HTTPException(status_code=404, detail="Endpoint disabled")
    if not x_dev_key or x_dev_key.strip() != dev_key:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Dev-Key")
    return dev_key


@router.post("/api/dev/ingest-image", dependencies=[Depends(verify_dev_key)])
async def ingest_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    phone: str = Form(...),
    caption: Optional[str] = Form(None),
):
    """
    Development/Demo image ingestion endpoint:
    Routes directly through the same Supabase storage, messaging table,
    and background agent pipeline as the WhatsApp webhook.
    """
    # 1. Content-type validation
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed.")

    # 2. File size validation (max 10 MB)
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds the 10 MB limit.")

    # 3. Upload to Supabase Storage using existing helper
    message_id = f"dev-{uuid.uuid4()}"
    logger.info(f"Processing dev image ingestion: message_id={message_id}, phone={phone}, size={len(content)} bytes")

    try:
        public_url = upload_media(
            content=content,
            content_type=file.content_type,
            message_id=message_id,
        )
    except Exception as e:
        logger.error(f"Failed to upload dev image to Supabase Storage: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload image to storage.")

    # 4. Resolve warung & session using existing phone normalization
    warung = db.get_or_create_warung(phone)
    session = db.get_or_create_session(warung["id"])

    # 5. Persist inbound message using the existing pipeline
    body_text = caption or ""
    db.save_message(
        session_id=session["id"],
        direction="in",
        body=body_text,
        media_url=public_url,
        media_type=file.content_type,
        twilio_sid=message_id,
        media_status="ok",
    )

    # 6. Trigger background agent processing
    background_tasks.add_task(process_in_background, session["id"], warung["id"])

    return {
        "status": "ok",
        "media_url": public_url,
        "message_id": message_id,
    }


@router.get("/dev/upload", response_class=HTMLResponse)
async def dev_upload_page():
    """
    Minimal self-contained web interface for developer/demo image upload.
    No external CDN or assets required.
    """
    dev_key = os.environ.get("DEV_INGEST_KEY", "").strip()
    if not dev_key:
        raise HTTPException(status_code=404, detail="Endpoint disabled")

    html_content = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>KawalHalal - Dev Image Ingestion</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #10b981;
      --primary-hover: #059669;
      --border: #334155;
      --error: #ef4444;
      --success: #22c55e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      width: 100%;
      max-width: 520px;
      padding: 2rem;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }
    h1 {
      font-size: 1.5rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
      color: #34d399;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    p.desc {
      color: var(--text-muted);
      font-size: 0.875rem;
      margin-bottom: 1.5rem;
      line-height: 1.4;
    }
    .form-group {
      margin-bottom: 1.25rem;
    }
    label {
      display: block;
      font-size: 0.875rem;
      font-weight: 500;
      margin-bottom: 0.375rem;
      color: var(--text);
    }
    input[type="text"],
    input[type="password"],
    input[type="file"] {
      width: 100%;
      padding: 0.625rem 0.75rem;
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text);
      font-size: 0.875rem;
      transition: border-color 0.2s;
    }
    input[type="file"] {
      padding: 0.5rem;
      cursor: pointer;
    }
    input:focus {
      outline: none;
      border-color: var(--primary);
    }
    button {
      width: 100%;
      padding: 0.75rem;
      background: var(--primary);
      color: #ffffff;
      font-weight: 600;
      font-size: 0.95rem;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.2s;
      margin-top: 0.5rem;
    }
    button:hover:not(:disabled) {
      background: var(--primary-hover);
    }
    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    .preview {
      margin-top: 1rem;
      text-align: center;
    }
    .preview img {
      max-width: 100%;
      max-height: 200px;
      border-radius: 6px;
      border: 1px solid var(--border);
      display: none;
      margin: 0 auto;
    }
    .result-box {
      margin-top: 1.5rem;
      padding: 1rem;
      border-radius: 6px;
      font-size: 0.825rem;
      display: none;
      white-space: pre-wrap;
      word-break: break-all;
    }
    .result-box.success {
      display: block;
      background: rgba(34, 197, 94, 0.1);
      border: 1px solid var(--success);
      color: #86efac;
    }
    .result-box.error {
      display: block;
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid var(--error);
      color: #fca5a5;
    }
    pre {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
    }
    .badge {
      display: inline-block;
      font-size: 0.75rem;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      background: rgba(52, 211, 153, 0.15);
      color: #34d399;
      font-weight: 600;
      margin-bottom: 0.75rem;
    }
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">DEV / DEMO PIPELINE</span>
    <h1>KawalHalal Dev Ingest</h1>
    <p class="desc">
      Unggah gambar langsung ke pipeline Supabase Storage & AI Agent KawalHalal menggunakan nomor warung yang dituju.
    </p>

    <form id="uploadForm">
      <div class="form-group">
        <label for="devKey">X-Dev-Key</label>
        <input type="password" id="devKey" placeholder="Masukkan DEV_INGEST_KEY" required autocomplete="current-password">
      </div>

      <div class="form-group">
        <label for="phone">Nomor WhatsApp Pelaku Usaha (Warung)</label>
        <input type="text" id="phone" value="+6281234567890" placeholder="+6281234567890" required>
      </div>

      <div class="form-group">
        <label for="caption">Keterangan / Caption (Opsional)</label>
        <input type="text" id="caption" placeholder="Contoh: Foto kemasan bumbu Masako Ayam">
      </div>

      <div class="form-group">
        <label for="file">Berkas Gambar (Maks 10 MB)</label>
        <input type="file" id="file" accept="image/*" required>
      </div>

      <div class="preview">
        <img id="imgPreview" alt="Preview Gambar">
      </div>

      <button type="submit" id="submitBtn">Kirim ke Pipeline Agent</button>
    </form>

    <div id="resultBox" class="result-box">
      <pre id="resultPre"></pre>
    </div>
  </div>

  <script>
    const fileInput = document.getElementById('file');
    const imgPreview = document.getElementById('imgPreview');
    const form = document.getElementById('uploadForm');
    const submitBtn = document.getElementById('submitBtn');
    const resultBox = document.getElementById('resultBox');
    const resultPre = document.getElementById('resultPre');
    const devKeyInput = document.getElementById('devKey');

    // Restore saved dev key from localStorage if present
    const savedKey = localStorage.getItem('kawalhalal_dev_key');
    if (savedKey) {
      devKeyInput.value = savedKey;
    }

    fileInput.addEventListener('change', () => {
      const file = fileInput.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
          imgPreview.src = e.target.result;
          imgPreview.style.display = 'block';
        };
        reader.readAsDataURL(file);
      } else {
        imgPreview.style.display = 'none';
      }
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      submitBtn.disabled = true;
      submitBtn.textContent = 'Mengunggah & Memproses...';
      resultBox.className = 'result-box';
      resultBox.style.display = 'none';

      const devKey = devKeyInput.value.trim();
      const phone = document.getElementById('phone').value.trim();
      const caption = document.getElementById('caption').value.trim();
      const file = fileInput.files[0];

      if (!file) {
        alert('Pilih berkas gambar terlebih dahulu.');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Kirim ke Pipeline Agent';
        return;
      }

      // Save key in localStorage for convenience during testing
      localStorage.setItem('kawalhalal_dev_key', devKey);

      const formData = new FormData();
      formData.append('file', file);
      formData.append('phone', phone);
      if (caption) {
        formData.append('caption', caption);
      }

      try {
        const res = await fetch('/api/dev/ingest-image', {
          method: 'POST',
          headers: {
            'X-Dev-Key': devKey
          },
          body: formData
        });

        const data = await res.json();
        if (res.ok) {
          resultBox.className = 'result-box success';
          resultPre.textContent = JSON.stringify(data, null, 2);
        } else {
          resultBox.className = 'result-box error';
          resultPre.textContent = `HTTP ${res.status}: ${JSON.stringify(data, null, 2)}`;
        }
      } catch (err) {
        resultBox.className = 'result-box error';
        resultPre.textContent = 'Terjadi kesalahan jaringan: ' + err.message;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Kirim ke Pipeline Agent';
      }
    });
  </script>
</body>
</html>"""
    return HTMLResponse(content=html_content, status_code=200)
