import { useState } from "react";
import type { ReactNode } from "react";
import { useUbahBagian } from "../../api/index.ts";
import type { PelakuUsaha, Pengajuan, PerubahanBagian, Persetujuan, Sumber } from "../../api/index.ts";
import { Button, Card, Checkbox, StatusBadge, useToast } from "../../components/ui/index.ts";
import { formatWaktu, labelPelaku } from "../../lib/format.ts";

export { AksiBaris, KonfirmasiHapus, Seksi, buatId, keBerkas, useHapus } from "../../components/ui/Seksi.tsx";
export { DenganTanda } from "../../components/kawal/ProvenanceMark.tsx";
export { BerkasLabel } from "../../components/ui/BerkasLabel.tsx";

export interface TabProps {
  p: Pengajuan;
  pu: PelakuUsaha | undefined;
}

/** Penanda bahwa data diisi atau diubah manual oleh pelaku usaha. */
export function sumberPengguna(): Sumber {
  return { oleh: "pengguna", waktu: new Date().toISOString() };
}

/** Simpan satu bagian lalu tampilkan notifikasi. Mengembalikan true bila berhasil. */
export function useSimpanBagian(id: string) {
  const ubah = useUbahBagian(id);
  const toast = useToast();
  const simpan = async (perubahan: PerubahanBagian, pesan: string) => {
    try {
      await ubah.mutateAsync(perubahan);
      toast({ title: pesan });
      return true;
    } catch (e) {
      toast({ tone: "risk", title: "Perubahan belum tersimpan", description: (e as Error).message });
      return false;
    }
  };
  return { simpan, menyimpan: ubah.isPending };
}

/** Blok pernyataan yang disetujui pelaku usaha (komitmen, bebas babi). */
export function BlokPersetujuan({
  id,
  judul,
  isi,
  persetujuan,
  onSetuju,
  menyimpan,
}: {
  id: string;
  judul: string;
  isi: ReactNode;
  persetujuan: Persetujuan | null;
  onSetuju: () => void;
  menyimpan: boolean;
}) {
  const [dicentang, setDicentang] = useState(false);
  return (
    <Card title={judul}>
      <div className="rounded-md bg-brand-tint p-4 text-body-sm text-ink">{isi}</div>
      <div className="mt-4">
        {persetujuan ? (
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge tone="ok">Disetujui</StatusBadge>
            <span className="text-caption text-ink-muted">
              {formatWaktu(persetujuan.disetujuiPada)}
              {persetujuan.sumber &&
                ` · ${persetujuan.sumber.catatan ?? labelPelaku[persetujuan.sumber.oleh]}`}
            </span>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <Checkbox
              id={`${id}-setuju`}
              checked={dicentang}
              onCheckedChange={setDicentang}
              label="Saya telah membaca seluruh pernyataan dan bersedia memenuhinya."
            />
            <div className="flex flex-wrap items-center gap-3">
              <Button size="sm" onClick={onSetuju} disabled={!dicentang} loading={menyimpan}>
                Saya setuju
              </Button>
              {!dicentang && <span className="text-caption text-ink-muted">Centang pernyataan di atas untuk melanjutkan.</span>}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
