import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router";
import { IconAlertTriangle, IconEye, IconEyeOff, IconInfoCircle } from "@tabler/icons-react";
import { MockBanner } from "../components/kawal/MockBanner.tsx";
import { Button, Field, IconButton, Input, hintId, useToast } from "../components/ui/index.ts";
import { AKUN_DEMO, ambilSesi, masuk } from "../lib/sesi.ts";

const langkah = [
  "Lengkapi data pelaku usaha dan ajukan permohonan",
  "Pendamping PPH memverifikasi dan memvalidasi data",
  "BPJPH dan Komite Fatwa memproses, lalu sertifikat terbit",
];

export default function Login() {
  const navigate = useNavigate();
  const lokasi = useLocation();
  const toast = useToast();
  const [pengguna, setPengguna] = useState("");
  const [password, setPassword] = useState("");
  const [lihat, setLihat] = useState(false);
  const [dicoba, setDicoba] = useState(false);
  const [gagal, setGagal] = useState(false);
  const tujuan = (lokasi.state as { dari?: string } | null)?.dari ?? "/";

  if (ambilSesi()) return <Navigate to={tujuan} replace />;

  const galatPengguna = dicoba && !pengguna.trim() ? "Username atau email belum diisi." : undefined;
  const galatPassword = dicoba && !password ? "Password belum diisi." : undefined;

  const kirim = (e: FormEvent) => {
    e.preventDefault();
    setDicoba(true);
    setGagal(false);
    if (!pengguna.trim() || !password) return;
    if (masuk(pengguna, password)) navigate(tujuan, { replace: true });
    else setGagal(true);
  };

  const belumTersedia = (fitur: string) =>
    toast({ tone: "info", title: `${fitur} belum tersedia`, description: "Fitur ini tidak termasuk dalam versi demo." });

  return (
    <div className="flex min-h-dvh flex-col bg-surface">
      <MockBanner />
      <div className="grid flex-1 lg:grid-cols-2">
        <main className="flex items-center justify-center px-4 py-10 md:px-8">
          <div className="w-full max-w-sm">
            <p className="text-h3 font-extrabold tracking-wide text-brand">SIHALAL</p>
            <h1 className="mt-6 text-h2">Masuk ke SIHALAL</h1>
            <p className="mt-1 text-body-sm text-ink-muted">Gunakan akun pelaku usaha Anda.</p>

            <form noValidate onSubmit={kirim} className="mt-6 flex flex-col gap-4">
              {gagal && (
                <p role="alert" className="flex gap-2 rounded-md bg-status-risk-bg p-3 text-body-sm text-status-risk">
                  <IconAlertTriangle size={20} stroke={1.75} className="shrink-0" aria-hidden="true" />
                  Username atau password salah. Periksa lalu coba lagi.
                </p>
              )}
              <Field label="Username atau email" htmlFor="pengguna" required error={galatPengguna}>
                <Input
                  id="pengguna"
                  autoComplete="username"
                  value={pengguna}
                  invalid={Boolean(galatPengguna) || gagal}
                  aria-describedby={galatPengguna ? hintId("pengguna") : undefined}
                  onChange={(e) => setPengguna(e.target.value)}
                />
              </Field>
              <Field label="Password" htmlFor="password" required error={galatPassword}>
                <div className="relative">
                  <Input
                    id="password"
                    type={lihat ? "text" : "password"}
                    autoComplete="current-password"
                    className="pr-12"
                    value={password}
                    invalid={Boolean(galatPassword) || gagal}
                    aria-describedby={galatPassword ? hintId("password") : undefined}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  <IconButton
                    label={lihat ? "Sembunyikan password" : "Tampilkan password"}
                    icon={lihat ? <IconEyeOff size={20} stroke={1.75} /> : <IconEye size={20} stroke={1.75} />}
                    className="absolute right-1 top-1"
                    onClick={() => setLihat((x) => !x)}
                  />
                </div>
              </Field>
              <button
                type="button"
                className="self-end text-label text-brand hover:underline"
                onClick={() => belumTersedia("Atur ulang password")}
              >
                Lupa password?
              </button>
              <Button type="submit" className="w-full">
                Masuk
              </Button>
            </form>

            <div className="mt-6 flex gap-3 rounded-md bg-brand-tint p-4 text-body-sm text-ink">
              <IconInfoCircle size={20} stroke={1.75} className="shrink-0 text-brand" aria-hidden="true" />
              <div className="min-w-0">
                <p>
                  Akun demo: <span className="font-mono">{AKUN_DEMO.username}</span> dengan password{" "}
                  <span className="font-mono">{AKUN_DEMO.password}</span>
                </p>
                <Button
                  size="sm"
                  variant="ghost"
                  className="-ml-3 mt-1"
                  onClick={() => {
                    setPengguna(AKUN_DEMO.username);
                    setPassword(AKUN_DEMO.password);
                    setGagal(false);
                  }}
                >
                  Isi akun demo
                </Button>
              </div>
            </div>

            <p className="mt-6 text-center text-body-sm text-ink-muted">
              Belum memiliki akun?{" "}
              <button type="button" className="text-label text-brand hover:underline" onClick={() => belumTersedia("Pendaftaran akun")}>
                Daftar
              </button>
            </p>
          </div>
        </main>

        <aside className="hidden flex-col justify-center gap-6 bg-brand-deep p-12 text-on-deep lg:flex">
          <h2 className="max-w-md text-h1">Sertifikasi halal untuk produk Anda</h2>
          <ol className="flex max-w-md flex-col gap-4">
            {langkah.map((teks, i) => (
              <li key={teks} className="flex gap-3 text-body">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-pill bg-white/15 text-label">{i + 1}</span>
                <span className="pt-1">{teks}</span>
              </li>
            ))}
          </ol>
          <p className="max-w-md text-body-sm text-on-deep/75">
            KawalHalal membantu menyiapkan berkas dari percakapan WhatsApp, lalu Anda meninjau dan mengirimnya sendiri.
          </p>
        </aside>
      </div>
    </div>
  );
}
