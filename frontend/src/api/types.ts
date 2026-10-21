/*
 * Tipe data mock SIHALAL. Ini kontrak antara frontend dan backend (/api/sihalal/*):
 * backend mengembalikan JSON dengan bentuk yang sama persis. Contoh isinya ada di src/mocks/fixtures.
 * Tanggal memakai string ISO 8601, misalnya "2026-10-21T14:02:00+07:00".
 */

// ---------- Umum ----------

export type Pelaku = "kawalhalal" | "pengguna" | "pendamping" | "sistem";

/** Asal sebuah data: siapa yang mengisi dan dari pesan WhatsApp mana. Menggerakkan penanda "Diisi KawalHalal". */
export interface Sumber {
  oleh: Pelaku;
  /** Rujukan ke pesan atau berkas asal, misalnya "wa-msg-07". */
  ref?: string;
  waktu: string;
  /** Keyakinan ekstraksi agen, 0 sampai 1. Hanya untuk oleh = "kawalhalal". */
  keyakinan?: number;
  /** Keterangan singkat, misalnya "Dibaca dari foto label". */
  catatan?: string;
}

export interface Berkas {
  nama: string;
  /** Kosong bila berkas hanya contoh di fixture. */
  url?: string;
}

/** Persetujuan pernyataan (Kebijakan Halal, Bebas Babi, dll.). null berarti belum disetujui. */
export interface Persetujuan {
  disetujuiPada: string;
  sumber?: Sumber;
}

// ---------- Pelaku usaha ----------

export type SkalaUsaha = "mikro" | "kecil" | "menengah" | "besar";

export interface PenanggungJawab {
  nama: string;
  noHp: string;
  email: string;
}

export interface AspekLegal {
  id: string;
  jenis: "NIB" | "NPWP" | "IUMK" | "SIUP" | "Lainnya";
  nomor: string;
  tanggal: string;
  masaBerlaku?: string;
  instansiPenerbit: string;
}

export interface Alamat {
  alamat: string;
  provinsi: string;
  kabKota: string;
  kodePos: string;
}

export interface Pabrik extends Alamat {
  id: string;
  nama: string;
  status: "milik-sendiri" | "sewa" | "maklon";
}

export interface Outlet extends Alamat {
  id: string;
  nama: string;
}

export interface PenyeliaHalal {
  id: string;
  nama: string;
  noKtp: string;
  agama: string;
  noSertifikat?: string;
  tanggalSertifikat?: string;
  noSk?: string;
  tanggalSk?: string;
  berkasKtp?: Berkas;
}

export interface PelakuUsaha extends Alamat {
  id: string;
  namaUsaha: string;
  nib: string;
  skala: SkalaUsaha;
  penanggungJawab: PenanggungJawab;
  aspekLegal: AspekLegal[];
  pabrik: Pabrik[];
  outlet: Outlet[];
  penyeliaHalal: PenyeliaHalal[];
}

// ---------- Pengajuan ----------

export type Jalur = "self-declare" | "reguler";
export type JenisLayanan = "baru" | "pengembangan";

/** Urutan alur self-declare, ditambah "dikembalikan" bila verifikator meminta perbaikan. */
export type StatusPengajuan =
  | "draf"
  | "terkirim"
  | "verifikasi-pendamping"
  | "verifikasi-bpjph"
  | "dikembalikan"
  | "sttd-terbit"
  | "sidang-fatwa"
  | "sh-terbit";

/** Bagian yang bisa diubah lewat PATCH /pengajuan/{id}/{bagian}. */
export type BagianPengajuan = "data" | "komitmen" | "bahan" | "produk" | "proses" | "pemetaan" | "pemantauan";

export interface DataPengajuan {
  nomorSurat: string;
  tanggalSurat: string;
  /** Klasifikasi produk utama, misalnya "Makanan". */
  jenisProduk: string;
  merek: string;
  areaPemasaran: "kabupaten-kota" | "provinsi" | "nasional";
  jenisPendaftaran: "mandiri" | "fasilitasi";
  kodeFasilitasi?: string;
  /** Pendamping Proses Produk Halal (khusus self-declare). */
  pendampingPph?: string;
  pabrikIds: string[];
  outletIds: string[];
  penyeliaIds: string[];
  /** Asal tiap field yang diisi agen, kunci = nama field. */
  sumberField: Partial<Record<Exclude<keyof DataPengajuan, "sumberField">, Sumber>>;
}

export interface AnggotaKomitmen {
  id: string;
  nama: string;
  jabatan: string;
  posisi: "ketua" | "anggota";
  sumber?: Sumber;
}

export interface Komitmen {
  kebijakanHalal: Persetujuan | null;
  pengertianHalalHaram: Persetujuan | null;
  praktikSjph: Persetujuan | null;
  anggota: AnggotaKomitmen[];
}

/** Status bukti bahan (design system, BR-08). */
export type StatusBukti = "ada" | "kurang" | "tidak-jelas";
/** Status pemeriksaan bahan oleh pengguna. Bukan penilaian halal. */
export type StatusKonfirmasi = "terkonfirmasi" | "perlu-konfirmasi";

