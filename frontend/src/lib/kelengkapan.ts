import type { Pengajuan } from "../api/types.ts";

/** Tab di halaman Ubah Data yang punya isian wajib. Tab Dokumen tidak dihitung. */
export type TabPengajuan = "data" | "komitmen" | "bahan" | "proses" | "produk" | "pemantauan";

export interface Skor {
  done: number;
  total: number;
}

export type Kelengkapan = Record<TabPengajuan, Skor>;

function hitung(cek: boolean[]): Skor {
  return { done: cek.filter(Boolean).length, total: cek.length };
}

/**
 * Hitung isian wajib per tab. Aturan yang sama perlu dipakai backend
 * untuk field kelengkapan di GET /pengajuan dan validasi saat kirim.
 */
export function hitungKelengkapan(p: Pengajuan): Kelengkapan {
  const { data, komitmen, bahan, produk, proses, pemetaan, pemantauan } = p;
  const bahanIds = bahan.daftarBahan.map((b) => b.id);
  const semuaBahanTercatat = (list: Array<{ bahanId: string }>) =>
    bahanIds.length > 0 && bahanIds.every((id) => list.some((x) => x.bahanId === id));

  return {
    data: hitung([
      data.nomorSurat !== "",
      data.tanggalSurat !== "",
      data.jenisProduk !== "",
      data.merek !== "",
      data.jenisPendaftaran === "mandiri" || Boolean(data.kodeFasilitasi),
      data.pabrikIds.length > 0,
      data.penyeliaIds.length > 0,
    ]),
    komitmen: hitung([
      komitmen.kebijakanHalal !== null,
      komitmen.pengertianHalalHaram !== null,
      komitmen.praktikSjph !== null,
      komitmen.anggota.length > 0,
    ]),
    bahan: hitung([
      bahan.daftarBahan.length > 0,
      produk.length > 0,
      produk.length > 0 && produk.every((pr) => pr.bahanIds.length > 0),
      semuaBahanTercatat(bahan.catatanPembelian),
      semuaBahanTercatat(bahan.pemeriksaan),
    ]),
    proses: hitung([
      proses.pernyataanBebasBabi !== null,
      proses.layout.length > 0,
      proses.penyimpanan.length > 0,
      proses.alurProses.length > 0,
      proses.hasilProduksi.length > 0,
      proses.distribusi.length > 0,
    ]),
    produk: hitung([produk.length > 0 && produk.every((pr) => pemetaan.some((m) => m.produkId === pr.id))]),
    pemantauan: hitung([pemantauan.tandaTangan.length > 0]),
  };
}

export function totalKelengkapan(k: Kelengkapan): Skor {
  return Object.values(k).reduce((acc, s) => ({ done: acc.done + s.done, total: acc.total + s.total }), { done: 0, total: 0 });
}

export function lengkap(s: Skor) {
  return s.total > 0 && s.done >= s.total;
}
