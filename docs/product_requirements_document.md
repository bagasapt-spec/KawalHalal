# PRODUCT REQUIREMENTS DOCUMENT (PRD)
## KawalHalal: Autonomous Dossier & Provenance Agent for P3H

**Versi Dokumen:** 1.0.0  
**Status:** Frozen for 24-Hour Hacking Sprint  
**Target Event:** ITB Agentic AI Hackathon 2026 (DHKT ITB & Google Cloud / Devoteam)  
**Lead AI / Author:** Bagas Anugrah Putra (Lead AI / Hacker)  
**Tim:** KawalHalal (Bagas Anugrah Putra, Rafel Dzinun Muhammad, Matthew Evan Kurniawan, Karen Evangeline Wahyudi, Kezia Josephine Manik)  

---

## 1. Executive Summary & Problem Scope

### 1.1 Latar Belakang Regulasi & Urgensi
Berdasarkan amanat Undang-Undang Jaminan Produk Halal (UU JPH) dan Peraturan Pemerintah terkait, per **18 Oktober 2026** seluruh produk makanan dan minuman dari Usaha Mikro dan Kecil (UMK) di Indonesia wajib memiliki sertifikat halal. 

Pemerintah menyediakan jalur verifikasi mandiri (*self-declare*) yang bertumpu pada **111.000+ Pendamping Proses Produk Halal (P3H)**. Di lapangan, P3H memikul tanggung jawab hukum dan sanksi administratif langsung jika terjadi kelalaian verifikasi bahan baku (Peraturan BPJPH No. 2/2026).

### 1.2 *Pain Points* Utama
1. **Beban Kognitif & Administratif P3H:** Verifikasi manual terhadap puluhan dokumen warung, transkripsi catatan WhatsApp yang berantakan, serta penelusuran status sertifikat bahan satu per satu memakan waktu 3–5 hari per pelaku usaha.
2. **Titik Buta (*Blind Spot*) Pasar Tradisional:** Bahan segar dan daging potong dari pedagang pasar tradisional tidak memiliki label, barcode, maupun struk pembelian formal. Hal ini menimbulkan risiko kegagalan verifikasi asal-usul sembelihan (Rumah Potong Hewan/RPH).
3. **Risiko Substitusi Bahan Pasca-Sertifikasi (*Ingredient Drift*):** Tidak adanya mekanisme pemantauan berkala membuat pelaku UMK rentan mengganti bahan baku halal berbiaya tinggi dengan bahan curah/non-sertifikat yang lebih murah saat produksi harian berjalan.

### 1.3 Pernyataan Nilai Produk (*Value Proposition*)
**KawalHalal** adalah platform *Agentic AI* multimodal otonom yang berperan sebagai *pra-verifikator berkas (pre-audit copilot)* bagi P3H. Agen ini:
* Mengumpulkan data bahan secara fleksibel via WhatsApp (teks, foto label, dan rekaman suara).
* Menjalankan penalaran berbasis *ReAct pattern* untuk memverifikasi bahan secara otomatis terhadap daftar pengecualian (KMA 1360), pangkalan data BPJPH, dan jaringan pemasok pasar tradisional.
* Menegakkan mekanisme **Human-in-the-Loop (HITL)** berjenjang sebelum berkas disahkan ke sistem SIHALAL.
* Memfasilitasi deteksi anomali visual berkala (*Watchdog*) terhadap dapur produksi UMK.

---

## 2. User Persona & System Interaction

### 2.1 Persona 1: Pelaku Usaha Mikro (Pak Joko - Penjual Bakso & Soto)
* **Karakter:** Mengelola operasional dapur sendiri, literasi aplikasi digital formal rendah, aktif berkomunikasi via WhatsApp, membeli daging harian di pasar rakyat.
* **Perilaku:** Lebih nyaman mengirim foto rak bumbu dan *voice note* mengenai resep ketimbang mengisi formulir web yang rumit.

### 2.2 Persona 2: Pendamping P3H (Ibu Sarah - Petugas Pendamping)
* **Karakter:** Mendampingi 30+ warung makan di area Bandung, bertanggung jawab menandatangani keabsahan berkas secara hukum sebelum diunggah ke SIHALAL.
* **Kebutuhan:** Tampilan antarmuka ringkas yang memetakan status bahan, menyorot risiko rantai pasok (*Needs Action*), dan tombol sekali klik untuk mengekspor dossier PDF resmi.

