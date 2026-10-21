import type { ReactNode } from "react";
import { IconAlertTriangle, IconInbox } from "@tabler/icons-react";
import { cn } from "../../lib/cn.ts";
import { Button } from "./Button.tsx";

export interface Column<T> {
  key: string;
  header: string;
  cell: (row: T, index: number) => ReactNode;
  className?: string;
  align?: "left" | "center" | "right";
  /** Jadi judul kartu di tampilan mobile. */
  primary?: boolean;
  /** Kolom Aksi: di mobile diletakkan di bawah kartu tanpa label. */
  action?: boolean;
}

export interface DataTableProps<T> {
  /** Nama tabel untuk pembaca layar. */
  caption: string;
  columns: Column<T>[];
  rows: T[] | undefined;
  getRowId: (row: T) => string;
  /** Tambahkan kolom "No" di kiri. */
  numbered?: boolean;
  /** Nomor awal untuk tabel berhalaman. */
  numberOffset?: number;
  loading?: boolean;
  /** Pesan galat: sebut masalahnya lalu langkah berikutnya. */
  error?: string | null;
  onRetry?: () => void;
  emptyMessage?: string;
  emptyAction?: ReactNode;
  footer?: ReactNode;
}

const alignCls = { left: "text-left", center: "text-center", right: "text-right" } as const;

function StateBox({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-4 py-10 text-center text-body-sm text-ink-muted">
      <span aria-hidden="true">{icon}</span>
      {children}
    </div>
  );
}

/** Tabel di desktop, daftar kartu di mobile. Selalu punya state memuat, galat, dan kosong. */
export function DataTable<T>({
  caption,
  columns,
  rows,
  getRowId,
  numbered = false,
  numberOffset = 0,
  loading = false,
  error,
  onRetry,
  emptyMessage = "Belum ada data.",
  emptyAction,
  footer,
}: DataTableProps<T>) {
  const allColumns: Column<T>[] = numbered
    ? [{ key: "__no", header: "No", cell: (_r, i) => numberOffset + i + 1, className: "w-14" }, ...columns]
    : columns;

  let body: ReactNode;
  if (loading) {
    body = (
      <div className="flex flex-col gap-2 p-4" aria-busy="true" aria-label="Memuat data">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-10 animate-pulse rounded-sm bg-surface" />
        ))}
      </div>
    );
  } else if (error) {
    body = (
      <StateBox icon={<IconAlertTriangle size={24} stroke={1.75} className="text-status-risk" />}>
        <p role="alert">{error}</p>
        {onRetry && (
          <Button size="sm" variant="secondary" onClick={onRetry}>
            Coba lagi
          </Button>
        )}
      </StateBox>
    );
  } else if (!rows || rows.length === 0) {
    body = (
      <StateBox icon={<IconInbox size={24} stroke={1.75} />}>
        <p>{emptyMessage}</p>
        {emptyAction}
      </StateBox>
    );
  }

  const dataColumns = allColumns.filter((c) => !c.action && !c.primary && c.key !== "__no");
  const primaryColumn = allColumns.find((c) => c.primary);
  const actionColumn = allColumns.find((c) => c.action);

  return (
    <div className="overflow-hidden rounded-sm border border-line">
      {body ?? (
        <>
          {/* Desktop: tabel lebar digeser di dalam kartu, tidak terpotong */}
          <div className="hidden overflow-x-auto md:block">
          <table className="w-full border-collapse">
            <caption className="sr-only">{caption}</caption>
            <thead className="bg-surface">
              <tr>
                {allColumns.map((col) => (
                  <th
                    key={col.key}
                    scope="col"
                    className={cn("px-3 py-3 text-label text-ink-muted", alignCls[col.align ?? "left"], col.className)}
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows!.map((row, i) => (
                <tr key={getRowId(row)} className="border-t border-line hover:bg-brand-tint/40">
                  {allColumns.map((col) => (
                    <td
                      key={col.key}
                      className={cn(
                        "px-3 py-3 align-middle text-body-sm text-ink",
                        alignCls[col.align ?? "left"],
                        col.className,
                      )}
                    >
                      {col.cell(row, i)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          </div>

          {/* Mobile */}
          <ul className="divide-y divide-line md:hidden" aria-label={caption}>
            {rows!.map((row, i) => (
              <li key={getRowId(row)} className="flex flex-col gap-2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 text-body-sm font-semibold text-ink">
                    {numbered && <span className="mr-2 text-ink-muted">{numberOffset + i + 1}.</span>}
                    {primaryColumn?.cell(row, i)}
                  </div>
                  {actionColumn && <div className="-my-1 shrink-0">{actionColumn.cell(row, i)}</div>}
                </div>
                {dataColumns.length > 0 && (
                  <dl className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-x-3 gap-y-1">
                    {dataColumns.map((col) => (
                      <div key={col.key} className="contents">
                        <dt className="text-caption text-ink-muted">{col.header}</dt>
                        <dd className="min-w-0 break-words text-body-sm text-ink">{col.cell(row, i)}</dd>
                      </div>
                    ))}
                  </dl>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {footer && <div className="border-t border-line px-3 py-2">{footer}</div>}
    </div>
  );
}
