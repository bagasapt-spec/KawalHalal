import { useState } from "react";
import { Link } from "react-router";
import { IconMapPin } from "@tabler/icons-react";
import { useDaftarPengajuan, usePengajuan } from "../../api/index.ts";
import type { PengajuanRingkas } from "../../api/index.ts";
import { PageHeader } from "../../components/layout/PageHeader.tsx";
import { ButtonLink, Card, DataTable, IconButton, Modal, SegmentedToggle, StatusBadge } from "../../components/ui/index.ts";
import type { Column } from "../../components/ui/index.ts";
import { formatWaktu, labelJalur, labelLayanan } from "../../lib/format.ts";
import { statusPengajuan } from "../../lib/status.ts";
import { StatusTimeline } from "./StatusTimeline.tsx";

type Filter = "semua" | "dikirim" | "draf";

function ModalTracking({ ringkas, onTutup }: { ringkas: PengajuanRingkas; onTutup: () => void }) {
  const q = usePengajuan(ringkas.id, { live: true });
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title="Tracking pengajuan"
      description={`${ringkas.nomorDaftar ?? "Draf tanpa nomor"} · ${labelJalur[ringkas.jalur]} · ${labelLayanan[ringkas.jenisLayanan]}`}
      size="sm"
      footer={
        <ButtonLink to={`/pengajuan/${ringkas.id}`} variant="secondary" onClick={onTutup}>
          Lihat detail pengajuan
        </ButtonLink>
      }
    >
      {q.isPending ? (
        <div className="h-64 animate-pulse rounded-md bg-line" aria-busy="true" aria-label="Memuat tracking" />
      ) : q.isError ? (
        <p role="alert" className="text-body-sm text-status-risk">
          {q.error.message}
        </p>
      ) : (
        <div className="flex flex-col gap-6">
          <StatusTimeline status={q.data.status} riwayat={q.data.riwayat} />
          {q.data.riwayat.some((r) => r.catatan) && (
            <div>
              <p className="text-label text-ink">Catatan</p>
              <ul className="mt-2 flex flex-col gap-2">
                {[...q.data.riwayat].reverse().filter((r) => r.catatan).map((r, i) => (
                  <li key={i} className="text-body-sm text-ink">
                    {r.catatan}
                    <span className="block text-caption text-ink-muted">
                      {statusPengajuan[r.status].label} · {formatWaktu(r.waktu)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

export default function StatusPermohonan() {
  const daftar = useDaftarPengajuan({ live: true });
  const [filter, setFilter] = useState<Filter>("dikirim");
  const [tracking, setTracking] = useState<PengajuanRingkas | null>(null);

  const baris = (daftar.data ?? []).filter((p) =>
    filter === "semua" ? true : filter === "draf" ? p.status === "draf" : p.status !== "draf",
  );

  const kolom: Column<PengajuanRingkas>[] = [
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
    { key: "diperbarui", header: "Terakhir Diperbarui", cell: (r) => formatWaktu(r.diperbarui) },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (r) => (
        <IconButton
          label={`Cek tracking ${r.nomorDaftar ?? "draf"}`}
          tone="brand"
          icon={<IconMapPin size={20} stroke={1.75} />}
          onClick={() => setTracking(r)}
        />
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Status Permohonan" description="Pantau tahapan setiap pengajuan sertifikasi halal Anda." />
      <Card>
        <SegmentedToggle
          label="Saring pengajuan"
          className="mb-4"
          value={filter}
          onValueChange={setFilter}
          options={[
            { value: "dikirim", label: "Sudah dikirim" },
            { value: "draf", label: "Draf" },
            { value: "semua", label: "Semua" },
          ]}
        />
        <DataTable
          caption="Status permohonan"
          columns={kolom}
          rows={baris}
          getRowId={(r) => r.id}
          numbered
          loading={daftar.isPending}
          error={daftar.error?.message}
          onRetry={() => daftar.refetch()}
          emptyMessage={
            filter === "dikirim"
              ? "Belum ada pengajuan yang dikirim. Lengkapi draf lalu kirim dari halaman detail pengajuan."
              : "Tidak ada pengajuan."
          }
        />
      </Card>
      {tracking && <ModalTracking ringkas={tracking} onTutup={() => setTracking(null)} />}
    </>
  );
}