---

## 3. Arsitektur Teknis Sistem

Sistem dirancang modular untuk memaksimalkan komponen Google Cloud/Gemini SDK dalam ekosistem monorepo:

```
                      [Pelaku UMK]
                           │
                (WhatsApp Gateway - Webhook)
                           │
                           ▼
              ┌───────────────────────────┐
              │    FastAPI API Server     │
              │  (Async Media Ingestion)  │
              └─────────────┬─────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │  KAWALHALAL AGENT CORE    │
              │   Google Gemini 1.5 SDK   │
              │   (ReAct Loop Orchestrator)│
              └──────┬──────┬──────┬──────┘
                     │      │      │
       ┌─────────────┘      │      └─────────────┐
       ▼                    ▼                    ▼
[Tool: KMA 1360]    [Tool: BPJPH]       [Tool: RPH Market]
(Exempt Registry)   (Registry API)      (Local Graph Cache)
       │                    │                    │
       └─────────────┬──────┴────────────────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │   Supabase DB       │
          │  - Audit Logs       │
          │  - State Storage    │
          │  - Media Files      │
          └──────────┬──────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌──────────────────┐   ┌───────────────────────┐
│ Next.js Web App  │   │ WeasyPrint PDF Engine │
│ (P3H Dashboard)  │   │ (Official Dossier)    │
└──────────────────┘   └───────────────────────┘
```

### 3.1 Komponen & Tech Stack

| Layer | Teknologi | Peran Teknis |
| :--- | :--- | :--- |
| **Agent Core & Reasoning** | **Google Gemini 1.5 Flash / Pro** via Google GenAI SDK | Ekstraksi multimodal (audio/vision), *function calling*, dan sintesis rekomendasi audit. |
| **Backend & Routing** | **Python 3.11 + FastAPI** | Webhook WhatsApp, koordinasi *agent execution loop*, dan validasi skema via Pydantic. |
| **Database & Media Storage** | **Supabase (PostgreSQL + S3 Storage)** | Penyimpanan status sesi, data bahan, log eksekusi tools, dan arsip gambar. |
| **P3H Web Dashboard** | **Next.js 14 (App Router) + Tailwind CSS** | Panel kerja P3H, antarmuka penelaahan bukti (*Human Gate*), dan visualisasi *audit trail*. |
| **Document Compiler** | **WeasyPrint / Jinja2** | Mesin kompilasi berkas laporan audit (*Dossier PDF*) siap hukum. |

---

## 4. Spesifikasi Tools & Agentic Functions

Agen beroperasi menggunakan prinsip *deterministic tool-use* melalui mekanisme Gemini Function Calling:

### 4.1 Tool 1: `check_kma1360_exemption`
* **Tujuan:** Menentukan apakah bahan termasuk dalam *Positive List* (bahan alami berisiko rendah yang dikecualikan dari sertifikasi menurut KMA 1360/2021).
* **Definisi Fungsi:**
```json
{
  "name": "check_kma1360_exemption",
  "description": "Verifikasi bahan mentah alami segar (sayur, buah, rempah murni, air) terhadap daftar pengecualian KMA 1360.",
  "parameters": {
    "type": "object",
    "properties": {
      "ingredient_name": { "type": "string", "description": "Nama bahan mentah standar" }
    },
    "required": ["ingredient_name"]
  }
}
```
* **Keluaran:** `{ "is_exempt": true, "category": "Bahan Alami Nabati", "reference": "KMA 1360 Lampiran II" }`

### 4.2 Tool 2: `lookup_bpjph_registry`
* **Tujuan:** Mencocokkan bahan olahan/bermerek terhadap pangkalan data sertifikat BPJPH.
* **Definisi Fungsi:**
```json
{
  "name": "lookup_bpjph_registry",
  "description": "Pencarian nama merek atau nomor sertifikat halal pada database registri BPJPH.",
  "parameters": {
    "type": "object",
    "properties": {
      "product_name": { "type": "string", "description": "Nama produk dan merek komersial" },
      "certificate_number": { "type": "string", "description": "Nomor sertifikat halal jika tertera di kemasan" }
    },
    "required": ["product_name"]
  }
}
```
* **Keluaran:** `{ "found": true, "cert_id": "ID3211000234123", "status": "TERBIT", "expiry_date": "2028-04-12" }`

