# Rencana multi-agent Kala (untuk Bagas)

Tujuan: jawab feedback juri ("single-agent") dengan tiga agen yang pembagian kerjanya jelas, tanpa merusak yang sudah jalan.

```
Pengguna (Telegram / WhatsApp)
        |
     KALA (orkestrator)  : ngobrol, baca foto, verifikasi, gerbang YA, memutuskan apa yang harus diisi
        |  serahkan(state)
   OPERATOR (agen 2)      : mengisi web SIHALAL lewat browser, tanpa akses database
        |  selesai
   PEMERIKSA (agen 3)     : membaca layar SIHALAL, mencocokkan dengan niat Kala, melapor selisih
```

## 1. Sudah ada (jangan ditulis ulang)

Semua kode di bawah belum di-commit saat dokumen ini ditulis. Minta Rafel commit dan push dulu, lalu `git pull`.

| Berkas | Isi |
|---|---|
| `backend/kawal_agent/operator_ui.py` | Operator **deterministik**: `rencana(state, live)` menyusun langkah formulir, `_Layar.lakukan(t)` menjalankannya lewat Playwright, `_Pekerja` mengantre di latar belakang. Aktif bila `KALA_OPERATOR=ui`. |
| `backend/kawal_agent/sinkron.py` | `sinkron(state, ref, lewati=...)`: bagian `bahan`, `produk`, `pemetaan`, `komitmen` dilewati dan dikerjakan operator. |
| `backend/kawal_agent/tools.py` | `_sinkron()` mengantre ke operator bila aktif; `_pengajuan()` menunggu operator selesai. |
| `backend/tests/test_operator_ui.py` | Tes rencana (murni) dan satu tes browser nyata. |
| `backend/latih_operator.py` | Latihan 7 beat dengan Gemini asli. Jalankan dari `backend`. |
| `frontend/src/pages/ubah/shared.tsx` | Isian operator ditandai KawalHalal lewat `window.__kalaOperator`. |

Cara menjalankan: `cd backend`, lalu `.venv/Scripts/python -m pytest tests -q` (harus 82 lulus), lalu `.venv/Scripts/python latih_operator.py`.

**Penting:** build frontend untuk uji harus `VITE_API_MODE=http npm run build` di folder `frontend`. Tanpa itu halaman memakai data tiruan dan operator tidak menemukan pengajuan.

## 2. Yang kamu kerjakan

Kerjakan berurutan. Tiap tahap harus bisa di-merge sendiri dan tes tetap hijau.

### Tahap 1. Operator menjadi agen ADK
- Buat `backend/kawal_agent/agen_operator.py` dengan `LlmAgent` bernama `operator`, model ringan (tambah env `GEMINI_MODEL_RINGAN`, bawaan sama dengan `GEMINI_MODEL`).
- Tool untuk agen ini, semuanya membungkus kode yang sudah ada: `lihat_rencana()` (hasil `rencana()`), `kerjakan_tugas(nomor)` (menjalankan satu langkah lewat `_Layar.lakukan`), `lihat_layar(tab)` (teks halaman). Tidak ada tool yang menyentuh `sihalal_mock`.
- Agen memutuskan urutan, mengulang langkah yang gagal, dan melapor. Instruksi pendek: kerjakan semua langkah, ulangi yang gagal satu kali, jangan mengarang data.
- Hubungkan di `_Pekerja._kerjakan` (`operator_ui.py`): bila `KALA_OPERATOR_AGEN=1`, jalankan agen operator pada `Runner` sendiri (sesi terpisah dari Kala, di loop agen lewat `kirim_ke_loop_agen`). Bila bukan, tetap `_pelaksana_playwright`. **Cadangan ini wajib tetap ada**: kalau model gagal atau terkena 429, demo tetap jalan.
- Selesai bila: tes baru dengan LLM terskrip (lihat `tests/test_agen_runner.py::LLMTerskrip`) membuktikan agen memanggil `kerjakan_tugas` untuk tiap langkah, dan latihan nyata mengisi bahan 5/5.

