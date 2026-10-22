# WhatsApp lewat WAHA (demo singkat)

Tujuannya menunjukkan bahwa Kala sudah bisa dipakai lewat WhatsApp. WAHA memakai sesi WhatsApp Web biasa, jadi **tidak butuh Twilio dan tidak butuh akun bisnis Meta**. Ini jalur demo, bukan produksi: nomor yang dipakai berisiko diblokir WhatsApp, jadi pakai **nomor cadangan**, bukan nomor utama.

## Cara kerja

```
HP penonton  <->  WhatsApp  <->  WAHA (Docker, laptop)  --webhook-->  backend lokal (:8010)  -->  Kala
                                       ^------ sendText / sendFile ------------+
```

Backend harus berjalan di laptop yang sama dengan WAHA, supaya tidak perlu ngrok. Bot Telegram di Cloud Run tetap jalan untuk demo utama.

## Langkah

1. Pasang Docker Desktop (belum ada di laptop ini), lalu jalankan WAHA:

   ```bash
   docker compose -f docker-compose.waha.yml up -d
   ```

2. Buka `http://localhost:3000/dashboard` (user `admin`, password sama dengan `WAHA_API_KEY`, bawaan `kawalhalal-waha`). Mulai sesi `default`, lalu pindai QR dengan WhatsApp nomor cadangan (Perangkat tertaut).

3. Jalankan backend lokal. Dari folder `backend`:

   ```bash
   TELEGRAM_NONAKTIF=1 WAHA_URL=http://localhost:3000 WAHA_API_KEY=kawalhalal-waha KALA_OPERATOR=ui OPERATOR_BASE_URL=http://127.0.0.1:8010 FRONTEND_DIST=../frontend/dist .venv/Scripts/python -m uvicorn main:app --port 8010
   ```

   `TELEGRAM_NONAKTIF=1` penting: tanpa itu server lokal ikut polling Telegram dan merebut bot yang sedang hidup di Cloud Run (galat 409).

4. Kirim pesan `Halo` dari HP lain ke nomor cadangan itu. Web SIHALAL ada di `http://localhost:8010`.

## Yang didukung

Teks, foto, dokumen (pdf, docx, xlsx), dan berkas xlsx buatan Kala dikirim balik sebagai dokumen. Pesan grup dan pesan dari nomor sendiri diabaikan. Voice note diteruskan ke agen, tetapi belum diuji.

## Variabel lingkungan

| Variabel | Fungsi |
|---|---|
| `WAHA_URL` | Alamat WAHA. Bila kosong, jalur WAHA nonaktif. |
| `WAHA_API_KEY` | Kunci API WAHA (header `X-Api-Key`). |
| `WAHA_SESSION` | Nama sesi, bawaan `default`. |
| `WAHA_WEBHOOK_KEY` | Opsional. Bila diisi, webhook menolak permintaan tanpa header `X-Api-Key` yang sama. |

Nama variabel WAHA di compose mengikuti dokumentasi WAHA saat ini. Bila versi image berbeda dan dashboard tidak muncul, cek dokumentasi WAHA.