### 4.3 Tool 3: `trace_rph_provenance`
* **Tujuan:** Memvalidasi rantai pasok daging/ayam dari lapak pasar tradisional ke Rumah Potong Hewan/Unggas bersertifikat.
* **Definisi Fungsi:**
```json
{
  "name": "trace_rph_provenance",
  "description": "Pelacakan keterhubungan lapak pedagang pasar tradisional ke RPH terakreditasi.",
  "parameters": {
    "type": "object",
    "properties": {
      "market_name": { "type": "string", "description": "Nama pasar tradisional" },
      "stall_name": { "type": "string", "description": "Nama lapak atau nama pedagang daging" },
      "meat_type": { "type": "string", "enum": ["ayam", "sapi", "kambing"] }
    },
    "required": ["market_name", "stall_name", "meat_type"]
  }
}
```
* **Keluaran:** 
  * *Jika terhubung:* `{ "verified": true, "rph_name": "RPH Ciroyom", "halal_cert": "ID3222000019283", "risk_level": "LOW" }`
  * *Jika tidak terdaftar:* `{ "verified": false, "reason": "UNMAPPED_STALL", "risk_level": "HIGH", "action": "FLAG_NEEDS_ACTION" }`

### 4.4 Tool 4: `analyze_kitchen_watchdog`
* **Tujuan:** Membandingkan foto meja kerja dapur terkini dengan foto *baseline* verifikasi untuk mendeteksi substitusi bahan secara visual (*ingredient drift*).
* **Definisi Fungsi:**
```json
{
  "name": "analyze_kitchen_watchdog",
  "description": "Membandingkan visual bahan baku di dapur dengan profil bahan yang telah disetujui.",
  "parameters": {
    "type": "object",
    "properties": {
      "session_id": { "type": "string" },
      "image_url": { "type": "string" }
    },
    "required": ["session_id", "image_url"]
  }
}
```

---

## 5. Mekanisme Human-in-the-Loop (HITL)

Sesuai kriteria integritas data dan etika regulasi:

```
[Input Pedagang via WhatsApp]
            │
            ▼
┌───────────────────────────────┐
│ Ekstraksi & Penalaran Agen   │
└───────────┬───────────────────┘
            │
            ▼
┌───────────────────────────────┐
│   HUMAN GATE 1: PEDAGANG      │
│ Konfirmasi Daftar Bahan via   │
│ Chat WhatsApp ("YA/SESUAI")   │
└───────────┬───────────────────┘
            │
            ▼
┌───────────────────────────────┐
│ Penyusunan Berkas Dossier     │
└───────────┬───────────────────┘
            │
            ▼
┌───────────────────────────────┐
│     HUMAN GATE 2: P3H         │
│ Telaah Bukti Visual & Rantai  │
│ Pasok di Web Dashboard        │
└───────────┬───────────────────┘
            │
   ┌────────┴────────┐
   ▼                 ▼
[Approved]       [Needs Revision]
   │                 │
   ▼                 ▼
(Kompilasi      (Notifikasi Balik
 Dossier PDF)    ke Pedagang via WA)
```

1. **Human Gate 1 (Verifikasi Pelaku Usaha):**
   * Agen merangkum seluruh bahan yang berhasil diidentifikasi dari foto dan rekaman suara, lalu menanyakannya kembali kepada pedagang untuk memastikan tidak ada resep rahasia yang terlewat.
2. **Human Gate 2 (Persetujuan Legal P3H):**
   * AI dilarang mengeluarkan rekomendasi kelulusan sepihak. P3H memeriksa penandaan status bahan (Hijau = Lolos, Merah = Butuh Verifikasi Lapangan), melengkapi catatan lapangan, lalu membubuhkan tanda tangan digital pada berkas PDF.

---

## 6. Penanganan Skenario Batas (*Edge Cases*)

