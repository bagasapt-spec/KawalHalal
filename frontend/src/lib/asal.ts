import type { DataPengajuan, Pengajuan, Persetujuan, Sumber } from "../api/types.ts";
import type { TabPengajuan } from "./kelengkapan.ts";

/** Di bawah nilai ini isian agen dianggap perlu diperiksa ulang oleh pengguna. */
export const BATAS_KEYAKINAN_RENDAH = 0.75;

export type TingkatKeyakinan = "tinggi" | "sedang" | "rendah";

export function tingkatKeyakinan(keyakinan?: number): TingkatKeyakinan | null {
  if (keyakinan === undefined) return null;
  if (keyakinan >= 0.9) return "tinggi";
  return keyakinan >= BATAS_KEYAKINAN_RENDAH ? "sedang" : "rendah";
}

export function perluDiperiksa(s?: Sumber) {
  return s?.oleh === "kawalhalal" && tingkatKeyakinan(s.keyakinan) === "rendah";
}

export interface ItemAsal {
  label: string;
  tab: TabPengajuan;
  sumber: Sumber;
}

const labelField: Record<Exclude<keyof DataPengajuan, "sumberField">, string> = {
  nomorSurat: "Nomor surat",
  tanggalSurat: "Tanggal surat",
  jenisProduk: "Jenis produk",
  merek: "Merek",
  areaPemasaran: "Area pemasaran",
  jenisPendaftaran: "Jenis pendaftaran",
  kodeFasilitasi: "Kode fasilitasi",
  pendampingPph: "Pendamping PPH",
  pabrikIds: "Pabrik",
  outletIds: "Outlet",
  penyeliaIds: "Penyelia halal",
};

/** Kumpulkan semua isian yang punya catatan asal, untuk ringkasan dan daftar periksa. */
export function kumpulkanAsal(p: Pengajuan): ItemAsal[] {
  const hasil: ItemAsal[] = [];
  const tambah = (label: string, tab: TabPengajuan, s?: Sumber) => {
    if (s) hasil.push({ label, tab, sumber: s });
  };
  const persetujuan = (label: string, tab: TabPengajuan, x: Persetujuan | null) => tambah(label, tab, x?.sumber);
  const namaBahan = (id: string) => p.bahan.daftarBahan.find((b) => b.id === id)?.nama ?? "bahan";
  const namaProduk = (id: string) => p.produk.find((x) => x.id === id)?.nama ?? "produk";

  for (const [kunci, s] of Object.entries(p.data.sumberField) as Array<[keyof typeof labelField, Sumber]>) {
    tambah(labelField[kunci] ?? kunci, "data", s);
  }
  persetujuan("Kebijakan Halal", "komitmen", p.komitmen.kebijakanHalal);
  persetujuan("Pengertian Halal dan Haram", "komitmen", p.komitmen.pengertianHalalHaram);
  persetujuan("Praktik SJPH", "komitmen", p.komitmen.praktikSjph);
  p.komitmen.anggota.forEach((a) => tambah(`Anggota komitmen ${a.nama}`, "komitmen", a.sumber));
  p.bahan.daftarBahan.forEach((b) => tambah(b.nama, "bahan", b.sumber));
  p.produk.forEach((x) => tambah(`Produk ${x.nama}`, "bahan", x.sumber));
  p.bahan.catatanPembelian.forEach((c) => tambah(`Pembelian ${namaBahan(c.bahanId)}`, "bahan", c.sumber));
  p.bahan.pemeriksaan.forEach((c) => tambah(`Pemeriksaan ${namaBahan(c.bahanId)}`, "bahan", c.sumber));
  persetujuan("Pernyataan Bebas Babi", "proses", p.proses.pernyataanBebasBabi);
  p.proses.layout.forEach((x) => tambah("Denah ruang produksi", "proses", x.sumber));
  p.proses.penyimpanan.forEach((x) =>
    tambah(`Penyimpanan ${x.jenis === "bahan" ? namaBahan(x.refId) : namaProduk(x.refId)}`, "proses", x.sumber),
  );
  p.proses.alurProses.forEach((x) => tambah(`Alur proses ${x.judul}`, "proses", x.sumber));
  p.proses.hasilProduksi.forEach((x) => tambah(`Hasil produksi ${namaProduk(x.produkId)}`, "proses", x.sumber));
  p.proses.distribusi.forEach((x) => tambah(`Distribusi ${x.tujuan}`, "proses", x.sumber));
  p.pemantauan.tandaTangan.forEach((x) => tambah("Tanda tangan", "pemantauan", x.sumber));
  return hasil;
}

export function ringkasAsal(items: ItemAsal[]) {
  const agen = items.filter((x) => x.sumber.oleh === "kawalhalal");
  return {
    agen: agen.length,
    rendah: agen.filter((x) => perluDiperiksa(x.sumber)),
    pengguna: items.filter((x) => x.sumber.oleh === "pengguna").length,
  };
}
