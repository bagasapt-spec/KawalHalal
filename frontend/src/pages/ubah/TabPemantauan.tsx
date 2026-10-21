import { useState } from "react";
import { IconInfoCircle } from "@tabler/icons-react";
import type { BagianPemantauan, Berkas, DokumenLain, TandaTangan } from "../../api/index.ts";
import { Button, Card, DataTable, Field, FileInput, Input, Modal, Select } from "../../components/ui/index.ts";
import type { Column, SelectOption } from "../../components/ui/index.ts";
import { AksiBaris, BerkasLabel, KonfirmasiHapus, Seksi, buatId, keBerkas, sumberPengguna, useHapus, useSimpanBagian } from "./shared.tsx";
import type { TabProps } from "./shared.tsx";

function FormTandaTangan({
  opsiPenyelia,
  onTutup,
  onSimpan,
  menyimpan,
}: {
  opsiPenyelia: SelectOption[];
  onTutup: () => void;
  onSimpan: (t: TandaTangan) => void;
  menyimpan: boolean;
}) {
  const [pj, setPj] = useState<Berkas | undefined>();
  const [penyeliaId, setPenyeliaId] = useState(opsiPenyelia[0]?.value ?? "");
  const [ttdPenyelia, setTtdPenyelia] = useState<Berkas | undefined>();
  const [dicoba, setDicoba] = useState(false);
  const galat = {
    pj: dicoba && !pj ? "Unggah foto tanda tangan penanggung jawab." : undefined,
    penyelia: dicoba && !penyeliaId ? "Pilih penyelia halal." : undefined,
    ttd: dicoba && !ttdPenyelia ? "Unggah foto tanda tangan penyelia halal." : undefined,
  };
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title="Tambah Tanda Tangan"
      footer={
        <>
          <Button variant="secondary" onClick={onTutup}>
            Batal
          </Button>
          <Button
            loading={menyimpan}
            onClick={() => {
              setDicoba(true);
              if (pj && penyeliaId && ttdPenyelia)
                onSimpan({ id: buatId("tt"), penanggungJawab: pj, penyeliaId, penyelia: ttdPenyelia, sumber: sumberPengguna() });
            }}
          >
            Simpan
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-body-sm text-ink-muted">Foto tanda tangan di atas kertas putih. Format JPG atau PNG.</p>
        <Field label="Tanda tangan penanggung jawab" htmlFor="tt-pj" required error={galat.pj}>
          <FileInput id="tt-pj" accept=".jpg,.jpeg,.png" fileName={pj?.nama} invalid={Boolean(galat.pj)} onChange={(f) => setPj(keBerkas(f))} />
        </Field>
        <Field label="Penyelia halal" htmlFor="tt-penyelia" required error={galat.penyelia}>
          <Select id="tt-penyelia" options={opsiPenyelia} value={penyeliaId} invalid={Boolean(galat.penyelia)} onValueChange={setPenyeliaId} />
        </Field>
        <Field label="Tanda tangan penyelia halal" htmlFor="tt-ttd" required error={galat.ttd}>
          <FileInput id="tt-ttd" accept=".jpg,.jpeg,.png" fileName={ttdPenyelia?.nama} invalid={Boolean(galat.ttd)} onChange={(f) => setTtdPenyelia(keBerkas(f))} />
        </Field>
      </div>
    </Modal>
  );
}

function FormDokumen({ onTutup, onSimpan, menyimpan }: { onTutup: () => void; onSimpan: (d: DokumenLain) => void; menyimpan: boolean }) {
  const [nama, setNama] = useState("");
  const [berkas, setBerkas] = useState<Berkas | undefined>();
  const [dicoba, setDicoba] = useState(false);
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title="Tambah Dokumen"
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onTutup}>
            Batal
          </Button>
          <Button
            loading={menyimpan}
            onClick={() => {
              setDicoba(true);
              if (nama.trim() && berkas) onSimpan({ id: buatId("dl"), nama: nama.trim(), berkas });
            }}
          >
            Simpan
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Nama dokumen" htmlFor="dl-nama" required error={dicoba && !nama.trim() ? "Nama dokumen belum diisi." : undefined}>
          <Input id="dl-nama" value={nama} invalid={dicoba && !nama.trim()} onChange={(e) => setNama(e.target.value)} />
        </Field>
        <Field label="Berkas" htmlFor="dl-berkas" required hint="Format PDF." error={dicoba && !berkas ? "Unggah berkas PDF." : undefined}>
          <FileInput id="dl-berkas" accept=".pdf" fileName={berkas?.nama} invalid={dicoba && !berkas} onChange={(f) => setBerkas(keBerkas(f))} />
        </Field>
      </div>
    </Modal>
  );
}

