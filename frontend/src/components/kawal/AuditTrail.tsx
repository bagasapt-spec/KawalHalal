import type { AuditEntri } from "../../api/types.ts";
import { cn } from "../../lib/cn.ts";
import { formatWaktu, labelPelaku, terbaruDulu } from "../../lib/format.ts";

export interface AuditTrailProps {
  entri: AuditEntri[];
  /** Tampilkan sejumlah entri terbaru saja. */
  batas?: number;
}

/** Riwayat siapa mengubah apa. Entri dari agen ditandai titik warna merek. */
export function AuditTrail({ entri, batas }: AuditTrailProps) {
  const urut = [...entri].sort(terbaruDulu((e) => e.waktu)).slice(0, batas);
  if (urut.length === 0) return <p className="text-body-sm text-ink-muted">Belum ada aktivitas.</p>;
  return (
    <ol className="flex flex-col gap-4">
      {urut.map((e) => (
        <li key={e.id} className="flex gap-3">
          <span
            aria-hidden="true"
            className={cn("mt-1.5 size-2 shrink-0 rounded-pill", e.pelaku === "kawalhalal" ? "bg-brand" : "bg-line-strong")}
          />
          <div className="min-w-0">
            <p className="text-body-sm text-ink">{e.aksi}</p>
            <p className="text-caption text-ink-muted">
              {labelPelaku[e.pelaku]} · {formatWaktu(e.waktu)}
              {e.ref && <span className="font-mono"> · {e.ref}</span>}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
