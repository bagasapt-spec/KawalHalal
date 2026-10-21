import { IconPaperclip } from "@tabler/icons-react";
import type { Berkas } from "../../api/types.ts";

/** Nama berkas dengan ikon klip, atau "-" bila kosong. */
export function BerkasLabel({ berkas }: { berkas?: Berkas }) {
  if (!berkas) return <span className="text-ink-muted">-</span>;
  return (
    <span className="inline-flex max-w-full items-center gap-1 text-ink">
      <IconPaperclip size={16} stroke={1.75} className="shrink-0 text-ink-muted" aria-hidden="true" />
      <span className="truncate">{berkas.nama}</span>
    </span>
  );
}