export default function TabPemantauan({ p, pu }: TabProps) {
  const { simpan, menyimpan } = useSimpanBagian(p.id);
  const [modal, setModal] = useState<"ttd" | "dokumen" | null>(null);
  const hapus = useHapus<{ kunci: keyof BagianPemantauan; id: string; nama: string }>();
  const pm = p.pemantauan;
  const skalaBesar = pu?.skala === "menengah" || pu?.skala === "besar";
  const penyelia = (pu?.penyeliaHalal ?? []).filter((x) => p.data.penyeliaIds.length === 0 || p.data.penyeliaIds.includes(x.id));
  const namaPenyelia = (id: string) => pu?.penyeliaHalal.find((x) => x.id === id)?.nama ?? "-";

  const simpanPemantauan = async (isi: BagianPemantauan, pesan: string) => {
    if (await simpan({ bagian: "pemantauan", isi }, pesan)) setModal(null);
  };

  const kolomTtd: Column<TandaTangan>[] = [
    { key: "penyelia", header: "Nama Penyelia Halal", primary: true, cell: (x) => namaPenyelia(x.penyeliaId) },
    { key: "pj", header: "Tanda Tangan Penanggung Jawab", cell: (x) => <BerkasLabel berkas={x.penanggungJawab} /> },
    { key: "ttd", header: "Tanda Tangan Penyelia", cell: (x) => <BerkasLabel berkas={x.penyelia} /> },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (x) => <AksiBaris nama="tanda tangan" onHapus={() => hapus.minta({ kunci: "tandaTangan", id: x.id, nama: "tanda tangan" })} />,
    },
  ];

  const kolomDokumen: Column<DokumenLain>[] = [
    { key: "nama", header: "Nama Dokumen", primary: true, cell: (x) => x.nama },
    { key: "berkas", header: "Berkas", cell: (x) => <BerkasLabel berkas={x.berkas} /> },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (x) => <AksiBaris nama={x.nama} onHapus={() => hapus.minta({ kunci: "dokumenLain", id: x.id, nama: x.nama })} />,
    },
  ];

  return (
    <>
      {skalaBesar ? (
        <Seksi title="Dokumen Lainnya" description="Dokumen pendukung untuk usaha skala menengah dan besar. Format PDF." onTambah={() => setModal("dokumen")}>
          <DataTable caption="Dokumen lainnya" columns={kolomDokumen} rows={pm.dokumenLain} getRowId={(x) => x.id} numbered emptyMessage="Belum ada dokumen." />
        </Seksi>
      ) : (
        <Card title="Dokumen Lainnya">
          <p className="flex gap-2 text-body-sm text-ink-muted">
            <IconInfoCircle size={20} stroke={1.75} className="shrink-0 text-brand" aria-hidden="true" />
            Bagian ini hanya untuk usaha skala menengah dan besar. Usaha Anda tercatat skala {pu?.skala ?? "mikro"}, jadi bagian ini tidak
            perlu diisi.
          </p>
        </Card>
      )}

      <Seksi title="Tanda Tangan" description="Tanda tangan penanggung jawab dan penyelia halal untuk dokumen pengajuan." onTambah={() => setModal("ttd")}>
        <DataTable
          caption="Tanda tangan"
          columns={kolomTtd}
          rows={pm.tandaTangan}
          getRowId={(x) => x.id}
          numbered
          emptyMessage="Belum ada tanda tangan. Tambahkan foto tanda tangan penanggung jawab dan penyelia halal."
        />
      </Seksi>

      {modal === "ttd" && (
        <FormTandaTangan
          opsiPenyelia={penyelia.map((x) => ({ value: x.id, label: x.nama }))}
          menyimpan={menyimpan}
          onTutup={() => setModal(null)}
          onSimpan={(t) => simpanPemantauan({ ...pm, tandaTangan: [...pm.tandaTangan, t] }, "Tanda tangan tersimpan")}
        />
      )}
      {modal === "dokumen" && (
        <FormDokumen
          menyimpan={menyimpan}
          onTutup={() => setModal(null)}
          onSimpan={(d) => simpanPemantauan({ ...pm, dokumenLain: [...pm.dokumenLain, d] }, "Dokumen tersimpan")}
        />
      )}

      <KonfirmasiHapus
        nama={hapus.target?.nama ?? "data"}
        open={hapus.target !== null}
        onOpenChange={(o) => !o && hapus.tutup()}
        loading={menyimpan}
        onConfirm={async () => {
          const t = hapus.target;
          if (!t) return;
          const daftar = pm[t.kunci] as Array<{ id: string }>;
          if (await simpan({ bagian: "pemantauan", isi: { ...pm, [t.kunci]: daftar.filter((x) => x.id !== t.id) } }, "Data dihapus"))
            hapus.tutup();
        }}
      />
    </>
  );
}
