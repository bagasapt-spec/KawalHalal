import { useState } from "react";
import type { ReactNode } from "react";
import { IconPencil, IconPlus, IconTrash } from "@tabler/icons-react";
import type { Berkas } from "../../api/types.ts";
import { Button } from "./Button.tsx";
import { Card } from "./Card.tsx";
import { ConfirmDialog } from "./ConfirmDialog.tsx";
import { IconButton } from "./IconButton.tsx";

/** Id lokal untuk item baru; backend boleh menggantinya. */
export function buatId(awalan: string) {
  return `${awalan}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

/** Ubah pilihan FileInput jadi Berkas. Mode mock hanya menyimpan nama berkas, belum mengunggah isinya. */
export function keBerkas(file: File | null): Berkas | undefined {
  return file ? { nama: file.name } : undefined;
}

/** Kartu satu bagian dengan tombol Tambah di kanan judul. */
export function Seksi({
  title,
  description,
  onTambah,
  labelTambah = "Tambah",
  children,
}: {
  title: string;
  description?: ReactNode;
  onTambah?: () => void;
  labelTambah?: string;
  children: ReactNode;
}) {
  return (
    <Card
      title={title}
      description={description}
      actions={
        onTambah && (
          <Button size="sm" variant="secondary" icon={<IconPlus size={16} stroke={1.75} />} onClick={onTambah}>
            {labelTambah}
          </Button>
        )
      }
    >
      {children}
    </Card>
  );
}

/** Tombol ubah dan hapus di kolom Aksi. Ikon sama di semua tabel. */
export function AksiBaris({ nama, onUbah, onHapus }: { nama: string; onUbah?: () => void; onHapus?: () => void }) {
  return (
    <div className="flex justify-end gap-1">
      {onUbah && <IconButton label={`Ubah ${nama}`} tone="brand" icon={<IconPencil size={18} stroke={1.75} />} onClick={onUbah} />}
      {onHapus && <IconButton label={`Hapus ${nama}`} tone="danger" icon={<IconTrash size={18} stroke={1.75} />} onClick={onHapus} />}
    </div>
  );
}

/** State konfirmasi hapus untuk satu tabel. */
export function useHapus<T>() {
  const [target, setTarget] = useState<T | null>(null);
  return { target, minta: setTarget, tutup: () => setTarget(null) };
}

export function KonfirmasiHapus({
  nama,
  open,
  onOpenChange,
  onConfirm,
  loading,
  catatan,
}: {
  nama: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  loading?: boolean;
  catatan?: string;
}) {
  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      tone="danger"
      title={`Hapus ${nama}`}
      description={catatan ?? "Data ini akan dihapus dari pengajuan."}
      confirmLabel="Hapus"
      loading={loading}
      onConfirm={onConfirm}
    />
  );
}