### Tahap 2. Pemeriksa
- Buat agen kedua `pemeriksa` (model ringan). Tool: `baca_tab(tab)` (isi tab dari layar, boleh lewat `GET /api/sihalal/pengajuan/{id}` seperti yang dilihat halaman) dan `niat_kala()` (state yang diserahkan).
- Setelah operator selesai, pemeriksa membandingkan dan mengembalikan daftar selisih. Bila ada selisih, operator mengulang satu kali, lalu hasilnya disimpan di `riwayat(pid)`.
- `periksa_pengajuan` di `tools.py` menyertakan hasil pemeriksa ke Kala supaya Kala bisa menjelaskan ke pengguna.
- Selesai bila: tes dengan selisih buatan (hapus satu bahan lewat API) memicu pengulangan, dan tidak ada pengulangan tak berujung.

### Tahap 3. Kala sebagai orkestrator
- Perbarui `INSTRUKSI_OPERATOR` di `prompts.py` bila perilaku berubah. Kala tidak boleh mengklaim sesuatu sudah masuk sebelum `lihat_progres` atau pemeriksa menunjukkannya.
- Jangan mengubah gerbang YA (`gates.py`) dan callback `_awal_giliran` di `agent.py`. Itu penjaga keamanan.

### Tahap 4. Rutinitas formulir yang masih kurang
Operator belum mengisi tab Proses dan lampiran, jadi itu masih ditulis langsung oleh `sinkron.sinkron`. Tambahkan ke `rencana()` dan `_Layar.lakukan()`: alur proses, penyimpanan, hasil produksi, distribusi, upload layout dan tanda tangan (`set_input_files`), dan tombol Kirim di halaman detail. Setiap bagian yang pindah ke operator harus ditambahkan ke `BAGIAN_FORMULIR`. Pola yang sama dengan bagian yang sudah ada: id elemen ada di `frontend/src/pages/ubah/TabProses.tsx`.

### Tahap 5. Opsional
- Panel "aktivitas operator" di web SIHALAL yang membaca `GET /api/agent/operator/{id}` (perlu header `X-Dev-Key`, jadi pikirkan cara aman).
- Mode terlihat: `OPERATOR_TAMPIL=1` membuka browser berkepala supaya penonton melihat operator bekerja.

## 3. Aturan yang tidak boleh dilanggar

1. Persetujuan komitmen dan konfirmasi bahan bercelah hanya dari balasan YA pengguna. Operator hanya mengeklik "Saya setuju" bila `state["persetujuan"]` sudah memuatnya.
2. Operator tidak membaca atau menulis `sihalal_mock` langsung untuk bagian yang sudah dipindah ke formulir.
3. Kala tidak pernah menyatakan produk halal. Guardrail di `agent.py` dibiarkan.
4. Jaga idempotensi: menjalankan ulang tidak boleh menggandakan data. Pencocokan memakai nama tanpa membedakan huruf besar kecil.
5. Mode lama harus tetap bisa dipakai lewat flag. Tes lama (tanpa browser) tetap hijau.
6. Jangan menjalankan server lokal dengan `TELEGRAM_BOT_TOKEN` aktif selagi bot Cloud Run hidup (galat 409). Pakai `TELEGRAM_NONAKTIF=1`.
7. Jangan commit token, kunci, atau isi `.env`.

## 4. Risiko dan cara menghadapinya

| Risiko | Penanganan |
|---|---|
| Panggilan LLM menambah waktu | Model ringan, beberapa tool call sekaligus, dan operator berjalan di latar belakang. Ukur dengan `latih_operator.py`. |
| Kuota Gemini (429) | Cadangan deterministik (Tahap 1). Jangan memanggil model tanpa perlu. |
| Elemen halaman berubah | Tombol dicari lewat nama yang terlihat; ubah lokator di `_Layar`, bukan di banyak tempat. |
| Pengulangan tak berujung | Batasi percobaan (sekarang 2). |
| Waktu demo molor | Mode lama dan mode operator dapat diganti hanya lewat env. |

## 5. Cara memeriksa pekerjaanmu

1. `python -m pytest tests -q` hijau.
2. `python latih_operator.py` selesai tanpa baris "Gagal", dengan bahan 5/5 dan produk 1/1.
3. Buka web SIHALAL lokal saat latihan berjalan: isian muncul bertahap, bertanda ✦.
4. Minta Rafel menjalankan satu demo penuh di Telegram sebelum merge ke `main`.
