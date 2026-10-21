import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { PerubahanBagian } from "./client.ts";
import { api } from "./sumber.ts";
import type { BuatPengajuan, Pengajuan } from "./types.ts";

/** Interval polling saat agen sedang mengisi, supaya field tampak terisi langsung. */
export const LIVE_MS = 1500;

export const kunci = {
  pelakuUsaha: ["pelaku-usaha"] as const,
  daftarPengajuan: ["pengajuan"] as const,
  pengajuan: (id: string) => ["pengajuan", id] as const,
};

interface OpsiLive {
  /** Aktifkan polling (layar demo dan halaman yang sedang diisi agen). */
  live?: boolean;
}

// ---------- Query ----------

export function usePelakuUsaha() {
  return useQuery({ queryKey: kunci.pelakuUsaha, queryFn: () => api.getPelakuUsaha() });
}

export function useDaftarPengajuan({ live = false }: OpsiLive = {}) {
  return useQuery({
    queryKey: kunci.daftarPengajuan,
    queryFn: () => api.daftarPengajuan(),
    refetchInterval: live ? LIVE_MS : false,
  });
}

export function usePengajuan(id: string | undefined, { live = false }: OpsiLive = {}) {
  return useQuery({
    queryKey: kunci.pengajuan(id ?? ""),
    queryFn: () => api.getPengajuan(id!),
    enabled: Boolean(id),
    refetchInterval: live ? LIVE_MS : false,
  });
}

// ---------- Mutasi ----------

/** Simpan hasil mutasi ke cache detail lalu segarkan daftar. */
function useSimpanPengajuan() {
  const qc = useQueryClient();
  return (p: Pengajuan) => {
    qc.setQueryData(kunci.pengajuan(p.id), p);
    return qc.invalidateQueries({ queryKey: kunci.daftarPengajuan, exact: true });
  };
}

export function useUbahPelakuUsaha() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.ubahPelakuUsaha,
    onSuccess: (pu) => qc.setQueryData(kunci.pelakuUsaha, pu),
  });
}

export function useBuatPengajuan() {
  const simpan = useSimpanPengajuan();
  return useMutation({
    mutationFn: (isi: BuatPengajuan) => api.buatPengajuan(isi),
    onSuccess: simpan,
  });
}

/** Ubah satu bagian pengajuan, misalnya { bagian: "bahan", isi: {...} }. */
export function useUbahBagian(id: string) {
  const simpan = useSimpanPengajuan();
  return useMutation({
    mutationFn: (perubahan: PerubahanBagian) => api.ubahBagian(id, perubahan),
    onSuccess: simpan,
  });
}

/** Human gate 2: hanya dipanggil dari tombol Kirim yang diklik pengguna. */
export function useKirimPengajuan(id: string) {
  const simpan = useSimpanPengajuan();
  return useMutation({
    mutationFn: () => api.kirimPengajuan(id),
    onSuccess: simpan,
  });
}

export function useResetDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.resetDemo(),
    onSuccess: () => qc.invalidateQueries(),
  });
}
