import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn.ts";

export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title?: ReactNode;
  description?: ReactNode;
  /** Aksi di kanan judul, misalnya tombol Tambah. */
  actions?: ReactNode;
}

/** Kartu putih dengan garis tipis: batas, bukan bayangan. */
export function Card({ title, description, actions, className, children, ...rest }: CardProps) {
  return (
    <section className={cn("rounded-lg border border-line bg-surface-raised p-4 md:p-6", className)} {...rest}>
      {(title || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            {title && <h3 className="text-h3 text-ink">{title}</h3>}
            {description && <p className="mt-1 text-body-sm text-ink-muted">{description}</p>}
          </div>
          {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
