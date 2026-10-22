# KawalHalal

Agen AI pendamping sertifikasi halal untuk pelaku usaha kecil. Pemilik usaha cukup ngobrol dengan **Kala** lewat Telegram atau WhatsApp, dan berkas pengajuannya terisi sendiri di SIHALAL. Dibuat untuk ITB Agentic AI Hackathon 2026.

> **Batas layanan.** Kala hanya memeriksa kelengkapan bukti dokumen. Kala tidak pernah menyatakan produk halal: penetapan ada di BPJPH dan Komite Fatwa. SIHALAL dan registri sertifikat di repo ini adalah **simulasi** untuk demo, dengan merek dan nomor yang fiktif.

## Masalah dan solusi

Mengurus sertifikat halal lewat SIHALAL rumit bagi pelaku usaha mikro: banyak tab, banyak istilah, dan tidak ada API untuk diotomasi. Kala mengubahnya menjadi percakapan:

1. Pengguna memilih kategori produk dan memberi data usaha. Kala mendaftarkan akun, menentukan jalur (SEHATI atau reguler), dan membuat draf pengajuan.
2. Pengguna mengirim foto label atau nota. Kala membaca foto, mencocokkan nomor sertifikat dengan registri, dan menelusuri lapak daging sampai rumah potong hewan.
3. Bahan dengan bukti lengkap langsung masuk. Bahan yang bercelah ditahan sampai pengguna membalas YA.
4. Pengguna boleh mengisi berkas Excel. Kala membaca dan memasukkannya ke banyak tab sekaligus.
5. Sebelum kirim, Kala memeriksa kelengkapan dan merinci yang masih kurang.

## Arsitektur

Tiga agen dengan pembagian kerja yang jelas:

| Agen | Tugas |
|---|---|
| **Kala** (orkestrator) | Mengobrol, membaca foto, memilih tool, memverifikasi bahan, menjaga gerbang konfirmasi. |
| **Operator** | Mengisi web SIHALAL lewat browser seperti pengguna biasa (Playwright), tanpa akses ke database. Karena SIHALAL asli tidak punya API. |
| **Pemeriksa** | Membaca hasil di layar dan mencocokkannya dengan niat Kala. |

Pengaman yang ditegakkan di kode, bukan hanya di prompt:

- **Gerbang manusia:** bahan bercelah, pernyataan komitmen, dan pengiriman hanya berjalan setelah balasan YA yang nyata dari pengguna. Persetujuan gugur bila datanya berubah.
- **Guardrail:** keluaran model disaring supaya tidak menyatakan produk halal.
- **Jejak asal data:** isian dari agen diberi tanda ✦ beserta sumbernya di web SIHALAL.

Teknologi: Google ADK (Python), Gemini lewat Vertex AI, FastAPI, React (web SIHALAL tiruan), Playwright, dan Cloud Run.

## Struktur repo

| Folder | Isi |
|---|---|
| `backend/kawal_agent/` | Agen: `agent.py`, `tools.py` (tool agen), `gates.py` (gerbang YA), `operator_ui.py` (operator browser), `verifikasi.py`, `registri.py`, `sinkron.py`, `prompts.py`. |
| `backend/services/` | Kanal: `telegram_bot.py`, `waha.py` (WhatsApp), `wa_agent.py` dan `outbound.py` (jalur Twilio dan Meta lama). |
| `backend/sihalal_mock.py` | SIHALAL tiruan: penyimpanan pengajuan di memori dan endpoint `/api/sihalal`. |
| `backend/data/registri_mock.json` | Registri sertifikat simulasi. |
| `frontend/` | Web SIHALAL tiruan (React). |
| `docs/` | Dokumen: `waha.md`, `rencana-multi-agent.md`, `handoff-agen-adk.md`, `product_requirements_document.md`. |

## Menjalankan secara lokal

Prasyarat: Python 3.12, Node 20, akses Vertex AI (ADC) atau API key Gemini.

```bash
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m playwright install chromium
```

