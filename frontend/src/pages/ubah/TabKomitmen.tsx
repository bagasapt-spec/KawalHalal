import { useState } from "react";
import type { AnggotaKomitmen, Komitmen } from "../../api/index.ts";
import { Button, DataTable, Field, Input, Modal, Select } from "../../components/ui/index.ts";
import type { Column } from "../../components/ui/index.ts";
import { AksiBaris, BlokPersetujuan, DenganTanda, KonfirmasiHapus, Seksi, buatId, sumberPengguna, useHapus, useSimpanBagian } from "./shared.tsx";
import type { TabProps } from "./shared.tsx";

type KunciPersetujuan = "kebijakanHalal" | "pengertianHalalHaram" | "praktikSjph";

const pernyataan: Array<{ kunci: KunciPersetujuan; judul: string; poin: string[] }> = [
  {
    kunci: "kebijakanHalal",
    judul: "Kebijakan Halal",
    poin: [
      "Hanya memakai bahan yang jelas asal-usulnya dan menyimpan buktinya.",
      "Menjalankan proses produksi sesuai arahan Pendamping PPH.",
      "Menjaga tempat produksi bebas dari bahan najis dan bahan yang tidak halal.",
      "Memberi tahu pendamping sebelum mengganti bahan atau cara produksi.",
    ],
  },
  {
    kunci: "pengertianHalalHaram",
    judul: "Pengertian Halal dan Haram",
    poin: [
      "Halal berarti boleh dikonsumsi menurut syariat Islam.",
      "Babi dan turunannya, bangkai, darah, dan khamar tidak boleh dipakai.",
      "Daging dan unggas harus disembelih sesuai syariat dan dibuktikan dengan dokumen.",
      "Bahan yang asalnya belum jelas ditelusuri dulu sebelum dipakai.",
    ],
  },
  {
    kunci: "praktikSjph",
    judul: "Praktik Sistem Jaminan Produk Halal",
    poin: [
      "Mencatat setiap pembelian bahan beserta notanya.",
      "Memeriksa bahan saat diterima.",
      "Memisahkan bahan dan produk dari sumber kontaminasi.",
      "Memakai peralatan yang bersih dan khusus untuk produk yang didaftarkan.",
      "Mencatat hasil produksi dan penjualan.",
    ],
  },
];

const opsiPosisi = [
  { value: "ketua", label: "Ketua" },
  { value: "anggota", label: "Anggota" },
];

function FormAnggota({
  awal,
  onTutup,
  onSimpan,
  menyimpan,
}: {
  awal?: AnggotaKomitmen;
  onTutup: () => void;
  onSimpan: (a: AnggotaKomitmen) => void;
  menyimpan: boolean;
}) {
  const [nama, setNama] = useState(awal?.nama ?? "");
  const [jabatan, setJabatan] = useState(awal?.jabatan ?? "");
  const [posisi, setPosisi] = useState<AnggotaKomitmen["posisi"]>(awal?.posisi ?? "anggota");
  const [dicoba, setDicoba] = useState(false);

  const simpan = () => {
    setDicoba(true);
    if (!nama.trim() || !jabatan.trim()) return;
    onSimpan({ id: awal?.id ?? buatId("ak"), nama: nama.trim(), jabatan: jabatan.trim(), posisi, sumber: sumberPengguna() });
  };

  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title={awal ? "Ubah Anggota Komitmen" : "Tambah Anggota Komitmen"}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onTutup}>
            Batal
          </Button>
          <Button onClick={simpan} loading={menyimpan}>
            Simpan
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Nama" htmlFor="ak-nama" required error={dicoba && !nama.trim() ? "Nama belum diisi." : undefined}>
          <Input id="ak-nama" value={nama} invalid={dicoba && !nama.trim()} onChange={(e) => setNama(e.target.value)} />
        </Field>
        <Field
          label="Jabatan"
          htmlFor="ak-jabatan"
          required
          error={dicoba && !jabatan.trim() ? "Jabatan belum diisi, misalnya Pemilik usaha atau Juru masak." : undefined}
        >
          <Input id="ak-jabatan" value={jabatan} invalid={dicoba && !jabatan.trim()} onChange={(e) => setJabatan(e.target.value)} />
        </Field>
        <Field label="Posisi" htmlFor="ak-posisi" required>
          <Select id="ak-posisi" options={opsiPosisi} value={posisi} onValueChange={(v) => setPosisi(v as AnggotaKomitmen["posisi"])} />
        </Field>
      </div>
    </Modal>
  );
}

export default function TabKomitmen({ p }: TabProps) {
  const { simpan, menyimpan } = useSimpanBagian(p.id);
  const [form, setForm] = useState<{ awal?: AnggotaKomitmen } | null>(null);
  const hapus = useHapus<AnggotaKomitmen>();
  const k = p.komitmen;

  const simpanKomitmen = (isi: Komitmen, pesan: string) => simpan({ bagian: "komitmen", isi }, pesan);

  const kolom: Column<AnggotaKomitmen>[] = [
    { key: "nama", header: "Nama", primary: true, cell: (a) => <DenganTanda sumber={a.sumber}>{a.nama}</DenganTanda> },
    { key: "jabatan", header: "Jabatan", cell: (a) => a.jabatan },
    { key: "posisi", header: "Posisi", cell: (a) => (a.posisi === "ketua" ? "Ketua" : "Anggota") },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (a) => <AksiBaris nama={a.nama} onUbah={() => setForm({ awal: a })} onHapus={() => hapus.minta(a)} />,
    },
  ];

  return (
    <>
      {pernyataan.map(({ kunci, judul, poin }) => (
        <BlokPersetujuan
          key={kunci}
          id={kunci}
          judul={judul}
          persetujuan={k[kunci]}
          menyimpan={menyimpan}
          onSetuju={() =>
            simpanKomitmen(
              { ...k, [kunci]: { disetujuiPada: new Date().toISOString(), sumber: sumberPengguna() } },
              `${judul} disetujui`,
            )
          }
          isi={
            <ol className="list-decimal space-y-1 pl-5">
              {poin.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ol>
          }
        />
      ))}

      <Seksi
        title="Tim komitmen dan tanggung jawab"
        description="Orang yang bertanggung jawab menjalankan proses produk halal. Untuk usaha mikro cukup pemilik sebagai ketua."
        onTambah={() => setForm({})}
      >
        <DataTable
          caption="Anggota komitmen dan tanggung jawab"
          columns={kolom}
          rows={k.anggota}
          getRowId={(a) => a.id}
          numbered
          emptyMessage="Belum ada anggota. Tambahkan minimal satu orang sebagai ketua."
        />
      </Seksi>

      {form && (
        <FormAnggota
          awal={form.awal}
          menyimpan={menyimpan}
          onTutup={() => setForm(null)}
          onSimpan={async (a) => {
            const anggota = form.awal ? k.anggota.map((x) => (x.id === a.id ? a : x)) : [...k.anggota, a];
            if (await simpanKomitmen({ ...k, anggota }, "Anggota komitmen tersimpan")) setForm(null);
          }}
        />
      )}

      <KonfirmasiHapus
        nama={hapus.target?.nama ?? "anggota"}
        open={hapus.target !== null}
        onOpenChange={(o) => !o && hapus.tutup()}
        loading={menyimpan}
        onConfirm={async () => {
          if (!hapus.target) return;
          const id = hapus.target.id;
          if (await simpanKomitmen({ ...k, anggota: k.anggota.filter((x) => x.id !== id) }, "Anggota dihapus")) hapus.tutup();
        }}
      />
    </>
  );
}
