import type { SelectOption } from "../components/ui/Select.tsx";

/** Klasifikasi produk dan rinciannya (disederhanakan dari daftar SIHALAL untuk demo). */
export const klasifikasiProduk: Record<string, string[]> = {
  Makanan: ["Produk olahan daging", "Makanan siap saji", "Roti dan kue", "Makanan ringan", "Bumbu dan saus"],
  Minuman: ["Minuman berbasis teh", "Minuman berbasis kopi", "Minuman sari buah", "Minuman lainnya"],
};

export const opsiKlasifikasi: SelectOption[] = Object.keys(klasifikasiProduk).map((k) => ({ value: k, label: k }));

export function opsiRincian(klasifikasi: string): SelectOption[] {
  return (klasifikasiProduk[klasifikasi] ?? []).map((r) => ({ value: r, label: r }));
}

export const opsiSatuan: SelectOption[] = ["kg", "gram", "liter", "ml", "pcs", "bungkus", "kotak"].map((s) => ({
  value: s,
  label: s,
}));

export const opsiAreaPemasaran: SelectOption[] = [
  { value: "kabupaten-kota", label: "Kabupaten/Kota" },
  { value: "provinsi", label: "Provinsi" },
  { value: "nasional", label: "Nasional" },
];

export const opsiJenisPendaftaran: SelectOption[] = [
  { value: "mandiri", label: "Mandiri" },
  { value: "fasilitasi", label: "Fasilitasi (misalnya SEHATI)" },
];

export const opsiTipeBahan: SelectOption[] = [
  { value: "bersertifikat", label: "Bahan bersertifikat halal" },
  { value: "tidak-bersertifikat", label: "Bahan tidak bersertifikat" },
];

export const opsiJenisBahan: SelectOption[] = [
  { value: "bahan", label: "Bahan" },
  { value: "kemasan", label: "Kemasan" },
  { value: "cleaning-agent", label: "Bahan pembersih" },
];

export const labelJenisBahan: Record<string, string> = {
  bahan: "Bahan",
  kemasan: "Kemasan",
  "cleaning-agent": "Bahan pembersih",
};
