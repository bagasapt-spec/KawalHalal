# Panduan Frontend KawalHalal (Mock SIHALAL)

Panduan ini untuk tim yang melanjutkan backend dan agen. Isinya: cara menjalankan, kontrak API yang dipakai frontend, cara agen mengisi data supaya tampil di web, dan daftar komponen bila perlu mengubah tampilan.

Ringkasnya: frontend adalah tiruan web SIHALAL (ptsp.halal.go.id) yang membaca dan menulis data lewat `/api/sihalal/*`. Backend menyimpan data itu di memori (`backend/sihalal_mock.py`). Agen menulis ke penyimpanan yang sama lewat fungsi `isi_sihalal_*`, lalu web menampilkannya dalam ±1,5 detik tanpa refresh.

---

## 1. Menjalankan

**Backend** (folder `backend`, Python 3.11+):

```bash
python -m venv venv
./venv/Scripts/python -m pip install -r requirements.txt
./venv/Scripts/python -m uvicorn main:app --port 8000 --reload
```

**Frontend** (folder `frontend`, Node 20+):

```bash
npm install
npm run dev
```

Buka http://localhost:5173, masuk dengan akun demo `bakso.paksam` / `demo1234` (atau klik **Isi akun demo**).

**Mode data** diatur di `frontend/.env.development`:

| Nilai `VITE_API_MODE` | Sumber data | Kapan dipakai |
|---|---|---|
| `http` (bawaan) | FastAPI lewat proxy `/api` ke `localhost:8000` | Kerja bareng backend dan agen |
| `mock` | Fixture di memori browser (`src/mocks/mockApi.ts`) | Mengubah tampilan tanpa backend |

Untuk ganti mode di laptop sendiri tanpa mengubah file tim, buat `frontend/.env.development.local` berisi `VITE_API_MODE=mock`, lalu restart `npm run dev`.

Perintah lain: `npm run build` (typecheck + build), `npm run typecheck`.

---

## 2. Gambaran arsitektur

```
Browser (React)                          Server (FastAPI)
  halaman SIHALAL tiruan                   backend/main.py
    └─ hooks TanStack Query  ──/api──▶       └─ include_router(sihalal_router)
         (polling 1,5 detik)                       backend/sihalal_mock.py
                                                     ├─ endpoint /api/sihalal/*
                                                     ├─ penyimpanan di memori
                                                     └─ tool agen isi_sihalal_*  ◀── agent.py (Gemini)
```

- Data awal backend dibaca dari **fixture frontend yang sama**: `frontend/src/mocks/fixtures/*.json`. Ubah fixture di satu tempat, kedua mode ikut berubah. Lokasinya bisa diganti dengan env `SIHALAL_FIXTURES_DIR`.
- Data hanya di memori. Hilang saat server restart, termasuk saat `--reload` mendeteksi file Python berubah. Untuk Cloud Run pakai max-instances 1.

---

## 3. Kontrak API

Sumber kebenaran bentuk data: **`frontend/src/api/types.ts`**. Backend harus mengembalikan JSON dengan nama field yang sama persis (camelCase). Contoh isi lengkap ada di fixture.

| Method | Path | Body | Balasan |
|---|---|---|---|
| GET | `/api/sihalal/pelaku-usaha` | | `PelakuUsaha` |
| PATCH | `/api/sihalal/pelaku-usaha` | `PelakuUsaha` utuh | `PelakuUsaha` |
| GET | `/api/sihalal/pengajuan` | | `PengajuanRingkas[]`, terbaru dulu |
| POST | `/api/sihalal/pengajuan` | `{ jalur, jenisLayanan }` | `Pengajuan` draf baru |
| GET | `/api/sihalal/pengajuan/{id}` | | `Pengajuan` |
| PATCH | `/api/sihalal/pengajuan/{id}/{bagian}` | isi bagian utuh | `Pengajuan` |
| POST | `/api/sihalal/pengajuan/{id}/kirim` | | `Pengajuan` (status `terkirim`, dapat `nomorDaftar`) |
| GET | `/api/sihalal/pengajuan/{id}/dokumen/{surat-permohonan\|sjph}` | | HTML untuk diunduh |
| POST | `/api/demo/reset` | | 204, data kembali ke fixture |
| POST | `/api/demo/agen/{nama_tool}` | argumen tool | hasil tool (khusus latihan demo) |

