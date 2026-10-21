import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react";
import { IconButton } from "./IconButton.tsx";

export interface PaginationProps {
  /** Halaman aktif, mulai dari 1. */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <nav aria-label="Navigasi halaman" className="flex items-center justify-end gap-2">
      <span className="text-caption text-ink-muted">
        {from}–{to} dari {total}
      </span>
      <IconButton
        label="Halaman sebelumnya"
        icon={<IconChevronLeft size={20} stroke={1.75} />}
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
      />
      <IconButton
        label="Halaman berikutnya"
        icon={<IconChevronRight size={20} stroke={1.75} />}
        disabled={page >= lastPage}
        onClick={() => onPageChange(page + 1)}
      />
    </nav>
  );
}
