import type { ReactNode } from "react";
import { Popover } from "radix-ui";
import { IconPaperclip, IconSparkles } from "@tabler/icons-react";
import type { Berkas, Sumber } from "../../api/types.ts";
import { tingkatKeyakinan } from "../../lib/asal.ts";
import { cn } from "../../lib/cn.ts";
import { formatWaktu } from "../../lib/format.ts";

export interface ProvenanceMarkProps {
  sumber?: Sumber;
  /** Foto atau berkas asal yang dibaca agen. */
  bukti?: Berkas;
  /** Hanya ikon, untuk baris tabel yang padat. */
  compact?: boolean;
  className?: string;
}

/**
 * Penanda "Diisi KawalHalal". Klik untuk melihat asal data: pesan WhatsApp, waktu, keyakinan, dan bukti.
 * Tidak tampil bila isian dibuat atau sudah diubah pengguna, karena data itu menjadi milik pengguna.
 */
export function ProvenanceMark({ sumber, bukti, compact = false, className }: ProvenanceMarkProps) {
  if (sumber?.oleh !== "kawalhalal") return null;
  const tingkat = tingkatKeyakinan(sumber.keyakinan);
  const rendah = tingkat === "rendah";

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label={`Diisi KawalHalal${rendah ? ", keyakinan rendah" : ""}. Lihat asal data`}
          className={cn(
            "inline-flex shrink-0 items-center gap-1 rounded-pill align-middle text-caption transition-colors",
            compact ? "size-6 justify-center" : "px-2 py-0.5",
            rendah ? "bg-status-warn-bg text-status-warn hover:bg-status-warn/15" : "bg-brand-tint text-brand hover:bg-brand/15",
            className,
          )}
        >
          <IconSparkles size={14} stroke={1.75} aria-hidden="true" />
          {!compact && "KawalHalal"}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="bottom"
          align="start"
          sideOffset={6}
          collisionPadding={16}
          className="z-50 w-72 max-w-[calc(100vw-32px)] rounded-lg border border-line bg-surface-raised p-4 text-left"
        >
          <p className="flex items-center gap-1 text-label text-brand">
            <IconSparkles size={16} stroke={1.75} aria-hidden="true" />
            Diisi KawalHalal
          </p>
          {sumber.catatan && <p className="mt-1 text-body-sm text-ink">{sumber.catatan}</p>}
          <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-caption">
            {sumber.ref && (
              <>
                <dt className="text-ink-muted">Sumber</dt>
                <dd className="text-ink">
                  Pesan WhatsApp <span className="font-mono">{sumber.ref}</span>
                </dd>
              </>
            )}
            <dt className="text-ink-muted">Waktu</dt>
            <dd className="text-ink">{formatWaktu(sumber.waktu)}</dd>
            {sumber.keyakinan !== undefined && (
              <>
                <dt className="text-ink-muted">Keyakinan</dt>
                <dd className={rendah ? "text-status-warn" : "text-ink"}>
                  {Math.round(sumber.keyakinan * 100)}% ({tingkat})
                </dd>
              </>
            )}
            {bukti && (
              <>
                <dt className="text-ink-muted">Bukti</dt>
                <dd className="flex min-w-0 items-center gap-1 text-ink">
                  <IconPaperclip size={14} stroke={1.75} className="shrink-0" aria-hidden="true" />
                  <span className="truncate">{bukti.nama}</span>
                </dd>
              </>
            )}
          </dl>
          <p className={cn("mt-3 text-caption", rendah ? "text-status-warn" : "text-ink-muted")}>
            {rendah
              ? "Keyakinan rendah. Periksa isian ini dan ubah bila tidak sesuai."
              : "Periksa isian ini dan ubah bila tidak sesuai. Setelah diubah, penanda ini hilang."}
          </p>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

/** Isi sel atau nilai dengan penanda KawalHalal ringkas di sampingnya. */
export function DenganTanda({ sumber, bukti, children }: { sumber?: Sumber; bukti?: Berkas; children: ReactNode }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      <span>{children}</span>
      <ProvenanceMark sumber={sumber} bukti={bukti} compact />
    </span>
  );
}
