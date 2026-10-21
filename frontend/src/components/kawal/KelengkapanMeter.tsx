import { cn } from "../../lib/cn.ts";
import { lengkap } from "../../lib/kelengkapan.ts";
import type { Skor } from "../../lib/kelengkapan.ts";

export interface KelengkapanMeterProps {
  skor: Skor;
  /** Nama untuk pembaca layar, misalnya "Kelengkapan tab Bahan". */
  label?: string;
  className?: string;
}

/** Bilah kemajuan isian wajib. Angka selalu tampil, tidak hanya warna. */
export function KelengkapanMeter({ skor, label = "Kelengkapan", className }: KelengkapanMeterProps) {
  const persen = skor.total > 0 ? Math.round((skor.done / skor.total) * 100) : 0;
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={skor.total}
        aria-valuenow={skor.done}
        aria-valuetext={`${skor.done} dari ${skor.total} terisi`}
        className="h-2 min-w-12 flex-1 overflow-hidden rounded-pill bg-line"
      >
        <div
          className={cn("h-full rounded-pill transition-[width]", lengkap(skor) ? "bg-status-ok" : "bg-brand")}
          style={{ width: `${persen}%` }}
        />
      </div>
      <span className="shrink-0 text-caption tabular-nums text-ink-muted">
        {skor.done}/{skor.total}
      </span>
    </div>
  );
}