Bangun frontend dalam mode http (wajib, tanpa itu halaman memakai data tiruan sendiri):

```bash
cd frontend
npm ci
VITE_API_MODE=http npm run build
```

Buat `backend/.env` (jangan di-commit), lalu jalankan dari folder `backend`:

```bash
FRONTEND_DIST=../frontend/dist .venv/Scripts/python -m uvicorn main:app --port 8010
```

Web SIHALAL tiruan ada di `http://localhost:8010`. Untuk ngobrol dari terminal tanpa Telegram: `python ngobrol.py`.

### Variabel lingkungan

| Variabel | Fungsi |
|---|---|
| `GOOGLE_GENAI_USE_ENTERPRISE`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` | Memakai Gemini di Vertex AI (lokasi model `global`). |
| `GEMINI_API_KEY` | Alternatif untuk uji lokal bila tanpa Vertex. |
| `GEMINI_MODEL` | Nama model utama. |
| `TELEGRAM_BOT_TOKEN` | Mengaktifkan bot Telegram (long polling). |
| `TELEGRAM_NONAKTIF=1` | Server lokal tidak ikut polling, supaya tidak merebut bot yang hidup di Cloud Run (galat 409). |
| `KALA_OPERATOR=ui` | Operator mengisi form lewat browser. Tanpa ini, data ditulis langsung (mode cadangan). |
| `OPERATOR_BASE_URL` | Alamat web yang dibuka operator, mis. `http://127.0.0.1:8010`. |
| `OPERATOR_TAMPIL=1` | Browser operator terlihat (bukan tanpa kepala), berguna saat demo lokal. |
| `WAHA_URL`, `WAHA_API_KEY`, `WAHA_SESSION` | Menghubungkan WhatsApp lewat WAHA. |
| `DEV_INGEST_KEY` | Kunci header `X-Dev-Key` untuk endpoint reset dan state. |
| `PUBLIC_BASE_URL` | Dasar tautan unduh berkas yang dikirim agen. |

## WhatsApp lewat WAHA

Lihat [docs/waha.md](docs/waha.md). Singkatnya: `docker compose -f docker-compose.waha.yml up -d`, tautkan **nomor dummy** (bukan nomor pribadi) lewat dashboard `http://localhost:3000/dashboard`, lalu jalankan backend lokal dengan `WAHA_URL` terisi. WAHA memakai sesi WhatsApp Web, jadi cocok untuk demo, bukan produksi.

## Deploy ke Cloud Run

Satu image berisi web dan backend (Chromium untuk operator ikut terpasang). Dari root repo:

```bash
gcloud run deploy kawalhalal-demo --source . --region asia-southeast2 --project <GCP_PROJECT_ID> --memory 2Gi --cpu 2 --min-instances 1 --max-instances 1 --no-cpu-throttling --update-env-vars KALA_OPERATOR=ui
```

Service account Cloud Run perlu peran `roles/aiplatform.user` agar bisa memanggil Gemini. Gunakan `--update-env-vars`, bukan `--env-vars-file`, agar variabel yang sudah ada (termasuk token bot) tidak terhapus. Untuk kembali ke mode cadangan, hapus `KALA_OPERATOR`.

## Tes

```bash
cd backend
.venv/Scripts/python -m pytest tests -q
```

Tes memakai model terskrip untuk agen dan satu uji nyata dengan browser terhadap server lokal (dilewati bila build frontend atau Chromium tidak ada). Latihan demo dengan Gemini asli: `python latih_operator.py`.

## Batasan yang jujur

- SIHALAL, registri sertifikat, dan lapak yang ditelusuri adalah simulasi. Data disimpan di memori server, belum database.
- Kanal produksi yang dituju adalah WhatsApp resmi (Meta). Kode siap, menunggu akun bisnis terverifikasi. Jalur WAHA hanya untuk demo.
- Kala hanya membantu kelengkapan bukti. Penentuan halal bukan wewenang Kala.
