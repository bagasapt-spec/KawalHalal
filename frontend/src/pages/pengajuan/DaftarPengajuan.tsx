import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { IconChevronRight, IconPlus, IconSearch } from "@tabler/icons-react";
import { useDaftarPengajuan } from "../../api/index.ts";
import type { Jalur, PengajuanRingkas, StatusPengajuan } from "../../api/index.ts";
import { KelengkapanMeter } from "../../components/kawal/KelengkapanMeter.tsx";
import { PageHeader } from "../../components/layout/PageHeader.tsx";
import {
  Button,
  Card,
  DataTable,
  IconButton,
  Input,
  Pagination,
  Select,
  StatusBadge,
} from "../../components/ui/index.ts";
import type { Column } from "../../components/ui/index.ts";
import { formatTanggal, labelJalur, labelLayanan } from "../../lib/format.ts";
import { statusPengajuan } from "../../lib/status.ts";
import { AjukanLayananModal } from "./AjukanLayananModal.tsx";

const PER_HALAMAN = 10;

type FilterStatus = "semua" | StatusPengajuan;

const opsiStatus = [
  { value: "semua", label: "Semua status" },
  ...(Object.keys(statusPengajuan) as StatusPengajuan[]).map((s) => ({ value: s, label: statusPengajuan[s].label })),
];

export default function DaftarPengajuan({ jalur }: { jalur: Jalur }) {
  const navigate = useNavigate();
  // Live: draf yang dibuat agen dari WhatsApp langsung muncul di daftar
  const daftar = useDaftarPengajuan({ live: true });
  const [cari, setCari] = useState("");
  const [status, setStatus] = useState<FilterStatus>("semua");
  const [halaman, setHalaman] = useState(1);
  const [modalTerbuka, setModalTerbuka] = useState(false);

  const baris = useMemo(() => {
    const kata = cari.trim().toLowerCase();
    return (daftar.data ?? [])
      .filter((p) => p.jalur === jalur)
      .filter((p) => status === "semua" || p.status === status)
      .filter(
        (p) =>
          kata === "" ||
          [p.nomorDaftar ?? "", p.jenisProduk, p.id].some((teks) => teks.toLowerCase().includes(kata)),
      );
  }, [daftar.data, jalur, status, cari]);

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
    { key: "dibuat", header: "Tanggal Dibuat", cell: (r) => formatTanggal(r.dibuat) },
    { key: "layanan", header: "Layanan", cell: (r) => labelLayanan[r.jenisLayanan] },
    {
      key: "produk",
      header: "Produk",
      cell: (r) => (
        <>
          {r.jenisProduk || "-"}
          <span className="block text-caption text-ink-muted">{r.jumlahProduk} produk</span>
        </>
      ),
    },
    {
      key: "kelengkapan",
      header: "Kelengkapan",
      className: "w-40",
      cell: (r) => <KelengkapanMeter skor={r.kelengkapan} label={`Kelengkapan ${r.nomorDaftar ?? "draf"}`} />,
    },
    {
      key: "status",
      header: "Status",
      cell: (r) => <StatusBadge tone={statusPengajuan[r.status].tone}>{statusPengajuan[r.status].label}</StatusBadge>,
    },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (r) => (
        <IconButton
          label={`Lihat detail ${r.nomorDaftar ?? "draf"}`}
          tone="brand"
          icon={<IconChevronRight size={20} stroke={1.75} />}
          onClick={() => navigate(`/pengajuan/${r.id}`)}
        />
      ),
    },
  ];

  const tombolAjukan = (variant: "primary" | "secondary") => (
    <Button variant={variant} icon={<IconPlus size={16} stroke={1.75} />} onClick={() => setModalTerbuka(true)}>
      Ajukan Layanan
    </Button>
  );

  return (
    <>
      <PageHeader
        title={`Pengajuan ${labelJalur[jalur]}`}
        description="Daftar permohonan sertifikasi halal Anda. Draf dari WhatsApp KawalHalal muncul di sini secara otomatis."
        actions={tombolAjukan("primary")}
      />

      <Card>
        <div className="mb-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
          <div className="relative">
            <label htmlFor="cari-pengajuan" className="sr-only">
              Cari pengajuan
            </label>
            <IconSearch
              size={16}
              stroke={1.75}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
            />
            <Input
              id="cari-pengajuan"
              type="search"
              className="pl-9"
              placeholder="Cari nomor daftar atau jenis produk"
              value={cari}
              onChange={(e) => {
                setCari(e.target.value);
                setHalaman(1);
              }}
            />
          </div>
          <div>
            <label htmlFor="filter-status" className="sr-only">
              Filter status
            </label>
            <Select
              id="filter-status"
              options={opsiStatus}
              value={status}
              onValueChange={(v) => {
                setStatus(v as FilterStatus);
                setHalaman(1);
              }}
            />
          </div>
        </div>

        <DataTable
          caption={`Daftar pengajuan ${labelJalur[jalur]}`}
          columns={kolom}
          rows={baris.slice((halaman - 1) * PER_HALAMAN, halaman * PER_HALAMAN)}
          getRowId={(r) => r.id}
          numbered
          numberOffset={(halaman - 1) * PER_HALAMAN}
          loading={daftar.isPending}
          error={daftar.error?.message}
          onRetry={() => daftar.refetch()}
          emptyMessage={
            cari || status !== "semua"
              ? "Tidak ada pengajuan yang cocok. Ubah kata pencarian atau filter status."
              : "Belum ada pengajuan. Ajukan layanan untuk membuat draf, atau mulai lewat WhatsApp KawalHalal."
          }
          emptyAction={!cari && status === "semua" ? tombolAjukan("secondary") : undefined}
          footer={
            baris.length > PER_HALAMAN ? (
              <Pagination page={halaman} pageSize={PER_HALAMAN} total={baris.length} onPageChange={setHalaman} />
            ) : undefined
          }
        />
      </Card>

      <AjukanLayananModal open={modalTerbuka} onOpenChange={setModalTerbuka} jalur={jalur} />
    </>
  );
}
