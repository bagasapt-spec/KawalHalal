import { IconDownload, IconFileText } from "@tabler/icons-react";
import { api } from "../../api/index.ts";
import type { JenisDokumen } from "../../api/index.ts";
import { Card } from "../../components/ui/index.ts";
import type { TabProps } from "./shared.tsx";

const dokumen: Array<{ jenis: JenisDokumen; nama: string; keterangan: string }> = [
  {
    jenis: "surat-permohonan",
    nama: "Surat Permohonan",
    keterangan: "Disusun dari data penanggung jawab dan data pengajuan.",
  },
  {
    jenis: "sjph",
    nama: "Manual Sistem Jaminan Produk Halal (SJPH)",
    keterangan: "Disusun dari komitmen, bahan, proses, dan tanda tangan.",
  },
];

export default function TabDokumen({ p }: TabProps) {
  return (
    <Card title="Unduh Dokumen Kelengkapan" description="Dokumen dibuat otomatis dari isian di tab lain. Lengkapi semua tab sebelum mengunduh.">
      <ul className="divide-y divide-line">
        {dokumen.map(({ jenis, nama, keterangan }) => {
          const url = api.urlDokumen(p.id, jenis);
          return (
            <li key={jenis} className="flex flex-wrap items-center gap-4 py-4 first:pt-0 last:pb-0">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-brand-tint text-brand" aria-hidden="true">
                <IconFileText size={24} stroke={1.75} />
              </span>
              <div className="min-w-0 flex-1 basis-48">
                <p className="text-body-sm font-semibold text-ink">{nama}</p>
                <p className="text-caption text-ink-muted">{keterangan}</p>
              </div>
              {url ? (
                <a
                  href={url}
                  download
                  className="inline-flex h-11 items-center gap-2 rounded-md bg-brand px-4 text-label text-on-brand hover:bg-brand-deep"
                >
                  <IconDownload size={16} stroke={1.75} aria-hidden="true" />
                  Unduh
                </a>
              ) : (
                <span className="text-caption text-ink-muted">Tersedia saat backend aktif</span>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
