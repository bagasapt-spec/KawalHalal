import type {
  BagianPengajuan,
  BuatPengajuan,
  IsiBagian,
  JenisDokumen,
  PelakuUsaha,
  Pengajuan,
  PengajuanRingkas,
} from "./types.ts";

/** Body PATCH /pengajuan/{id}/{bagian}, dipasangkan dengan isinya. */
export type PerubahanBagian = { [B in BagianPengajuan]: { bagian: B; isi: IsiBagian[B] } }[BagianPengajuan];

/** Galat dengan pesan siap tampil: sebut masalahnya lalu langkah berikutnya. */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Semua operasi mock SIHALAL. Diimplementasikan oleh httpApi (FastAPI) dan mockApi (fixture di browser). */
export interface SihalalApi {
  getPelakuUsaha(): Promise<PelakuUsaha>;
  ubahPelakuUsaha(isi: PelakuUsaha): Promise<PelakuUsaha>;
  daftarPengajuan(): Promise<PengajuanRingkas[]>;
  getPengajuan(id: string): Promise<Pengajuan>;
  buatPengajuan(isi: BuatPengajuan): Promise<Pengajuan>;
  ubahBagian(id: string, perubahan: PerubahanBagian): Promise<Pengajuan>;
  /** Hanya dipanggil dari klik pengguna (human gate), tidak pernah oleh agen. */
  kirimPengajuan(id: string): Promise<Pengajuan>;
  /** null bila dokumen belum bisa dibuat di mode ini. */
  urlDokumen(id: string, jenis: JenisDokumen): string | null;
  resetDemo(): Promise<void>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Server tidak bisa dihubungi. Pastikan backend berjalan lalu coba lagi.");
  }
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = ((await res.json()) as { detail?: unknown }).detail;
    } catch {
      // body bukan JSON
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : `Permintaan gagal (HTTP ${res.status}). Coba lagi.`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const json = (body: unknown) => JSON.stringify(body);

export const httpApi: SihalalApi = {
  getPelakuUsaha: () => request("/sihalal/pelaku-usaha"),
  ubahPelakuUsaha: (isi) => request("/sihalal/pelaku-usaha", { method: "PATCH", body: json(isi) }),
  daftarPengajuan: () => request("/sihalal/pengajuan"),
  getPengajuan: (id) => request(`/sihalal/pengajuan/${encodeURIComponent(id)}`),
  buatPengajuan: (isi) => request("/sihalal/pengajuan", { method: "POST", body: json(isi) }),
  ubahBagian: (id, { bagian, isi }) =>
    request(`/sihalal/pengajuan/${encodeURIComponent(id)}/${bagian}`, { method: "PATCH", body: json(isi) }),
  kirimPengajuan: (id) => request(`/sihalal/pengajuan/${encodeURIComponent(id)}/kirim`, { method: "POST" }),
  urlDokumen: (id, jenis) => `/api/sihalal/pengajuan/${encodeURIComponent(id)}/dokumen/${jenis}`,
  resetDemo: () => request("/demo/reset", { method: "POST" }),
};
