import { ApiError } from "../api/client.ts";
import type { SihalalApi } from "../api/client.ts";
import type { AuditEntri, BagianPengajuan, PelakuUsaha, Pengajuan, PengajuanRingkas } from "../api/types.ts";
import { hitungKelengkapan, lengkap, totalKelengkapan } from "../lib/kelengkapan.ts";
import type { TabPengajuan } from "../lib/kelengkapan.ts";
import { labelTab, terbaruDulu } from "../lib/format.ts";
import seedPelakuUsaha from "./fixtures/pelaku-usaha.json";
import seedPengajuan from "./fixtures/pengajuan.json";

/*
 * Pengganti backend yang hidup di memori browser. Perilakunya meniru kontrak /api/sihalal:
 * jeda jaringan, galat 404/409/422, nomor daftar saat kirim, dan catatan audit.
 * Data kembali ke fixture setiap halaman dimuat ulang atau resetDemo dipanggil.
 */

const JEDA_MS = 350;

let pelakuUsaha: PelakuUsaha;
let pengajuan: Pengajuan[];
let nomorBerikutnya: number;

function muatSeed() {
  pelakuUsaha = structuredClone(seedPelakuUsaha as PelakuUsaha);
  pengajuan = structuredClone(seedPengajuan as Pengajuan[]);
  nomorBerikutnya = 143;
}
muatSeed();

function jeda<T>(nilai: T): Promise<T> {
  // Selalu kirim salinan supaya cache TanStack Query tidak ikut termutasi
  return new Promise((resolve) => setTimeout(() => resolve(structuredClone(nilai)), JEDA_MS));
}

function sekarang() {
  return new Date().toISOString();
}

function cari(id: string) {
  const p = pengajuan.find((x) => x.id === id);
  if (!p) throw new ApiError(404, "Pengajuan tidak ditemukan. Kembali ke daftar pengajuan lalu pilih lagi.");
  return p;
}

function catat(p: Pengajuan, entri: Omit<AuditEntri, "id" | "waktu">) {
  p.audit.push({ id: `au-${Date.now()}`, waktu: sekarang(), ...entri });
  p.diperbarui = sekarang();
}

const namaBagian: Record<BagianPengajuan, string> = {
  data: "data pengajuan",
  komitmen: "komitmen dan tanggung jawab",
  bahan: "daftar bahan",
  produk: "daftar produk",
  proses: "proses produksi",
  pemetaan: "pemetaan produk dan pabrik",
  pemantauan: "pemantauan dan evaluasi",
};

function keRingkas(p: Pengajuan): PengajuanRingkas {
  return {
    id: p.id,
    nomorDaftar: p.nomorDaftar,
    jalur: p.jalur,
    jenisLayanan: p.jenisLayanan,
    status: p.status,
    namaUsaha: p.namaUsaha,
    jenisProduk: p.data.jenisProduk,
    jumlahProduk: p.produk.length,
    dibuat: p.dibuat,
    diperbarui: p.diperbarui,
    kelengkapan: totalKelengkapan(hitungKelengkapan(p)),
  };
}

export const mockApi: SihalalApi = {
  async getPelakuUsaha() {
    return jeda(pelakuUsaha);
  },

  async ubahPelakuUsaha(isi) {
    pelakuUsaha = structuredClone(isi);
    return jeda(pelakuUsaha);
  },

  async daftarPengajuan() {
    const urut = [...pengajuan].sort(terbaruDulu((p) => p.dibuat));
    return jeda(urut.map(keRingkas));
  },

  async getPengajuan(id) {
    return jeda(cari(id));
  },

  async buatPengajuan({ jalur, jenisLayanan }) {
    const waktu = sekarang();
    const baru: Pengajuan = {
      id: `pj-${Date.now()}`,
      nomorDaftar: null,
      jalur,
      jenisLayanan,
      status: "draf",
      namaUsaha: pelakuUsaha.namaUsaha,
      dibuat: waktu,
      diperbarui: waktu,
      data: {
        nomorSurat: "",
        tanggalSurat: "",
        jenisProduk: "",
        merek: "",
        areaPemasaran: "kabupaten-kota",
        jenisPendaftaran: "mandiri",
        pabrikIds: [],
        outletIds: [],
        penyeliaIds: [],
        sumberField: {},
      },
      komitmen: { kebijakanHalal: null, pengertianHalalHaram: null, praktikSjph: null, anggota: [] },
      bahan: { daftarBahan: [], catatanPembelian: [], pemeriksaan: [] },
      produk: [],
      proses: { pernyataanBebasBabi: null, layout: [], penyimpanan: [], alurProses: [], hasilProduksi: [], distribusi: [] },
      pemetaan: [],
      pemantauan: { dokumenLain: [], tandaTangan: [] },
      riwayat: [{ status: "draf", waktu }],
      audit: [],
    };
    catat(baru, { pelaku: "pengguna", aksi: `Membuat draf pengajuan ${jalur === "self-declare" ? "Self Declare" : "Reguler"}` });
    pengajuan.push(baru);
    return jeda(baru);
  },

  async ubahBagian(id, perubahan) {
    const p = cari(id);
    if (p.status !== "draf" && p.status !== "dikembalikan") {
      throw new ApiError(409, "Pengajuan sudah dikirim sehingga tidak bisa diubah. Tunggu hasil verifikasi.");
    }
    (p as unknown as Record<BagianPengajuan, unknown>)[perubahan.bagian] = structuredClone(perubahan.isi);
    catat(p, { pelaku: "pengguna", aksi: `Mengubah ${namaBagian[perubahan.bagian]}`, bagian: perubahan.bagian });
    return jeda(p);
  },

  async kirimPengajuan(id) {
    const p = cari(id);
    if (p.status !== "draf" && p.status !== "dikembalikan") {
      throw new ApiError(409, "Pengajuan ini sudah dikirim.");
    }
    const kurang = (Object.entries(hitungKelengkapan(p)) as Array<[TabPengajuan, { done: number; total: number }]>)
      .filter(([, skor]) => !lengkap(skor))
      .map(([tab]) => labelTab[tab]);
    if (kurang.length > 0) {
      throw new ApiError(422, `Pengajuan belum lengkap di tab ${kurang.join(", ")}. Lengkapi isian lalu kirim lagi.`);
    }
    const waktu = sekarang();
    p.nomorDaftar ??= `SH2026-1-${String(nomorBerikutnya++).padStart(6, "0")}`;
    p.status = "terkirim";
    p.riwayat.push({ status: "terkirim", waktu, catatan: "Dikirim oleh pelaku usaha" });
    catat(p, { pelaku: "pengguna", aksi: "Mengirim pengajuan" });
    return jeda(p);
  },

  urlDokumen() {
    // Dokumen PDF dibuat backend; di mode mock belum tersedia
    return null;
  },

  async resetDemo() {
    muatSeed();
    return jeda(undefined);
  },
};
