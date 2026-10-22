# Handoff: agen ADK KawalHalal (untuk Bagas)

Branch: `feat/doc-filler` (dari `origin/dev`). Semua kode agen ada di `backend/kawal_agent/`. Status: **53 tes lolos pakai Gemini palsu; belum pernah dites dengan Gemini asli** (kuota gratis 20 request/hari habis saat percobaan pertama).

## Yang sudah dibangun

Agen ADK (`LlmAgent`) dengan 25 tool. Model memilih tool sendiri; di awal tiap giliran ia memanggil `lihat_progres`. Target alur: dari belum punya akun sampai pengajuan terkirim di mock SIHALAL.

| File | Isi |
|---|---|
| `kawal_agent/agent.py` | `bangun_agen()`, `jalankan(user_id, teks, lampiran)`, sesi in-memory, loop event khusus agen, guardrail output (pakai `terapkan_guardrail` dari `agent.py` lama) |
| `kawal_agent/prompts.py` | Instruksi sistem |
| `kawal_agent/tools.py` | 25 tool (akun, kategori, jalur, draf, produk, bahan, pembelian, proses, komitmen, lampiran, xlsx, periksa, kirim) |
| `kawal_agent/gates.py` | Gerbang konfirmasi manusia, ditegakkan di kode |
| `kawal_agent/verifikasi.py` | Verifikasi bahan: sertifikat, nabati, RPH/RPU, titik kritis |
| `kawal_agent/registri.py` + `data/registri_mock.json` | Registri simulasi (merek dan nomor FIKTIF) |
| `kawal_agent/sinkron.py` | Data kerja sesi -> pengajuan mock SIHALAL (idempoten, tidak menimpa isian web) |
| `kawal_agent/templates.py` | xlsx dua arah (buat dan impor), sel kosong = `BELUM DIISI` |
| `kawal_agent/kategori.py` | 5 kategori, data-driven |
| `routers/agent_chat.py` | `POST /api/agent/chat`, unduh berkas bertanda tangan, `/state`, reset sesi |
| `services/wa_agent.py`, `services/outbound.py` | WhatsApp -> agen -> balasan (Twilio atau Meta, dipilih dari awalan id pesan) |
| `ngobrol.py` | Chat terminal untuk tes dengan key asli |

## Aturan yang ditegakkan kode (jangan dipindah ke prompt)

- Bahan bukti lengkap -> langsung masuk mockup. Bahan bercelah -> ditahan sampai user membalas YA.
- `before_agent_callback` (`gates.proses_giliran_baru`) membaca balasan ASLI user. Model tidak bisa menyetujui sendiri. Balasan ragu ("ya tapi...") dianggap belum setuju.
- Persetujuan kirim memakai fingerprint data: kalau data berubah setelah YA, harus minta lagi.
- Kirim pengajuan selalu butuh YA (bisa dilonggarkan di `kirim_pengajuan_sihalal`).
- Berkas hanya bisa dilampirkan kalau benar-benar dikirim user. Tidak ada isian karangan.

## Perubahan di file milikmu (semua kecil, aditif)

- `agent.py`: `process_in_background` sekarang menjalankan agen (dulu stub). Dijadwalkan ke event loop khusus agen, aman dipanggil dari BackgroundTasks maupun fungsi async (webhook Meta).
- `main.py`: 1 import + `include_router(agent_router)`.
- `sihalal_mock.py`: `daftarkan_akun`, `cek_masuk`, `pelaku_usaha_aktif`, endpoint `POST /api/sihalal/akun/masuk`, dan `kirim_draf()` (logika kirim dipindah ke fungsi yang dipakai endpoint lama dan agen).
- `tools.py`: tambahan kata kunci bahan (kosmetik, minyak goreng, dll.).
- `backend/requirements.txt`: `google-adk`, `openpyxl`, `python-docx`.
- Frontend: `Login.tsx` + `sesi.ts` (login akun hasil daftar agen), `opsi.ts` (kategori tambahan).

## Yang belum beres / perlu keputusanmu

1. **Tes dengan Gemini asli.** Isi `GEMINI_API_KEY` di `backend/.env`, jalankan `python ngobrol.py`. Perhatikan: apakah model patuh urutan, tidak menebak nomor sertifikat, dan menunggu YA di gerbang.
2. **Kuota.** Tier gratis 20 request/hari/model; satu giliran chat = 3 sampai 6 request. Demo butuh billing atau kredit GCP.
3. **Nama model.** Default `gemini-3.8-flash` (dari kodemu), override dengan `GEMINI_MODEL`. `AGENTS.md` menyebut `gemini-2.0-flash`.
4. **Deploy.** Dockerfile menyalin `data/`. Set `PUBLIC_BASE_URL` (link xlsx), `DEV_INGEST_KEY` (endpoint chat), opsional `TWILIO_WHATSAPP_FROM`, `BERKAS_SECRET`. Sesi agen dan mock SIHALAL ada di memori: pakai max-instances 1 dan jaga instance tetap hidup saat demo (scale-to-zero menghapus state).
5. **Mock satu penyewa.** Daftar akun lewat agen mengganti profil Pak Sam sampai `/api/demo/reset`.
6. **Jalur ingest dev** (`/api/dev/ingest-image`) masih image-only. Dokumen bisa lewat `/api/agent/chat`. Kode ingest PDF/DOCX/video lama ada di branch lokal `wip/docs-ingest` (video di luar scope demo).
7. **Skema tabel `messages`** tidak ada di repo. `wa_agent.py` mengandalkan kolom `created_at`, `direction`, `body`, `media_url`, `media_type`, `twilio_sid`: cek cocok dengan Supabase.
8. **Agen lama** (`KawalHalalAgent`, `/api/scan`, `/api/chat`) masih ada dan tidak dipakai agen baru.
9. Gagal 429 dari Gemini sekarang dibalas pesan umum "agen bermasalah"; bisa dibuat pesan khusus kuota.

## Cara tes

```
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt pytest
.venv\Scripts\python -m pytest tests -q
.venv\Scripts\python ngobrol.py
```
