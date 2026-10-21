import type { Jalur, JenisLayanan, DataPengajuan, Pelaku } from "../api/types.ts";
import type { TabPengajuan } from "./kelengkapan.ts";

const fmtTanggal = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Asia/Jakarta",
});

const fmtWaktu = new Intl.DateTimeFormat("id-ID", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Jakarta",
});

function parse(iso?: string | null) {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** "21 Okt 2026", atau "-" bila kosong. */
export function formatTanggal(iso?: string | null) {
  const d = parse(iso);
  return d ? fmtTanggal.format(d) : "-";
}

/** "21 Okt 2026, 14.31" (WIB), atau "-" bila kosong. */
export function formatWaktu(iso?: string | null) {
  const d = parse(iso);
  return d ? fmtWaktu.format(d) : "-";
}

/** Urutkan terbaru dulu; aman untuk zona waktu berbeda (+07:00 dan Z). */
export function terbaruDulu<T>(ambil: (x: T) => string) {
  return (a: T, b: T) => Date.parse(ambil(b)) - Date.parse(ambil(a));
}

export const labelJalur: Record<Jalur, string> = {
  "self-declare": "Self Declare",
  reguler: "Reguler",
};

export const labelLayanan: Record<JenisLayanan, string> = {
  baru: "Baru",
  pengembangan: "Pengembangan",
};

export const labelArea: Record<DataPengajuan["areaPemasaran"], string> = {
  "kabupaten-kota": "Kabupaten/Kota",
  provinsi: "Provinsi",
  nasional: "Nasional",
};

export const labelPendaftaran: Record<DataPengajuan["jenisPendaftaran"], string> = {
  mandiri: "Mandiri",
  fasilitasi: "Fasilitasi",
};

export const labelPelaku: Record<Pelaku, string> = {
  kawalhalal: "KawalHalal",
  pengguna: "Pelaku usaha",
  pendamping: "Pendamping PPH",
  sistem: "Sistem",
};

/** Nama tab di halaman Ubah Data, sama dengan SIHALAL. */
export const labelTab: Record<TabPengajuan, string> = {
  data: "Data Pengajuan",
  komitmen: "Komitmen dan Tanggung Jawab",
  bahan: "Bahan",
  proses: "Proses",
  produk: "Produk",
  pemantauan: "Pemantauan dan Evaluasi",
};

export const urutanTab: TabPengajuan[] = ["data", "komitmen", "bahan", "proses", "produk", "pemantauan"];