`{bagian}` salah satu dari: `data`, `komitmen`, `bahan`, `produk`, `proses`, `pemetaan`, `pemantauan`. Frontend selalu mengirim **seluruh isi bagian**, bukan satu item. `produk` dan `pemetaan` berupa array, sisanya objek.

**Galat.** Frontend menampilkan `detail` apa adanya di toast, jadi tulis pesannya dalam Bahasa Indonesia: sebut masalahnya lalu langkah berikutnya.

| Kode | Kapan | Contoh `detail` |
|---|---|---|
| 404 | Id tidak ada | "Pengajuan tidak ditemukan. Kembali ke daftar pengajuan lalu pilih lagi." |
| 409 | Ubah/kirim pengajuan yang sudah dikirim | "Pengajuan ini sudah dikirim." |
| 422 | Kirim saat belum lengkap, atau format salah | "Pengajuan belum lengkap di tab Bahan, Proses. Lengkapi isian lalu kirim lagi." |

Galat 4xx tidak di-retry oleh frontend.

### Aturan kelengkapan

Dipakai untuk progres tab ("3/5"), kolom Kelengkapan di daftar, dan validasi kirim. Ada di dua tempat dan **harus sama**:

- Frontend: `frontend/src/lib/kelengkapan.ts`
- Backend: `hitung_kelengkapan()` di `backend/sihalal_mock.py`

Kalau mengubah aturan di satu sisi, ubah juga sisi lainnya.

---

## 4. Supaya isian agen tampil sebagai "Diisi KawalHalal"

Setiap item yang bisa diisi agen punya field `sumber`:

```json
{ "oleh": "kawalhalal", "ref": "wa-msg-10", "waktu": "2026-10-21T14:14:00+07:00",
  "keyakinan": 0.61, "catatan": "Foto buram di bagian nomor" }
```

- `oleh: "kawalhalal"` membuat web menampilkan penanda ✦ dengan popover asal data. Isian dari pengguna (`oleh: "pengguna"`) tidak diberi penanda.
- `keyakinan` < 0,75 ditandai kuning dan masuk daftar "Perlu diperiksa" di halaman Detail.
- `ref` ditampilkan sebagai "Pesan WhatsApp wa-msg-10". `catatan` tampil sebagai kalimat pertama di popover.
- Untuk field `data` (merek, jenis produk, dst.), sumbernya disimpan di `data.sumberField[namaField]`.
- Untuk bahan, isi juga `fotoSumber: { "nama": "label-merica.jpg" }` supaya nama bukti tampil.
- Status bukti bahan: `bukti` = `ada` / `kurang` / `tidak-jelas`, dengan `alasanBukti` berupa kalimat yang menjelaskan langkah berikutnya. Isian agen sebaiknya `konfirmasi: "perlu-konfirmasi"`.

Hindari kata "halal", "lolos", atau "pasti disetujui" di teks yang tampil ke pengguna. Pakai "kelengkapan bukti" atau "kemungkinan jalur".

### Tool agen yang sudah tersedia

Di `backend/sihalal_mock.py`, dikumpulkan dalam `TOOLS_SIHALAL`. Semua otomatis menambah `sumber` agen dan mencatat audit.

| Fungsi | Gunanya |
|---|---|
| `isi_sihalal_buat_draf(jalur, jenis_layanan, ref_pesan)` | Buat draf pengajuan baru, mengembalikan `pengajuan_id` |
| `isi_sihalal_data(pengajuan_id, field, nilai, ref_pesan, keyakinan, catatan)` | Isi satu field Data Pengajuan |
| `isi_sihalal_tambah_bahan(pengajuan_id, nama, jenis, produsen, nomor_sertifikat, foto_bukti, ref_pesan, keyakinan, catatan)` | Tambah bahan; status bukti dihitung otomatis |
| `isi_sihalal_tambah_produk(pengajuan_id, nama, klasifikasi, rincian, ref_pesan, keyakinan, catatan)` | Tambah produk dengan semua bahan yang sudah tercatat |

Agen sengaja **tidak** punya tool untuk mengirim pengajuan. Kirim hanya lewat tombol di web (human gate).

**Mendaftarkan ke Gemini** di `backend/agent.py`:

```python
from sihalal_mock import TOOLS_SIHALAL

tools=[cek_sertifikat_bpjph, analisis_titik_kritis, *TOOLS_SIHALAL],
```

