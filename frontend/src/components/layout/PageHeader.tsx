import type { ReactNode } from "react";
import { Link } from "react-router";
import { IconArrowLeft } from "@tabler/icons-react";

export interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  /** Tautan kembali di atas judul. */
  back?: { to: string; label: string };
  /** Badge atau info di samping judul. */
  meta?: ReactNode;
  actions?: ReactNode;
}

export function PageHeader({ title, description, back, meta, actions }: PageHeaderProps) {
  return (
    <header className="mb-6 flex flex-col gap-3">
      {back && (
        <Link to={back.to} className="inline-flex items-center gap-1 self-start text-label text-brand hover:underline">
          <IconArrowLeft size={16} stroke={1.75} aria-hidden="true" />
          {back.label}
        </Link>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-h2 md:text-h1">{title}</h1>
            {meta}
          </div>
          {description && <p className="mt-1 text-body text-ink-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
    </header>
  );
}