export interface Bahan {
  id: string;
  tipe: "bersertifikat" | "tidak-bersertifikat";
  jenis: "bahan" | "kemasan" | "cleaning-agent";
  nama: string;
  produsen?: string;
  noSertifikat?: string;
  bukti: StatusBukti;
  /** Alasan status bukti, ditampilkan di samping badge. */
  alasanBukti?: string;
  konfirmasi: StatusKonfirmasi;
  fotoSumber?: Berkas;
  sumber?: Sumber;
}

export interface CatatanPembelian {
  id: string;
  bahanId: string;
  jumlah: number;
  satuan: string;
  tanggal: string;
  berkas?: Berkas;
  sumber?: Sumber;
}

export interface PemeriksaanBahan {
  id: string;
  bahanId: string;
  lokasi: string;
  tanggal: string;
  berkas?: Berkas;
  sumber?: Sumber;
}

export interface BagianBahan {
  daftarBahan: Bahan[];
  catatanPembelian: CatatanPembelian[];
  pemeriksaan: PemeriksaanBahan[];
}

export interface Produk {
  id: string;
  klasifikasi: string;
  rincian: string;
  nama: string;
  merek?: string;
  foto?: Berkas;
  /** Bahan yang dipakai produk ini (Input Bahan). */
  bahanIds: string[];
  sumber?: Sumber;
}

export interface LayoutProduksi {
  id: string;
  pabrikId: string;
  berkas: Berkas;
  sumber?: Sumber;
}

export interface CatatanPenyimpanan {
  id: string;
  jenis: "bahan" | "produk";
  /** bahanId atau produkId sesuai jenis. */
  refId: string;
  jumlah: number;
  tanggalMasuk: string;
  tanggalKeluar?: string;
  berkas?: Berkas;
  sumber?: Sumber;
}

export interface AlurProses {
  id: string;
  judul: string;
  langkah: string[];
  berkas?: Berkas;
  sumber?: Sumber;
}

export interface HasilProduksi {
  id: string;
  produkId: string;
  jumlah: number;
  tanggalProduksi: string;
  tanggalKedaluwarsa?: string;
  sumber?: Sumber;
}

export interface Distribusi {
  id: string;
  produkId?: string;
  jumlah?: number;
  tanggal?: string;
  tujuan: string;
  berkas?: Berkas;
  sumber?: Sumber;
}

export interface BagianProses {
  pernyataanBebasBabi: Persetujuan | null;
  layout: LayoutProduksi[];
  penyimpanan: CatatanPenyimpanan[];
  alurProses: AlurProses[];
  hasilProduksi: HasilProduksi[];
  distribusi: Distribusi[];
}

export interface PemetaanProduk {
  id: string;
  produkId: string;
  pabrikId: string;
}

export interface DokumenLain {
  id: string;
  nama: string;
  berkas: Berkas;
}

export interface TandaTangan {
  id: string;
  penanggungJawab: Berkas;
  penyeliaId: string;
  penyelia: Berkas;
  sumber?: Sumber;
}

export interface BagianPemantauan {
  /** Hanya untuk skala menengah dan besar. */
  dokumenLain: DokumenLain[];
  tandaTangan: TandaTangan[];
}

export interface RiwayatStatus {
  status: StatusPengajuan;
  waktu: string;
  catatan?: string;
}

export interface AuditEntri {
  id: string;
  waktu: string;
  pelaku: Pelaku;
  /** Kalimat singkat, misalnya "Menambahkan 7 bahan dari foto label". */
  aksi: string;
  bagian?: BagianPengajuan;
  ref?: string;
}

export interface Pengajuan {
  id: string;
  /** Diberikan saat pengajuan dikirim; null selama draf. */
  nomorDaftar: string | null;
  jalur: Jalur;
  jenisLayanan: JenisLayanan;
  status: StatusPengajuan;
  namaUsaha: string;
  dibuat: string;
  diperbarui: string;
  data: DataPengajuan;
  komitmen: Komitmen;
  bahan: BagianBahan;
  produk: Produk[];
  proses: BagianProses;
  pemetaan: PemetaanProduk[];
  pemantauan: BagianPemantauan;
  riwayat: RiwayatStatus[];
  audit: AuditEntri[];
}

/** Isi body PATCH /pengajuan/{id}/{bagian}: seluruh bagian dikirim ulang. */
export interface IsiBagian {
  data: DataPengajuan;
  komitmen: Komitmen;
  bahan: BagianBahan;
  produk: Produk[];
  proses: BagianProses;
  pemetaan: PemetaanProduk[];
  pemantauan: BagianPemantauan;
}

/** Baris di GET /pengajuan (daftar), lebih ringan dari Pengajuan. */
export interface PengajuanRingkas {
  id: string;
  nomorDaftar: string | null;
  jalur: Jalur;
  jenisLayanan: JenisLayanan;
  status: StatusPengajuan;
  namaUsaha: string;
  jenisProduk: string;
  jumlahProduk: number;
  dibuat: string;
  diperbarui: string;
  /** Jumlah isian wajib yang sudah terpenuhi di seluruh tab. */
  kelengkapan: { done: number; total: number };
}

/** Body POST /pengajuan. */
export interface BuatPengajuan {
  jalur: Jalur;
  jenisLayanan: JenisLayanan;
}

export type JenisDokumen = "surat-permohonan" | "sjph";
