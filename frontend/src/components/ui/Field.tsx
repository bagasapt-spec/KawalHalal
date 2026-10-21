import type { ReactNode } from "react";
import { IconAlertTriangle } from "@tabler/icons-react";
import { cn } from "../../lib/cn.ts";

/** Kelas dasar yang sama untuk semua kontrol isian. 16px di mobile supaya iOS tidak zoom. */
export const fieldBase = cn(
  "w-full rounded-sm border border-line-strong bg-surface-raised px-3 text-body text-ink md:text-body-sm",
  "placeholder:text-ink-muted/70",
  "disabled:cursor-not-allowed disabled:bg-surface disabled:text-ink-muted",
  "aria-[invalid=true]:border-status-risk",
);

/** Id elemen hint/galat, untuk aria-describedby pada kontrol. */
export function hintId(id: string) {
  return `${id}-hint`;
}

export interface FieldProps {
  label: string;
  htmlFor: string;
  required?: boolean;
  hint?: ReactNode;
  /** Pesan galat: sebut masalahnya lalu langkah berikutnya. */
  error?: string;
  /** Konten di kanan label, misalnya penanda isian KawalHalal. */
  aside?: ReactNode;
  className?: string;
  children: ReactNode;
}

export function Field({ label, htmlFor, required, hint, error, aside, className, children }: FieldProps) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <div className="flex min-h-5 items-center justify-between gap-2">
        <label htmlFor={htmlFor} className="text-label text-ink">
          {label}
          {required && (
            <span className="ml-1 text-status-risk" aria-hidden="true">
              *
            </span>
          )}
          {required && <span className="sr-only"> (wajib)</span>}
        </label>
        {aside}
      </div>
      {children}
      {error ? (
        <p id={hintId(htmlFor)} role="alert" className="flex items-start gap-1 text-caption text-status-risk">
          <IconAlertTriangle size={16} stroke={1.75} className="shrink-0" />
          {error}
        </p>
      ) : (
        hint && (
          <p id={hintId(htmlFor)} className="text-caption text-ink-muted">
            {hint}
          </p>
        )
      )}
    </div>
  );
}
