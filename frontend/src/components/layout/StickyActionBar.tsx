import type { ReactNode } from "react";

/** Bar aksi menempel di bawah layar pada mobile, baris biasa mulai md. Satu tombol utama saja. */
export function StickyActionBar({ children }: { children: ReactNode }) {
  return (
    <>
      {/* Ruang kosong supaya konten terakhir tidak tertutup bar di mobile */}
      <div className="h-20 md:hidden" aria-hidden="true" />
      <div className="fixed inset-x-0 bottom-0 z-30 flex justify-end gap-2 border-t border-line bg-surface-raised px-4 py-3 md:static md:mt-6 md:border-0 md:bg-transparent md:p-0">
        {children}
      </div>
    </>
  );
}