| Kasus Batas (*Edge Case*) | Respon Otonom Agen | Penanganan Sistem & UI |
| :--- | :--- | :--- |
| **Lapak Daging Belum Terdaftar di Pangkalan Data** | Agen menghentikan proses kelulusan otomatis bahan tersebut; menetapkan status `NEEDS_ACTION`. | Dashboard P3H menandai kartu bahan dengan warna merah dan memunculkan rekomendasi suplier RPH bersertifikat alternatif terdekat. |
| **Foto Label Buram / Terpotong** | Gemini Multimodal mendeteksi tingkat keterbacaan rendah ($< 0.70$ *confidence*). | Agen membalas otomatis di WhatsApp: *"Foto label kurang jelas. Mohon kirimkan ulang foto yang menampilkan nama merek dan nomor registrasi dengan pencahayaan cukup."* |
| **Audio Suara Pasar Sangat Bising** | Model transkripsi memanfaatkan *system instruction* berbasis kosa kata bahan pasar lokal. | Jika ekstraksi entitas gagal, agen meminta konfirmasi berbasis pilihan teks angka di WhatsApp. |
| **Substitusi Bahan Terdeteksi (*Drift*)** | *Watchdog* mendeteksi botol minyak curah tanpa merek menggantikan minyak bermerek terdaftar. | Sistem mencatat anomali pada log audit, menurunkan skor kepatuhan warung, dan mengirim peringatan langsung ke dashboard P3H. |

---

## 7. Rencana Eksekusi Hacking 24 Jam

Target penyelesaian merujuk jadwal resmi: **Rabu 13.00 WIB s.d. Kamis 13.00 WIB**.

```
[13.00 - 16.00] Sprint 1: Setup Lingkungan, Skema DB & Dataset Mock (KMA 1360, BPJPH, RPH)
[16.00 - 20.00] Sprint 2: Core Agent Engine (Gemini Function Calling + Webhook WhatsApp)
[20.00 - 02.00] Sprint 3: Integrasi End-to-End Pipeline & Dashboard Next.js P3H
[02.00 - 08.00] Sprint 4: Watchdog Anomaly Detector & Kompilasi Engine PDF Dossier
[08.00 - 11.00] Sprint 5: Uji 3 Skenario Evaluasi, Pengambilan Video Demo Cadangan
[11.00 - 13.00] Sprint 6: Code Freeze, Pembuatan Tag Versi Git, dan Dokumentasi Akhir
[13.00 - 15.00] Submission: Unggah Berkas Luaran, Finalisasi Pitch Deck 2 Menit
```

### 7.1 Matriks Peran Anggota Tim
* **Bagas Anugrah Putra (Lead AI / Hacker):** Arsitektur agen ReAct, Gemini tool calling, integrasi pangkalan data regulasi.
* **Rafel Dzinun Muhammad (Backend / Hacker):** Webhook WhatsApp, skema Supabase, berkas *engine* PDF WeasyPrint.
* **Matthew Evan Kurniawan (Frontend / Hipster):** Web dashboard penelaahan P3H (Next.js), tampilan visual bukti dan audit trail.
* **Karen Evangeline Wahyudi (Product / Hustler):** Verifikasi data KMA 1360, penyusunan mock dataset pasar, kurasi dokumentasi kepatuhan TOR.
* **Kezia Josephine Manik (QA & Pitching / Hustler):** Skenario pengujian kualitas, perekaman *backup demo video*, penyusunan slide presentasi seleksi Top 10.

---

## 8. Pemetaan Kriteria Penilaian TOR Hackathon

| Kriteria TOR | Bobot | Pembuktian Teknis Proyek KawalHalal |
| :--- | :---: | :--- |
| **Kualitas Agentic AI** | 25% | Menggunakan multi-tool calling otonom berbasis ReAct, penanganan input multimodal (gambar/audio), serta penegakan batas kendali manusia (*human gate*). |
| **Kelayakan Teknis** | 20% | Prototipe fungsional yang menghubungkan WhatsApp $\rightarrow$ FastAPI $\rightarrow$ Supabase $\rightarrow$ Dashboard Next.js secara *real-time*. |
| **Potensi Dampak** | 20% | Mengurangi waktu perakitan berkas P3H dari 3 hari menjadi 15 menit, serta mencegah sanksi pembatalan sertifikat akibat substitusi bahan. |
| **Relevansi Masalah** | 15% | Secara langsung menjawab tenggat wajib halal nasional 18 Oktober 2026 dan beban operasional 111.000 petugas P3H. |
| **User Experience** | 10% | Zero-barrier intake via WhatsApp bagi pelaku usaha, dan antarmuka *review* terpusat berbasis kartu risiko bagi P3H. |
| **Pitching & Live Demo** | 10% | Penyampaian terstruktur 2 menit didukung *live demo* interaktif dan video cadangan (*fail-safe backup*). |