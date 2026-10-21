import type { StatusBukti, StatusKonfirmasi, StatusPengajuan } from "../api/types.ts";
import type { StatusTone } from "../components/ui/StatusBadge.tsx";

interface Tampilan {
  label: string;
  tone: StatusTone;
}

export const statusPengajuan: Record<StatusPengajuan, Tampilan> = {
  draf: { label: "Draf", tone: "neutral" },
  terkirim: { label: "Terkirim", tone: "info" },
  "verifikasi-pendamping": { label: "Verifikasi Pendamping", tone: "info" },
  "verifikasi-bpjph": { label: "Verifikasi BPJPH", tone: "info" },
  dikembalikan: { label: "Dikembalikan", tone: "warn" },
  "sttd-terbit": { label: "STTD Terbit", tone: "info" },
  "sidang-fatwa": { label: "Sidang Fatwa", tone: "info" },
  "sh-terbit": { label: "Sertifikat Terbit", tone: "ok" },
};

/** Urutan alur resmi self-declare untuk timeline status. "dikembalikan" bukan tahap, jadi tidak masuk. */
export const urutanStatus: StatusPengajuan[] = [
  "draf",
  "terkirim",
  "verifikasi-pendamping",
  "verifikasi-bpjph",
  "sttd-terbit",
  "sidang-fatwa",
  "sh-terbit",
];

export const statusBukti: Record<StatusBukti, Tampilan> = {
  ada: { label: "Ada", tone: "ok" },
  kurang: { label: "Kurang", tone: "risk" },
  "tidak-jelas": { label: "Tidak jelas", tone: "warn" },
};

export const statusKonfirmasi: Record<StatusKonfirmasi, Tampilan> = {
  terkonfirmasi: { label: "Terkonfirmasi", tone: "neutral" },
  "perlu-konfirmasi": { label: "Perlu konfirmasi", tone: "warn" },
};