Tambahkan juga instruksi di `system_instruction`, misalnya: simpan bahan ke SIHALAL setelah pengguna membalas YA.

**Mencoba tanpa Gemini.** Buka http://localhost:5173/pengajuan, lalu jalankan:

```bash
curl -X POST -H "Content-Type: application/json" -d "{\"ref_pesan\":\"wa-msg-01\"}" http://localhost:8000/api/demo/agen/isi_sihalal_buat_draf
```

Draf baru muncul di daftar tanpa refresh. Pola yang sama berlaku untuk tool lain, dengan argumen sesuai nama parameternya.

### Menambah tool atau endpoint baru

1. Tulis fungsi di `sihalal_mock.py` dengan pola `isi_sihalal_tambah_bahan`: ambil pengajuan dengan `_cari`, salin bagian dengan `copy.deepcopy`, ubah, lalu simpan dengan `ubah_bagian(..., pelaku="kawalhalal", aksi="...", ref=...)`. Bungkus dengan `with _kunci:`.
2. Tambahkan fungsinya ke `TOOLS_SIHALAL`.
3. Kalau bentuk data berubah, ubah `frontend/src/api/types.ts` dan fixture-nya, lalu jalankan `npm run typecheck` di folder frontend.

---

## 5. Struktur folder frontend

```
frontend/src/
  api/
    types.ts        Kontrak data (mulai baca dari sini)
    client.ts       httpApi: pemanggil endpoint + ApiError
    sumber.ts       Memilih httpApi atau mockApi dari VITE_API_MODE
    hooks.ts        Hooks TanStack Query untuk semua halaman
    index.ts        Ekspor gabungan: import { usePengajuan } from "../api/index.ts"
  mocks/
    fixtures/       pelaku-usaha.json, pengajuan.json (juga seed backend)
    mockApi.ts      Backend tiruan di browser untuk mode mock
  lib/
    kelengkapan.ts  Aturan isian wajib per tab
    asal.ts         Ringkasan asal data dan ambang keyakinan
    status.ts       Label dan warna status pengajuan, bukti, konfirmasi
    format.ts       Format tanggal WIB dan label teks
    opsi.ts         Pilihan dropdown (klasifikasi produk, satuan, dll.)
    sesi.ts         Login tiruan dan akun demo
  components/
    ui/             Komponen dasar (tombol, input, tabel, modal, ...)
    layout/         AppShell, Sidebar, Topbar, PageHeader, WajibMasuk
    kawal/          Komponen khas KawalHalal (penanda asal data, dll.)
  pages/            Satu folder atau file per halaman
  styles/theme.css  Token desain (warna, font, spasi, radius)
```

---

## 6. Hooks untuk mengambil dan menyimpan data

Semua dari `src/api/index.ts`:

| Hook | Kegunaan |
|---|---|
| `usePelakuUsaha()` | Data pelaku usaha |
| `useDaftarPengajuan({ live })` | Daftar pengajuan; `live: true` untuk polling 1,5 detik |
| `usePengajuan(id, { live })` | Detail satu pengajuan |
| `useBuatPengajuan()` | Buat draf |
| `useUbahBagian(id)` | `mutate({ bagian: "bahan", isi: {...} })` |
| `useKirimPengajuan(id)` | Kirim (hanya dari tombol pengguna) |
| `useUbahPelakuUsaha()` | Simpan pelaku usaha |
| `useResetDemo()` | Kembalikan data ke fixture |

Contoh:

```tsx
const q = usePengajuan(id, { live: true });
const ubah = useUbahBagian(id);
ubah.mutate({ bagian: "bahan", isi: { ...q.data.bahan, daftarBahan: [...] } });
```

---

## 7. Katalog komponen

Lihat semuanya hidup di **http://localhost:5173/komponen** (hanya di mode dev). Impor dari `src/components/ui/index.ts`.

**Komponen dasar (`components/ui`)**

