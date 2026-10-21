import { IconInfoCircle } from "@tabler/icons-react";
import { PageHeader } from "../components/layout/PageHeader.tsx";
import { Card, DataTable } from "../components/ui/index.ts";
import type { Column } from "../components/ui/index.ts";

interface Tagihan {
  id: string;
  nomorInvoice: string;
}

// Kolom sama dengan SIHALAL; data tagihan belum ada di kontrak API demo
const kolom: Column<Tagihan>[] = [
  { key: "invoice", header: "No. Invoice", primary: true, cell: (x) => x.nomorInvoice },
  { key: "nomor", header: "Nomor Daftar", cell: () => "-" },
  { key: "tanggal", header: "Tanggal", cell: () => "-" },
  { key: "jatuhTempo", header: "Jatuh Tempo", cell: () => "-" },
  { key: "jumlah", header: "Jumlah", cell: () => "-" },
  { key: "status", header: "Status", cell: () => "-" },
];

const caraBayar = [
  "Buka tagihan untuk melihat rincian invoice dan nomor rekening tujuan.",
  "Bayar sesuai jumlah tagihan sebelum tanggal jatuh tempo.",
  "Isi konfirmasi pembayaran: tanggal, jumlah, bank tujuan, bank pengirim, dan nama pengirim.",
  "Unggah bukti transfer dalam format PDF.",
  "Surat Tanda Terima Dokumen (STTD) terbit setelah pembayaran diverifikasi.",
];

export default function Tagihan() {
  return (
    <>
      <PageHeader title="Tagihan" description="Tagihan biaya sertifikasi halal dan konfirmasi pembayarannya." />
      <div className="flex flex-col gap-6">
        <div className="flex gap-3 rounded-lg border border-line bg-brand-tint p-4 text-body-sm text-ink">
          <IconInfoCircle size={20} stroke={1.75} className="mt-0.5 shrink-0 text-brand" aria-hidden="true" />
          <p>
            Tagihan muncul setelah biaya ditetapkan. Untuk pengajuan Self Declare lewat program fasilitasi seperti SEHATI,
            biaya ditanggung program sehingga tidak ada tagihan. Untuk jalur Reguler, biaya pemeriksaan ditetapkan oleh LPH.
          </p>
        </div>

        <Card title="Daftar tagihan">
          <DataTable
            caption="Daftar tagihan"
            columns={kolom}
            rows={[]}
            getRowId={(x) => x.id}
            numbered
            emptyMessage="Belum ada tagihan untuk pengajuan Anda."
          />
        </Card>

        <Card title="Cara membayar tagihan">
          <ol className="flex flex-col gap-3">
            {caraBayar.map((teks, i) => (
              <li key={teks} className="flex gap-3 text-body-sm text-ink">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-pill bg-brand-tint text-caption text-brand">
                  {i + 1}
                </span>
                <span className="pt-0.5">{teks}</span>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </>
  );
}
