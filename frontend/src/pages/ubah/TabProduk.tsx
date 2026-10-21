import { useState } from "react";
import { Link } from "react-router";
import type { PemetaanProduk } from "../../api/index.ts";
import { StickyActionBar } from "../../components/layout/StickyActionBar.tsx";
import { Button, Card, Checkbox } from "../../components/ui/index.ts";
import { buatId, useSimpanBagian } from "./shared.tsx";
import type { TabProps } from "./shared.tsx";

const kunci = (produkId: string, pabrikId: string) => `${produkId}|${pabrikId}`;

/** Pemetaan produk ke pabrik sebagai tabel centang, menggantikan modal "pilih nomor s.d." di SIHALAL. */
export default function TabProduk({ p, pu }: TabProps) {
  const { simpan, menyimpan } = useSimpanBagian(p.id);
  const awal = new Set(p.pemetaan.map((m) => kunci(m.produkId, m.pabrikId)));
  const [dipilih, setDipilih] = useState<Set<string>>(awal);
  const pabrik = (pu?.pabrik ?? []).filter((x) => p.data.pabrikIds.includes(x.id));
  const berubah = dipilih.size !== awal.size || [...dipilih].some((k) => !awal.has(k));

  const ubah = (k: string, aktif: boolean) =>
    setDipilih((s) => {
      const baru = new Set(s);
      if (aktif) baru.add(k);
      else baru.delete(k);
      return baru;
    });

  const simpanPemetaan = () => {
    const isi: PemetaanProduk[] = [...dipilih].map((k) => {
      const [produkId, pabrikId] = k.split("|");
      return p.pemetaan.find((m) => m.produkId === produkId && m.pabrikId === pabrikId) ?? { id: buatId("pp"), produkId, pabrikId };
    });
    return simpan({ bagian: "pemetaan", isi }, "Pemetaan produk tersimpan");
  };

  if (p.produk.length === 0 || pabrik.length === 0) {
    return (
      <Card title="Pemetaan Produk dan Pabrik">
        <p className="text-body-sm text-ink-muted">
          {p.produk.length === 0 ? (
            <>
              Belum ada produk.{" "}
              <Link to="?tab=bahan" className="text-brand underline">
                Tambahkan produk di tab Bahan
              </Link>
              .
            </>
          ) : (
            <>
              Belum ada pabrik yang dipilih.{" "}
              <Link to="?tab=data" className="text-brand underline">
                Pilih pabrik di tab Data Pengajuan
              </Link>
              .
            </>
          )}
        </p>
      </Card>
    );
  }

  return (
    <>
      <Card
        title="Pemetaan Produk dan Pabrik"
        description="Centang pabrik tempat setiap produk dibuat. Setiap produk perlu minimal satu pabrik."
        actions={
          pabrik.length === 1 && (
            <Button size="sm" variant="secondary" onClick={() => setDipilih(new Set(p.produk.map((x) => kunci(x.id, pabrik[0].id))))}>
              Petakan semua ke {pabrik[0].nama}
            </Button>
          )
        }
      >
        <div className="overflow-x-auto rounded-sm border border-line">
          <table className="w-full border-collapse">
            <caption className="sr-only">Pemetaan produk dan pabrik</caption>
            <thead className="bg-surface">
              <tr>
                <th scope="col" className="px-3 py-3 text-left text-label text-ink-muted">
                  Nama Produk
                </th>
                {pabrik.map((pb) => (
                  <th key={pb.id} scope="col" className="px-3 py-3 text-left text-label text-ink-muted">
                    {pb.nama}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {p.produk.map((pr) => {
                const belum = !pabrik.some((pb) => dipilih.has(kunci(pr.id, pb.id)));
                return (
                  <tr key={pr.id} className="border-t border-line">
                    <th scope="row" className="px-3 py-3 text-left text-body-sm font-normal text-ink">
                      {pr.nama}
                      {belum && <span className="block text-caption text-status-warn">Belum dipetakan</span>}
                    </th>
                    {pabrik.map((pb) => (
                      <td key={pb.id} className="px-3 py-3">
                        <Checkbox
                          id={`map-${pr.id}-${pb.id}`}
                          label={<span className="sr-only">{`${pr.nama} dibuat di ${pb.nama}`}</span>}
                          checked={dipilih.has(kunci(pr.id, pb.id))}
                          onCheckedChange={(aktif) => ubah(kunci(pr.id, pb.id), aktif)}
                        />
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <StickyActionBar>
        {!berubah && <span className="mr-auto self-center text-caption text-ink-muted">Belum ada perubahan.</span>}
        {berubah && (
          <Button variant="secondary" onClick={() => setDipilih(awal)}>
            Batalkan perubahan
          </Button>
        )}
        <Button onClick={simpanPemetaan} loading={menyimpan} disabled={!berubah}>
          Simpan
        </Button>
      </StickyActionBar>
    </>
  );
}
