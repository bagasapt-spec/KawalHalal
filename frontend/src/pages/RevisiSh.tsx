import { useState } from "react";
import type { FormEvent } from "react";
import { IconSearch } from "@tabler/icons-react";
import { useDaftarPengajuan } from "../api/index.ts";
import type { PengajuanRingkas } from "../api/index.ts";
import { PageHeader } from "../components/layout/PageHeader.tsx";
import { Button, ButtonLink, Card, Field, Input, StatusBadge, hintId, useToast } from "../components/ui/index.ts";
import { labelJalur, labelLayanan } from "../lib/format.ts";
import { statusPengajuan } from "../lib/status.ts";

type Hasil = { jenis: "ketemu"; p: PengajuanRingkas } | { jenis: "tidak-ada"; nomor: string };

const alasanRevisi = [
  "Nama atau alamat usaha berubah.",
  "Ada kesalahan penulisan pada sertifikat.",
  "Nama produk berubah tanpa mengubah bahan dan proses produksi.",
];

export default function RevisiSh() {
  const toast = useToast();
  const daftar = useDaftarPengajuan();
  const [nomor, setNomor] = useState("");
  const [galat, setGalat] = useState<string>();
  const [hasil, setHasil] = useState<Hasil | null>(null);

  const cari = (e: FormEvent) => {
    e.preventDefault();
    const kata = nomor.trim().toUpperCase();
    setHasil(null);
    if (!kata) {
      setGalat("Nomor belum diisi. Tulis nomor STTD atau nomor sertifikat halal.");
      return;
    }
    setGalat(undefined);
    const p = (daftar.data ?? []).find((x) => x.nomorDaftar?.toUpperCase() === kata);
    setHasil(p ? { jenis: "ketemu", p } : { jenis: "tidak-ada", nomor: kata });
  };

  return (
    <>
      <PageHeader title="Revisi Sertifikat" description="Ajukan perubahan data pada sertifikat halal yang sudah terbit." />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-6 lg:col-span-2">
          <Card title="Cari data sertifikat">
            <form noValidate onSubmit={cari} className="flex flex-col gap-3 sm:flex-row sm:items-start">
              <Field
                label="Nomor STTD atau nomor sertifikat halal"
                htmlFor="nomor-sh"
                required
                error={galat}
                className="min-w-0 flex-1"
              >
                <Input
                  id="nomor-sh"
                  className="font-mono"
                  placeholder="Contoh: SH2026-1-000142"
                  value={nomor}
                  invalid={Boolean(galat)}
                  aria-describedby={galat ? hintId("nomor-sh") : undefined}
                  onChange={(e) => setNomor(e.target.value)}
                />
              </Field>
              <Button type="submit" icon={<IconSearch size={16} stroke={1.75} />} loading={daftar.isPending} className="sm:mt-6">
                Cari data
              </Button>
            </form>
          </Card>

          {hasil?.jenis === "tidak-ada" && (
            <Card>
              <p role="status" className="text-body-sm text-ink">
                Nomor <span className="font-mono">{hasil.nomor}</span> tidak ditemukan di akun Anda. Periksa penulisan nomor lalu
                cari lagi.
              </p>
            </Card>
          )}

          {hasil?.jenis === "ketemu" && (
            <Card
              title={<span className="font-mono">{hasil.p.nomorDaftar}</span>}
              description={`${labelJalur[hasil.p.jalur]} · ${labelLayanan[hasil.p.jenisLayanan]} · ${hasil.p.jenisProduk || "-"}`}
              actions={
                <StatusBadge tone={statusPengajuan[hasil.p.status].tone}>{statusPengajuan[hasil.p.status].label}</StatusBadge>
              }
            >
              {hasil.p.status === "sh-terbit" ? (
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    onClick={() =>
                      toast({ tone: "info", title: "Pengajuan revisi belum tersedia", description: "Fitur ini tidak termasuk dalam versi demo." })
                    }
                  >
                    Ajukan revisi
                  </Button>
                </div>
              ) : (
                <div className="flex flex-col gap-3">
                  <p role="status" className="rounded-md bg-status-warn-bg p-3 text-body-sm text-status-warn">
                    Pengajuan ini masih berstatus {statusPengajuan[hasil.p.status].label}. Revisi hanya bisa diajukan untuk
                    sertifikat yang sudah terbit.
                  </p>
                  <ButtonLink to={`/pengajuan/${hasil.p.id}`} variant="secondary" className="self-start">
                    Lihat detail pengajuan
                  </ButtonLink>
                </div>
              )}
            </Card>
          )}
        </div>

        <Card title="Kapan perlu revisi?" className="self-start">
          <ul className="flex list-disc flex-col gap-2 pl-5 text-body-sm text-ink">
            {alasanRevisi.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
          <p className="mt-3 text-caption text-ink-muted">
            Bila bahan atau proses produksi berubah, ajukan pengembangan produk lewat menu Pengajuan, bukan revisi.
          </p>
        </Card>
      </div>
    </>
  );
}