| Komponen | Catatan |
|---|---|
| `Button`, `ButtonLink` | Varian `primary`, `secondary`, `ghost`, `danger`; ukuran `sm`/`md`; prop `loading`, `icon`. Satu tombol primary per layar. |
| `IconButton` | Wajib prop `label` (untuk pembaca layar). |
| `Field` | Pembungkus label + tanda wajib + hint + galat. Pakai `hintId(id)` untuk `aria-describedby`. |
| `Input`, `Textarea`, `DateInput` | Prop `invalid`, dan `showCount` + `maxLength` untuk penghitung karakter. |
| `Select`, `Checkbox`, `FileInput` | `FileInput` mengembalikan `File`; ubah jadi `Berkas` dengan `keBerkas(file)`. |
| `Card`, `Seksi` | `Seksi` = kartu dengan tombol Tambah. |
| `DataTable` + `Pagination` | Tabel di desktop, kartu di HP. Sudah ada state memuat, galat, kosong. Kolom `primary` jadi judul kartu, kolom `action` jadi tombol. |
| `Modal`, `ConfirmDialog`, `KonfirmasiHapus` | Modal layar penuh di HP. |
| `Tabs` + `TabPanel` | Mendukung progres per tab. |
| `StatusBadge` | Tone `ok`, `warn`, `risk`, `info`, `neutral`; selalu ikon + label. |
| `SegmentedToggle`, `BerkasLabel`, `AksiBaris`, `useToast` | Pelengkap. |

**Komponen KawalHalal (`components/kawal`)**

| Komponen | Catatan |
|---|---|
| `ProvenanceMark`, `DenganTanda` | Penanda ✦ + popover asal data dari field `sumber`. |
| `BannerAsalData`, `KartuAsalData` | Ringkasan isian agen dan yang perlu diperiksa. |
| `KelengkapanMeter` | Bilah progres + angka. |
| `AuditTrail` | Riwayat aktivitas pengajuan. |
| `MockBanner` | Penanda "Tiruan untuk demo, bukan SIHALAL resmi". |

**Halaman dan rute**

| Rute | File |
|---|---|
| `/login` | `pages/Login.tsx` |
| `/` | `pages/Dashboard.tsx` |
| `/pelaku-usaha` | `pages/pelaku/PelakuUsaha.tsx` |
| `/pengajuan`, `/pengajuan-reguler` | `pages/pengajuan/DaftarPengajuan.tsx` |
| `/pengajuan/:id` | `pages/pengajuan/DetailPengajuan.tsx` |
| `/pengajuan/:id/ubah?tab=...` | `pages/ubah/UbahData.tsx` + `Tab*.tsx` |
| `/status` | `pages/pengajuan/StatusPermohonan.tsx` |
| `/tagihan`, `/revisi-sh` | `pages/Tagihan.tsx`, `pages/RevisiSh.tsx` |
| `/komponen` | `pages/Komponen.tsx` (dev saja) |

Semua rute kecuali `/login` dijaga `WajibMasuk`. Login hanya tiruan (dicocokkan di browser).

**Token desain.** Warna, font (Plus Jakarta Sans), spasi, dan radius ada di `src/styles/theme.css`. Tulis class Tailwind dengan nama peran (`bg-brand`, `text-ink-muted`, `border-line`), jangan menulis kode hex di komponen. Untuk ganti warna merek, cukup ubah blok `@theme`.

---

## 8. Yang belum ada

- **Unggah berkas.** Web hanya menyimpan nama berkas. Perlu endpoint seperti `POST /api/sihalal/berkas` yang mengembalikan `{ nama, url }`, lalu `keBerkas()` di frontend diganti dengan pemanggilan unggah.
- **Tool agen belum didaftarkan di `agent.py`** (lihat bagian 4).
- **Penyimpanan permanen.** Data masih di memori server.
- **Tagihan** belum punya data di kontrak; halamannya hanya penjelasan dan tabel kosong.
- **Dokumen** berupa HTML sederhana, belum PDF.

---

## 9. Cek cepat setelah mengubah backend

1. `curl http://localhost:8000/api/sihalal/pengajuan` mengembalikan 3 pengajuan dengan kelengkapan 1/24, 20/24, 24/24.
2. `curl -X POST http://localhost:8000/api/sihalal/pengajuan/pj-1/kirim` mengembalikan 422 dengan daftar tab yang kurang.
3. Di web, buka draf pj-1 → Ubah Data, lalu panggil `isi_sihalal_tambah_bahan` lewat `/api/demo/agen/...`. Bahan baru muncul dengan penanda ✦ tanpa refresh.
4. Reset data dengan `curl -X POST http://localhost:8000/api/demo/reset`.
