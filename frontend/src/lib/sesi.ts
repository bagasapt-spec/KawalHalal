/*
 * Sesi masuk tiruan untuk demo. Tidak ada autentikasi sungguhan: akun demo dicocokkan di browser
 * dan penandanya disimpan di localStorage supaya tidak perlu masuk ulang setiap muat ulang.
 */

const KUNCI = "kawalhalal-sesi";

/** Akun demo pelaku usaha Bakso Pak Sam (data contoh, bukan kredensial nyata). */
export const AKUN_DEMO = {
  username: "bakso.paksam",
  email: "samsul.bakso@example.com",
  password: "demo1234",
};

// Cadangan bila localStorage tidak bisa dipakai (mode privat, diblokir)
let cadangan: string | null = null;

export function ambilSesi(): string | null {
  try {
    return localStorage.getItem(KUNCI) ?? cadangan;
  } catch {
    return cadangan;
  }
}

/** Cocokkan username atau email dengan akun demo. Mengembalikan true bila berhasil masuk. */
export function masuk(pengguna: string, password: string): boolean {
  const id = pengguna.trim().toLowerCase();
  if ((id !== AKUN_DEMO.username && id !== AKUN_DEMO.email) || password !== AKUN_DEMO.password) return false;
  cadangan = AKUN_DEMO.username;
  try {
    localStorage.setItem(KUNCI, AKUN_DEMO.username);
  } catch {
    // tetap masuk lewat cadangan memori
  }
  return true;
}

/**
 * Akun yang didaftarkan lewat agen KawalHalal disimpan di backend. Dicek ke server setelah akun demo gagal.
 * Mengembalikan false bila server tidak bisa dihubungi (mis. mode mock), jadi login demo tetap jalan.
 */
export async function masukDariServer(pengguna: string, password: string): Promise<boolean> {
  try {
    const res = await fetch("/api/sihalal/akun/masuk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pengguna: pengguna.trim(), password }),
    });
    if (!res.ok) return false;
    const { berhasil } = (await res.json()) as { berhasil: boolean };
    if (!berhasil) return false;
    cadangan = pengguna.trim().toLowerCase();
    try {
      localStorage.setItem(KUNCI, cadangan);
    } catch {
      // tetap masuk lewat cadangan memori
    }
    return true;
  } catch {
    return false;
  }
}

export function keluar() {
  cadangan = null;
  try {
    localStorage.removeItem(KUNCI);
  } catch {
    // tidak ada yang perlu dihapus
  }
}
