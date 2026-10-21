import type { ComponentType } from "react";
import { Link } from "react-router";
import {
  IconAlertTriangle,
  IconHourglass,
  IconPencil,
  IconRosetteDiscountCheck,
} from "@tabler/icons-react";
import type { IconProps } from "@tabler/icons-react";
import { useDaftarPengajuan, usePelakuUsaha } from "../api/index.ts";
import type { PengajuanRingkas, StatusPengajuan } from "../api/index.ts";
import { KelengkapanMeter } from "../components/kawal/KelengkapanMeter.tsx";
import { PageHeader } from "../components/layout/PageHeader.tsx";
import { ButtonLink, Card, DataTable, StatusBadge } from "../components/ui/index.ts";
import type { Column } from "../components/ui/index.ts";
import { formatTanggal, formatWaktu, labelJalur, labelLayanan, terbaruDulu } from "../lib/format.ts";
import { statusPengajuan } from "../lib/status.ts";

const dalamProses: StatusPengajuan[] = ["terkirim", "verifikasi-pendamping", "verifikasi-bpjph", "sttd-terbit", "sidang-fatwa"];

interface Ringkasan {
  label: string;
  keterangan: string;
  icon: ComponentType<IconProps>;
  cocok: (p: PengajuanRingkas) => boolean;
}

const ringkasan: Ringkasan[] = [
  { label: "Draf", keterangan: "Belum dikirim", icon: IconPencil, cocok: (p) => p.status === "draf" },
  { label: "Dalam proses", keterangan: "Sedang diverifikasi", icon: IconHourglass, cocok: (p) => dalamProses.includes(p.status) },
  { label: "Perlu perbaikan", keterangan: "Dikembalikan verifikator", icon: IconAlertTriangle, cocok: (p) => p.status === "dikembalikan" },
  { label: "Sertifikat terbit", keterangan: "Siap diunduh", icon: IconRosetteDiscountCheck, cocok: (p) => p.status === "sh-terbit" },
];

const kolomTerbaru: Column<PengajuanRingkas>[] = [
  {
    key: "nomor",
    header: "Nomor Daftar",
    primary: true,
    cell: (r) => (
      <Link to={`/pengajuan/${r.id}`} className="text-brand hover:underline">
        {r.nomorDaftar ? <span className="font-mono text-mono">{r.nomorDaftar}</span> : "Draf tanpa nomor"}
      </Link>
    ),
  },
  { key: "jalur", header: "Jalur", cell: (r) => `${labelJalur[r.jalur]} · ${labelLayanan[r.jenisLayanan]}` },
  { key: "produk", header: "Jenis Produk", cell: (r) => r.jenisProduk || "-" },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge tone={statusPengajuan[r.status].tone}>{statusPengajuan[r.status].label}</StatusBadge>,
  },
  { key: "diperbarui", header: "Diperbarui", cell: (r) => formatWaktu(r.diperbarui) },
];

export default function Dashboard() {
  const daftar = useDaftarPengajuan({ live: true });
  const pu = usePelakuUsaha();
  const semua = daftar.data ?? [];
  const draf = semua.filter((p) => p.status === "draf" || p.status === "dikembalikan");
  const terbaru = [...semua].sort(terbaruDulu((p) => p.diperbarui)).slice(0, 5);

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={pu.data ? `Selamat datang, ${pu.data.penanggungJawab.nama}.` : "Ringkasan pengajuan sertifikasi halal Anda."}
      />

      <ul className="grid grid-cols-2 gap-4 lg:grid-cols-4" aria-label="Ringkasan status pengajuan">
        {ringkasan.map(({ label, keterangan, icon: Icon, cocok }) => (
          <li key={label}>
            <Link
              to="/pengajuan"
              className="flex h-full flex-col gap-3 rounded-lg border border-line bg-surface-raised p-4 transition-colors hover:border-brand"
            >
              <span className="flex size-10 items-center justify-center rounded-md bg-brand-tint text-brand" aria-hidden="true">
                <Icon size={24} stroke={1.75} />
              </span>
              <span className="text-h1 tabular-nums">{daftar.isPending ? "–" : semua.filter(cocok).length}</span>
              <span>
                <span className="block text-label text-ink">{label}</span>
                <span className="block text-caption text-ink-muted">{keterangan}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-6 lg:col-span-2">
          <Card title="Lanjutkan pengajuan" description="Lengkapi isian yang kurang lalu kirim pengajuan.">
            {daftar.isPending ? (
              <div className="h-16 animate-pulse rounded-sm bg-surface" />
            ) : draf.length === 0 ? (
              <p className="text-body-sm text-ink-muted">Tidak ada draf. Semua pengajuan sudah dikirim.</p>
            ) : (
              <ul className="divide-y divide-line">
                {draf.map((p) => (
                  <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0 flex-1 basis-48">
                      <p className="text-body-sm font-semibold text-ink">
                        {labelJalur[p.jalur]} · {labelLayanan[p.jenisLayanan]}
                        {p.jenisProduk && ` · ${p.jenisProduk}`}
                      </p>
                      <p className="text-caption text-ink-muted">
                        Dibuat {formatTanggal(p.dibuat)}
                        {p.status === "dikembalikan" && " · dikembalikan verifikator"}
                      </p>
                    </div>
                    <KelengkapanMeter skor={p.kelengkapan} label={`Kelengkapan pengajuan ${p.id}`} className="w-40" />
                    <ButtonLink to={`/pengajuan/${p.id}`} variant="secondary" size="sm">
                      Lanjutkan
                    </ButtonLink>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card
            title="Pengajuan terbaru"
            actions={
              <ButtonLink to="/pengajuan" variant="ghost" size="sm">
                Lihat semua
              </ButtonLink>
            }
          >
            <DataTable
              caption="Pengajuan terbaru"
              columns={kolomTerbaru}
              rows={terbaru}
              getRowId={(r) => r.id}
              loading={daftar.isPending}
              error={daftar.error?.message}
              onRetry={() => daftar.refetch()}
              emptyMessage="Belum ada pengajuan. Ajukan layanan dari menu Pengajuan Self Declare."
            />
          </Card>
        </div>

        <Card
          title="Profil usaha"
          className="self-start"
          actions={
            <ButtonLink to="/pelaku-usaha" variant="ghost" size="sm">
              Lihat profil
            </ButtonLink>
          }
        >
          {pu.isPending ? (
            <div className="h-32 animate-pulse rounded-sm bg-surface" />
          ) : pu.isError ? (
            <p role="alert" className="text-body-sm text-status-risk">
              {pu.error.message}
            </p>
          ) : (
            <dl className="flex flex-col gap-3">
              {[
                ["Nama usaha", pu.data.namaUsaha],
                ["NIB", <span className="font-mono text-mono">{pu.data.nib}</span>],
                ["Skala usaha", pu.data.skala[0].toUpperCase() + pu.data.skala.slice(1)],
                ["Penanggung jawab", pu.data.penanggungJawab.nama],
                ["Alamat", `${pu.data.alamat}, ${pu.data.kabKota}`],
              ].map(([dt, dd]) => (
                <div key={String(dt)}>
                  <dt className="text-caption text-ink-muted">{dt}</dt>
                  <dd className="text-body-sm text-ink">{dd}</dd>
                </div>
              ))}
            </dl>
          )}
        </Card>
      </div>
    </>
  );
}
