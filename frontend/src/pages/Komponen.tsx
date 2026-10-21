import { useState } from "react";
import { IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
import { PageHeader } from "../components/layout/PageHeader.tsx";
import { StickyActionBar } from "../components/layout/StickyActionBar.tsx";
import {
  Button,
  Card,
  Checkbox,
  ConfirmDialog,
  DataTable,
  DateInput,
  Field,
  FileInput,
  IconButton,
  Input,
  Modal,
  Pagination,
  SegmentedToggle,
  Select,
  StatusBadge,
  TabPanel,
  Tabs,
  Textarea,
  hintId,
  useToast,
} from "../components/ui/index.ts";
import type { Column, StatusTone } from "../components/ui/index.ts";
import { apiMode, useBuatPengajuan, useDaftarPengajuan, useKirimPengajuan, useResetDemo } from "../api/index.ts";
import type { PengajuanRingkas } from "../api/index.ts";
import { statusPengajuan } from "../lib/status.ts";

// Galeri pengembang: semua primitif di satu halaman untuk cek tampilan dan responsif. Hanya ada di mode dev.

interface ContohBahan {
  id: string;
  nama: string;
  jenis: string;
  produsen: string;
  noSertifikat: string;
  bukti: { tone: StatusTone; label: string };
}

const contohBahan: ContohBahan[] = [
  {
    id: "1",
    nama: "Daging sapi giling",
    jenis: "Bahan",
    produsen: "RPH Ciroyom",
    noSertifikat: "ID32110000123450224",
    bukti: { tone: "ok", label: "Ada" },
  },
  {
    id: "2",
    nama: "Kecap manis",
    jenis: "Bahan",
    produsen: "PT Contoh Pangan",
    noSertifikat: "ID00410000054910420",
    bukti: { tone: "warn", label: "Tidak jelas" },
  },
  { id: "3", nama: "Tepung tapioka", jenis: "Bahan", produsen: "-", noSertifikat: "-", bukti: { tone: "risk", label: "Kurang" } },
  { id: "4", nama: "Plastik pouch", jenis: "Kemasan", produsen: "-", noSertifikat: "-", bukti: { tone: "neutral", label: "Tidak wajib" } },
];

type TableState = "data" | "loading" | "empty" | "error";

const kolomPengajuan: Column<PengajuanRingkas>[] = [
  { key: "id", header: "ID", cell: (r) => <span className="font-mono text-mono">{r.id}</span>, primary: true },
  { key: "nomor", header: "Nomor Daftar", cell: (r) => <span className="font-mono text-mono">{r.nomorDaftar ?? "-"}</span> },
  { key: "produk", header: "Jenis Produk", cell: (r) => r.jenisProduk || "-" },
  {
    key: "status",
    header: "Status",
    cell: (r) => <StatusBadge tone={statusPengajuan[r.status].tone}>{statusPengajuan[r.status].label}</StatusBadge>,
  },
  { key: "lengkap", header: "Kelengkapan", cell: (r) => `${r.kelengkapan.done}/${r.kelengkapan.total}` },
];

/** Uji hooks TanStack Query terhadap mock API (atau backend bila VITE_API_MODE=http). */
function KartuDataApi() {
  const toast = useToast();
  const daftar = useDaftarPengajuan();
  const buat = useBuatPengajuan();
  const kirim = useKirimPengajuan("pj-1");
  const reset = useResetDemo();
  const galat = (e: Error) => toast({ tone: "risk", title: "Gagal", description: e.message });

  return (
    <Card
      title="Data dari API"
      description={`Mode ${apiMode}. Hooks useDaftarPengajuan, useBuatPengajuan, useKirimPengajuan, useResetDemo.`}
      actions={
        <>
          <Button
            size="sm"
            variant="secondary"
            loading={buat.isPending}
            onClick={() =>
              buat.mutate(
                { jalur: "self-declare", jenisLayanan: "baru" },
                { onSuccess: (p) => toast({ title: `Draf ${p.id} dibuat` }), onError: galat },
              )
            }
          >
            Buat draf
          </Button>
          <Button
            size="sm"
            variant="secondary"
            loading={kirim.isPending}
            onClick={() => kirim.mutate(undefined, { onSuccess: (p) => toast({ tone: "info", title: `Terkirim ${p.nomorDaftar}` }), onError: galat })}
          >
            Kirim pj-1
          </Button>
          <Button size="sm" variant="ghost" loading={reset.isPending} onClick={() => reset.mutate()}>
            Reset demo
          </Button>
        </>
      }
    >
      <DataTable
        caption="Daftar pengajuan dari API"
        columns={kolomPengajuan}
        rows={daftar.data}
        getRowId={(r) => r.id}
        loading={daftar.isPending}
        error={daftar.error?.message}
        onRetry={() => daftar.refetch()}
      />
    </Card>
  );
}

export default function Komponen() {
  const toast = useToast();
  const [tab, setTab] = useState("bahan");
  const [tableState, setTableState] = useState<TableState>("data");
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [mode, setMode] = useState<"unggah" | "manual">("manual");
  const [hapus, setHapus] = useState<ContohBahan | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [namaProduk, setNamaProduk] = useState("Bakso Sapi");

  const columns: Column<ContohBahan>[] = [
    { key: "nama", header: "Nama Bahan", cell: (r) => r.nama, primary: true },
    { key: "jenis", header: "Jenis", cell: (r) => r.jenis },
    { key: "produsen", header: "Produsen", cell: (r) => r.produsen },
    { key: "sertifikat", header: "No. Sertifikat Halal", cell: (r) => <span className="font-mono text-mono">{r.noSertifikat}</span> },
    { key: "bukti", header: "Bukti", cell: (r) => <StatusBadge tone={r.bukti.tone}>{r.bukti.label}</StatusBadge> },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (r) => (
        <div className="flex justify-end gap-1">
          <IconButton label={`Ubah ${r.nama}`} tone="brand" icon={<IconPencil size={18} stroke={1.75} />} onClick={() => setModalOpen(true)} />
          <IconButton label={`Hapus ${r.nama}`} tone="danger" icon={<IconTrash size={18} stroke={1.75} />} onClick={() => setHapus(r)} />
        </div>
      ),
    },
  ];

  return (
    <>
      <PageHeader
        title="Komponen UI"
        description="Galeri primitif dan token design system. Hanya tampil di mode pengembangan."
        back={{ to: "/", label: "Dashboard" }}
        meta={<StatusBadge tone="info">Dev</StatusBadge>}
      />

      <div className="flex flex-col gap-6">
        <KartuDataApi />

        <Card title="Tipografi">
          <div className="flex flex-col gap-2">
            <p className="text-h1">h1 · Pengajuan Self Declare</p>
            <p className="text-h2">h2 · Daftar Nama Bahan</p>
            <p className="text-h3">h3 · Catatan Pembelian Bahan</p>
            <p className="text-body">body · Ayam dibeli di lapak langganan, di pasar dekat warung.</p>
            <p className="text-body-sm">body-sm · Dicocokkan dengan registri BPJPH.</p>
            <p className="text-label">label · Perlu konfirmasi</p>
            <p className="text-caption text-ink-muted">caption · Diperbarui 2 jam lalu</p>
            <p className="font-mono text-mono">mono · SH2026-1-000142</p>
          </div>
        </Card>

        <Card title="Tombol dan badge">
          <div className="flex flex-wrap gap-2">
            <Button icon={<IconPlus size={16} stroke={1.75} />}>Tambah bahan</Button>
            <Button variant="secondary">Batal</Button>
            <Button variant="ghost">Lihat bukti</Button>
            <Button variant="danger">Hapus</Button>
            <Button loading>Menyimpan</Button>
            <Button disabled>Nonaktif</Button>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusBadge tone="ok">Ada</StatusBadge>
            <StatusBadge tone="risk">Kurang</StatusBadge>
            <StatusBadge tone="warn">Tidak jelas</StatusBadge>
            <StatusBadge tone="info">Terkirim</StatusBadge>
            <StatusBadge tone="neutral">Draf</StatusBadge>
          </div>
        </Card>

        <Card title="Isian form" description="Penghitung karakter membaca isi sebenarnya.">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Nama Produk" htmlFor="nama-produk" required>
              <Input id="nama-produk" value={namaProduk} onChange={(e) => setNamaProduk(e.target.value)} maxLength={200} showCount />
            </Field>
            <Field label="Klasifikasi Produk" htmlFor="klasifikasi" required>
              <Select
                id="klasifikasi"
                options={[
                  { value: "makanan", label: "Makanan" },
                  { value: "minuman", label: "Minuman" },
                ]}
                defaultValue="makanan"
              />
            </Field>
            <Field label="Merek" htmlFor="merek" error="Merek belum diisi. Tulis nama dagang yang tertera di kemasan.">
              <Input id="merek" invalid aria-describedby={hintId("merek")} />
            </Field>
            <Field label="Tanggal Pembelian" htmlFor="tgl-beli" hint="Sesuai tanggal di nota.">
              <DateInput id="tgl-beli" aria-describedby={hintId("tgl-beli")} />
            </Field>
            <Field label="Diagram Alur Proses" htmlFor="alur" className="md:col-span-2">
              <Textarea id="alur" defaultValue={"1. Daging digiling\n2. Dicampur tapioka dan bumbu"} maxLength={1000} showCount />
            </Field>
            <Field label="Unggah Denah Ruang Produksi" htmlFor="denah" hint="Format JPG, PNG, atau PDF. Maksimal 50 MB.">
              <FileInput id="denah" accept=".jpg,.jpeg,.png,.pdf" fileName={fileName} onChange={(f) => setFileName(f?.name ?? null)} />
            </Field>
            <div className="flex flex-col gap-3 md:pt-6">
              <Checkbox id="setuju" label="Saya telah membaca seluruh pernyataan dan bersedia memenuhinya." />
              <Checkbox id="nonaktif" label="Contoh nonaktif" disabled />
            </div>
          </div>
        </Card>

        <Card title="Tabs dengan kelengkapan">
          <Tabs
            label="Bagian pengajuan"
            value={tab}
            onValueChange={setTab}
            items={[
              { value: "data", label: "Data Pengajuan", progress: { done: 6, total: 6 } },
              { value: "komitmen", label: "Komitmen", progress: { done: 3, total: 3 } },
              { value: "bahan", label: "Bahan", progress: { done: 2, total: 4 } },
              { value: "proses", label: "Proses", progress: { done: 0, total: 6 } },
              { value: "produk", label: "Produk" },
              { value: "pemantauan", label: "Pemantauan dan Evaluasi" },
              { value: "dokumen", label: "Dokumen" },
            ]}
          >
            {["data", "komitmen", "proses", "produk", "pemantauan", "dokumen"].map((v) => (
              <TabPanel key={v} value={v}>
                <p className="text-body-sm text-ink-muted">Isi tab {v}.</p>
              </TabPanel>
            ))}
            <TabPanel value="bahan">
              <Card
                title="Daftar Nama Bahan dan Kemasan"
                actions={
                  <Button size="sm" variant="secondary" icon={<IconPlus size={16} stroke={1.75} />} onClick={() => setModalOpen(true)}>
                    Tambah
                  </Button>
                }
              >
                <SegmentedToggle
                  label="State tabel"
                  className="mb-4"
                  value={tableState}
                  onValueChange={setTableState}
                  options={[
                    { value: "data", label: "Data" },
                    { value: "loading", label: "Memuat" },
                    { value: "empty", label: "Kosong" },
                    { value: "error", label: "Galat" },
                  ]}
                />
                <DataTable
                  caption="Daftar nama bahan dan kemasan"
                  columns={columns}
                  rows={tableState === "empty" ? [] : contohBahan}
                  getRowId={(r) => r.id}
                  numbered
                  loading={tableState === "loading"}
                  error={tableState === "error" ? "Data bahan gagal dimuat. Periksa koneksi lalu coba lagi." : null}
                  onRetry={() => setTableState("data")}
                  emptyMessage="Belum ada bahan. Tambahkan bahan atau kirim foto label lewat WhatsApp."
                  footer={<Pagination page={page} pageSize={10} total={23} onPageChange={setPage} />}
                />
              </Card>
            </TabPanel>
          </Tabs>
        </Card>
      </div>

      <StickyActionBar>
        <Button variant="secondary" onClick={() => toast({ title: "Perubahan disimpan", description: "Data bahan tersimpan sebagai draf." })}>
          Simpan
        </Button>
        <Button onClick={() => toast({ tone: "info", title: "Pengajuan terkirim", description: "Menunggu verifikasi Pendamping PPH." })}>
          Kirim pengajuan
        </Button>
      </StickyActionBar>

      <Modal
        open={modalOpen}
        onOpenChange={setModalOpen}
        title="Tambah Data Bahan"
        footer={
          <>
            <Button variant="secondary" onClick={() => setModalOpen(false)}>
              Batal
            </Button>
            <Button onClick={() => setModalOpen(false)}>Simpan</Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <SegmentedToggle
            label="Cara menambah bahan"
            className="self-center"
            value={mode}
            onValueChange={setMode}
            options={[
              { value: "unggah", label: "Unggah File" },
              { value: "manual", label: "Tambah Manual" },
            ]}
          />
          {mode === "manual" ? (
            <>
              <Field label="Tipe Bahan" htmlFor="tipe-bahan" required>
                <Select
                  id="tipe-bahan"
                  options={[
                    { value: "bersertifikat", label: "Bahan bersertifikat" },
                    { value: "tidak", label: "Bahan tidak bersertifikat" },
                  ]}
                />
              </Field>
              <Field label="Nama Bahan" htmlFor="nama-bahan" required>
                <Input id="nama-bahan" placeholder="Contoh: Kecap manis" />
              </Field>
            </>
          ) : (
            <Field label="Berkas Daftar Bahan" htmlFor="berkas-bahan" hint="Gunakan templat XLSX dari tombol Unduh templat.">
              <FileInput id="berkas-bahan" accept=".xlsx" onChange={() => undefined} />
            </Field>
          )}
        </div>
      </Modal>

      <ConfirmDialog
        open={hapus !== null}
        onOpenChange={(open) => !open && setHapus(null)}
        tone="danger"
        title="Hapus bahan"
        description={`${hapus?.nama ?? "Bahan"} akan dihapus dari daftar. Tindakan ini tidak bisa dibatalkan.`}
        confirmLabel="Hapus"
        onConfirm={() => {
          toast({ tone: "ok", title: `${hapus?.nama} dihapus` });
          setHapus(null);
        }}
      />
    </>
  );
}
