import { useState } from "react";
import type { ReactNode } from "react";
import type {
  AlurProses,
  BagianProses,
  Berkas,
  CatatanPenyimpanan,
  Distribusi,
  HasilProduksi,
  LayoutProduksi,
} from "../../api/index.ts";
import {
  Button,
  Card,
  DataTable,
  DateInput,
  Field,
  FileInput,
  Input,
  Modal,
  SegmentedToggle,
  Select,
  Textarea,
} from "../../components/ui/index.ts";
import type { Column, SelectOption } from "../../components/ui/index.ts";
import { formatTanggal } from "../../lib/format.ts";
import {
  AksiBaris,
  BerkasLabel,
  BlokPersetujuan,
  DenganTanda,
  KonfirmasiHapus,
  Seksi,
  buatId,
  keBerkas,
  sumberPengguna,
  useHapus,
  useSimpanBagian,
} from "./shared.tsx";
import type { TabProps } from "./shared.tsx";

// ---------- Kerangka modal formulir ----------

function ModalForm({
  title,
  onTutup,
  onSimpan,
  menyimpan,
  children,
}: {
  title: string;
  onTutup: () => void;
  onSimpan: () => void;
  menyimpan: boolean;
  children: ReactNode;
}) {
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onTutup}>
            Batal
          </Button>
          <Button onClick={onSimpan} loading={menyimpan}>
            Simpan
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">{children}</div>
    </Modal>
  );
}

interface FormProps<T> {
  awal?: T;
  onTutup: () => void;
  onSimpan: (item: T) => void;
  menyimpan: boolean;
}

// ---------- Formulir ----------

function FormLayout({ opsiPabrik, ...f }: FormProps<LayoutProduksi> & { opsiPabrik: SelectOption[] }) {
  const [pabrikId, setPabrikId] = useState(f.awal?.pabrikId ?? opsiPabrik[0]?.value ?? "");
  const [berkas, setBerkas] = useState<Berkas | undefined>(f.awal?.berkas);
  const [dicoba, setDicoba] = useState(false);
  return (
    <ModalForm
      title="Tambah Layout Ruang Produksi"
      {...f}
      onSimpan={() => {
        setDicoba(true);
        if (pabrikId && berkas) f.onSimpan({ id: f.awal?.id ?? buatId("lp"), pabrikId, berkas, sumber: sumberPengguna() });
      }}
    >
      <Field label="Pabrik atau dapur" htmlFor="lp-pabrik" required error={dicoba && !pabrikId ? "Pilih pabrik." : undefined}>
        <Select id="lp-pabrik" options={opsiPabrik} value={pabrikId} onValueChange={setPabrikId} />
      </Field>
      <Field
        label="Denah ruang produksi"
        htmlFor="lp-berkas"
        required
        hint="Foto atau gambar denah dapur. Format JPG, PNG, atau PDF."
        error={dicoba && !berkas ? "Unggah foto atau gambar denah." : undefined}
      >
        <FileInput id="lp-berkas" accept=".jpg,.jpeg,.png,.pdf" fileName={berkas?.nama} invalid={dicoba && !berkas} onChange={(x) => setBerkas(keBerkas(x))} />
      </Field>
    </ModalForm>
  );
}

function FormPenyimpanan({
  opsiBahan,
  opsiProduk,
  ...f
}: FormProps<CatatanPenyimpanan> & { opsiBahan: SelectOption[]; opsiProduk: SelectOption[] }) {
  const [jenis, setJenis] = useState<CatatanPenyimpanan["jenis"]>(f.awal?.jenis ?? "bahan");
  const [refId, setRefId] = useState(f.awal?.refId ?? "");
  const [jumlah, setJumlah] = useState(f.awal ? String(f.awal.jumlah) : "");
  const [masuk, setMasuk] = useState(f.awal?.tanggalMasuk ?? "");
  const [keluar, setKeluar] = useState(f.awal?.tanggalKeluar ?? "");
  const [dicoba, setDicoba] = useState(false);
  const angka = Number(jumlah);
  const galat = {
    refId: dicoba && !refId ? `Pilih ${jenis}.` : undefined,
    jumlah: dicoba && !(angka > 0) ? "Isi jumlah lebih dari 0." : undefined,
    masuk: dicoba && !masuk ? "Tanggal masuk belum diisi." : undefined,
    keluar: keluar && masuk && keluar < masuk ? "Tanggal keluar tidak boleh sebelum tanggal masuk." : undefined,
  };
  return (
    <ModalForm
      title={f.awal ? "Ubah Catatan Penyimpanan" : "Tambah Catatan Penyimpanan"}
      {...f}
      onSimpan={() => {
        setDicoba(true);
        if (!refId || !(angka > 0) || !masuk || galat.keluar) return;
        f.onSimpan({
          id: f.awal?.id ?? buatId("ps"),
          jenis,
          refId,
          jumlah: angka,
          tanggalMasuk: masuk,
          tanggalKeluar: keluar || undefined,
          sumber: sumberPengguna(),
        });
      }}
    >
      <SegmentedToggle
        label="Jenis yang disimpan"
        className="self-start"
        value={jenis}
        onValueChange={(v) => {
          setJenis(v);
          setRefId("");
        }}
        options={[
          { value: "bahan", label: "Bahan" },
          { value: "produk", label: "Produk" },
        ]}
      />
      <Field label={jenis === "bahan" ? "Nama bahan" : "Nama produk"} htmlFor="ps-ref" required error={galat.refId}>
        <Select id="ps-ref" options={jenis === "bahan" ? opsiBahan : opsiProduk} value={refId} invalid={Boolean(galat.refId)} onValueChange={setRefId} />
      </Field>
      <Field label="Jumlah" htmlFor="ps-jumlah" required error={galat.jumlah}>
        <Input id="ps-jumlah" type="number" min={0} step="any" inputMode="decimal" value={jumlah} invalid={Boolean(galat.jumlah)} onChange={(e) => setJumlah(e.target.value)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Tanggal masuk" htmlFor="ps-masuk" required error={galat.masuk}>
          <DateInput id="ps-masuk" value={masuk} invalid={Boolean(galat.masuk)} onChange={(e) => setMasuk(e.target.value)} />
        </Field>
        <Field label="Tanggal keluar" htmlFor="ps-keluar" error={galat.keluar} hint="Kosongkan bila masih disimpan.">
          <DateInput id="ps-keluar" value={keluar} invalid={Boolean(galat.keluar)} onChange={(e) => setKeluar(e.target.value)} />
        </Field>
      </div>
    </ModalForm>
  );
}

function FormAlur(f: FormProps<AlurProses>) {
  const [mode, setMode] = useState<"tulis" | "unggah">(f.awal?.berkas && f.awal.langkah.length === 0 ? "unggah" : "tulis");
  const [judul, setJudul] = useState(f.awal?.judul ?? "");
  const [teks, setTeks] = useState((f.awal?.langkah ?? []).join("\n"));
  const [berkas, setBerkas] = useState<Berkas | undefined>(f.awal?.berkas);
  const [dicoba, setDicoba] = useState(false);
  const langkah = teks
    .split("\n")
    .map((l) => l.replace(/^\s*\d+[.)]\s*/, "").trim())
    .filter(Boolean);
  const galat = {
    judul: dicoba && !judul.trim() ? "Judul proses belum diisi, misalnya Pembuatan bakso." : undefined,
    isi:
      dicoba && mode === "tulis" && langkah.length === 0
        ? "Tulis minimal satu langkah."
        : dicoba && mode === "unggah" && !berkas
          ? "Unggah berkas diagram alur."
          : undefined,
  };
  return (
    <ModalForm
      title={f.awal ? "Ubah Diagram Alur Proses" : "Tambah Diagram Alur Proses"}
      {...f}
      onSimpan={() => {
        setDicoba(true);
        if (!judul.trim() || (mode === "tulis" ? langkah.length === 0 : !berkas)) return;
        f.onSimpan({
          id: f.awal?.id ?? buatId("ap"),
          judul: judul.trim(),
          langkah: mode === "tulis" ? langkah : [],
          berkas: mode === "unggah" ? berkas : undefined,
          sumber: sumberPengguna(),
        });
      }}
    >
      <SegmentedToggle
        label="Cara mengisi alur proses"
        className="self-center"
        value={mode}
        onValueChange={setMode}
        options={[
          { value: "unggah", label: "Unggah File" },
          { value: "tulis", label: "Tulis Langkah" },
        ]}
      />
      <Field label="Judul proses" htmlFor="ap-judul" required error={galat.judul}>
        <Input id="ap-judul" value={judul} invalid={Boolean(galat.judul)} onChange={(e) => setJudul(e.target.value)} />
      </Field>
      {mode === "tulis" ? (
        <Field
          label="Langkah proses"
          htmlFor="ap-langkah"
          required
          hint={`Satu langkah per baris, urut dari awal. Terbaca ${langkah.length} langkah.`}
          error={galat.isi}
        >
          <Textarea
            id="ap-langkah"
            rows={8}
            value={teks}
            invalid={Boolean(galat.isi)}
            placeholder={"Daging dicuci lalu digiling\nAdonan dicampur tapioka dan bumbu\nAdonan dibentuk lalu direbus"}
            onChange={(e) => setTeks(e.target.value)}
          />
        </Field>
      ) : (
        <Field label="Berkas diagram alur" htmlFor="ap-berkas" required hint="Format JPG, PNG, atau PDF." error={galat.isi}>
          <FileInput id="ap-berkas" accept=".jpg,.jpeg,.png,.pdf" fileName={berkas?.nama} invalid={Boolean(galat.isi)} onChange={(x) => setBerkas(keBerkas(x))} />
        </Field>
      )}
    </ModalForm>
  );
}

function FormHasil({ opsiProduk, ...f }: FormProps<HasilProduksi> & { opsiProduk: SelectOption[] }) {
  const [produkId, setProdukId] = useState(f.awal?.produkId ?? "");
  const [jumlah, setJumlah] = useState(f.awal ? String(f.awal.jumlah) : "");
  const [produksi, setProduksi] = useState(f.awal?.tanggalProduksi ?? "");
  const [kedaluwarsa, setKedaluwarsa] = useState(f.awal?.tanggalKedaluwarsa ?? "");
  const [dicoba, setDicoba] = useState(false);
  const angka = Number(jumlah);
  const galat = {
    produk: dicoba && !produkId ? "Pilih produk." : undefined,
    jumlah: dicoba && !(angka > 0) ? "Isi jumlah lebih dari 0." : undefined,
    produksi: dicoba && !produksi ? "Tanggal produksi belum diisi." : undefined,
    kedaluwarsa: kedaluwarsa && produksi && kedaluwarsa < produksi ? "Tanggal kedaluwarsa tidak boleh sebelum tanggal produksi." : undefined,
  };
  return (
    <ModalForm
      title={f.awal ? "Ubah Catatan Hasil Produksi" : "Tambah Catatan Hasil Produksi"}
      {...f}
      onSimpan={() => {
        setDicoba(true);
        if (!produkId || !(angka > 0) || !produksi || galat.kedaluwarsa) return;
        f.onSimpan({
          id: f.awal?.id ?? buatId("hp"),
          produkId,
          jumlah: angka,
          tanggalProduksi: produksi,
          tanggalKedaluwarsa: kedaluwarsa || undefined,
          sumber: sumberPengguna(),
        });
      }}
    >
      <Field label="Nama produk" htmlFor="hp-produk" required error={galat.produk}>
        <Select id="hp-produk" options={opsiProduk} value={produkId} invalid={Boolean(galat.produk)} onValueChange={setProdukId} />
      </Field>
      <Field label="Jumlah" htmlFor="hp-jumlah" required error={galat.jumlah} hint="Dalam porsi, bungkus, atau satuan jual.">
        <Input id="hp-jumlah" type="number" min={0} step="any" inputMode="decimal" value={jumlah} invalid={Boolean(galat.jumlah)} onChange={(e) => setJumlah(e.target.value)} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Tanggal produksi" htmlFor="hp-produksi" required error={galat.produksi}>
          <DateInput id="hp-produksi" value={produksi} invalid={Boolean(galat.produksi)} onChange={(e) => setProduksi(e.target.value)} />
        </Field>
        <Field label="Tanggal kedaluwarsa" htmlFor="hp-kedaluwarsa" error={galat.kedaluwarsa}>
          <DateInput id="hp-kedaluwarsa" value={kedaluwarsa} invalid={Boolean(galat.kedaluwarsa)} onChange={(e) => setKedaluwarsa(e.target.value)} />
        </Field>
      </div>
    </ModalForm>
  );
}

function FormDistribusi({ opsiProduk, ...f }: FormProps<Distribusi> & { opsiProduk: SelectOption[] }) {
  const [tujuan, setTujuan] = useState(f.awal?.tujuan ?? "");
  const [produkId, setProdukId] = useState(f.awal?.produkId ?? "");
  const [jumlah, setJumlah] = useState(f.awal?.jumlah ? String(f.awal.jumlah) : "");
  const [tanggal, setTanggal] = useState(f.awal?.tanggal ?? "");
  const [berkas, setBerkas] = useState<Berkas | undefined>(f.awal?.berkas);
  const [dicoba, setDicoba] = useState(false);
  const galatTujuan = dicoba && !tujuan.trim() ? "Tujuan belum diisi, misalnya Dijual langsung di warung." : undefined;
  return (
    <ModalForm
      title={f.awal ? "Ubah Catatan Distribusi" : "Tambah Catatan Distribusi"}
      {...f}
      onSimpan={() => {
        setDicoba(true);
        if (!tujuan.trim()) return;
        f.onSimpan({
          id: f.awal?.id ?? buatId("ds"),
          tujuan: tujuan.trim(),
          produkId: produkId || undefined,
          jumlah: Number(jumlah) > 0 ? Number(jumlah) : undefined,
          tanggal: tanggal || undefined,
          berkas,
          sumber: sumberPengguna(),
        });
      }}
    >
      <Field label="Tujuan distribusi atau penjualan" htmlFor="ds-tujuan" required error={galatTujuan}>
        <Input id="ds-tujuan" value={tujuan} invalid={Boolean(galatTujuan)} onChange={(e) => setTujuan(e.target.value)} />
      </Field>
      <Field label="Nama produk" htmlFor="ds-produk">
        <Select id="ds-produk" options={opsiProduk} value={produkId} onValueChange={setProdukId} placeholder="Semua produk" />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Jumlah" htmlFor="ds-jumlah">
          <Input id="ds-jumlah" type="number" min={0} step="any" inputMode="decimal" value={jumlah} onChange={(e) => setJumlah(e.target.value)} />
        </Field>
        <Field label="Tanggal" htmlFor="ds-tanggal">
          <DateInput id="ds-tanggal" value={tanggal} onChange={(e) => setTanggal(e.target.value)} />
        </Field>
      </div>
      <Field label="Berkas catatan penjualan" htmlFor="ds-berkas" hint="Opsional, misalnya foto buku penjualan.">
        <FileInput id="ds-berkas" accept=".jpg,.jpeg,.png,.pdf" fileName={berkas?.nama} onChange={(x) => setBerkas(keBerkas(x))} />
      </Field>
    </ModalForm>
  );
}

// ---------- Tab ----------

type KeadaanModal =
  | { jenis: "layout"; awal?: LayoutProduksi }
  | { jenis: "penyimpanan"; awal?: CatatanPenyimpanan }
  | { jenis: "alur"; awal?: AlurProses }
  | { jenis: "hasil"; awal?: HasilProduksi }
  | { jenis: "distribusi"; awal?: Distribusi };

type KunciDaftar = "layout" | "penyimpanan" | "alurProses" | "hasilProduksi" | "distribusi";

export default function TabProses({ p, pu }: TabProps) {
  const { simpan, menyimpan } = useSimpanBagian(p.id);
  const [modal, setModal] = useState<KeadaanModal | null>(null);
  const hapus = useHapus<{ kunci: KunciDaftar; id: string; nama: string }>();
  const pr = p.proses;
  const tutup = () => setModal(null);

  const opsiPabrik = (pu?.pabrik ?? []).map((x) => ({ value: x.id, label: x.nama }));
  const opsiBahan = p.bahan.daftarBahan.map((x) => ({ value: x.id, label: x.nama }));
  const opsiProduk = p.produk.map((x) => ({ value: x.id, label: x.nama }));
  const namaPabrik = (id: string) => pu?.pabrik.find((x) => x.id === id)?.nama ?? "-";
  const namaProduk = (id?: string) => (id ? (p.produk.find((x) => x.id === id)?.nama ?? "Produk terhapus") : "Semua produk");
  const namaRef = (c: CatatanPenyimpanan) =>
    c.jenis === "bahan"
      ? (p.bahan.daftarBahan.find((x) => x.id === c.refId)?.nama ?? "Bahan terhapus")
      : namaProduk(c.refId);

  const simpanProses = (isi: BagianProses, pesan: string) => simpan({ bagian: "proses", isi }, pesan);
  const simpanItem = async <K extends KunciDaftar>(kunci: K, item: BagianProses[K][number], pesan: string) => {
    const daftar = pr[kunci] as Array<{ id: string }>;
    const baru = daftar.some((x) => x.id === item.id) ? daftar.map((x) => (x.id === item.id ? item : x)) : [...daftar, item];
    if (await simpanProses({ ...pr, [kunci]: baru }, pesan)) tutup();
  };

  const aksi = (kunci: KunciDaftar, id: string, nama: string, ubah?: () => void) => (
    <AksiBaris nama={nama} onUbah={ubah} onHapus={() => hapus.minta({ kunci, id, nama })} />
  );

  const kolomLayout: Column<LayoutProduksi>[] = [
    {
      key: "pabrik",
      header: "Nama Pabrik",
      primary: true,
      cell: (x) => (
        <DenganTanda sumber={x.sumber} bukti={x.berkas}>
          {namaPabrik(x.pabrikId)}
        </DenganTanda>
      ),
    },
    { key: "berkas", header: "Berkas Denah", cell: (x) => <BerkasLabel berkas={x.berkas} /> },
    { key: "aksi", header: "Aksi", action: true, align: "right", cell: (x) => aksi("layout", x.id, `denah ${namaPabrik(x.pabrikId)}`) },
  ];

  const kolomPenyimpanan: Column<CatatanPenyimpanan>[] = [
    { key: "nama", header: "Nama", primary: true, cell: (x) => <DenganTanda sumber={x.sumber}>{namaRef(x)}</DenganTanda> },
    { key: "jenis", header: "Jenis", cell: (x) => (x.jenis === "bahan" ? "Bahan" : "Produk") },
    { key: "jumlah", header: "Jumlah", cell: (x) => x.jumlah },
    { key: "masuk", header: "Tanggal Masuk", cell: (x) => formatTanggal(x.tanggalMasuk) },
    { key: "keluar", header: "Tanggal Keluar", cell: (x) => formatTanggal(x.tanggalKeluar) },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (x) => aksi("penyimpanan", x.id, `catatan ${namaRef(x)}`, () => setModal({ jenis: "penyimpanan", awal: x })),
    },
  ];

  const kolomHasil: Column<HasilProduksi>[] = [
    {
      key: "produk",
      header: "Nama Produk",
      primary: true,
      cell: (x) => <DenganTanda sumber={x.sumber}>{namaProduk(x.produkId)}</DenganTanda>,
    },
    { key: "jumlah", header: "Jumlah", cell: (x) => x.jumlah },
    { key: "produksi", header: "Tanggal Produksi", cell: (x) => formatTanggal(x.tanggalProduksi) },
    { key: "kedaluwarsa", header: "Tanggal Kedaluwarsa", cell: (x) => formatTanggal(x.tanggalKedaluwarsa) },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (x) => aksi("hasilProduksi", x.id, `hasil ${namaProduk(x.produkId)}`, () => setModal({ jenis: "hasil", awal: x })),
    },
  ];

  const kolomDistribusi: Column<Distribusi>[] = [
    { key: "tujuan", header: "Tujuan", primary: true, cell: (x) => <DenganTanda sumber={x.sumber}>{x.tujuan}</DenganTanda> },
    { key: "produk", header: "Produk", cell: (x) => namaProduk(x.produkId) },
    { key: "jumlah", header: "Jumlah", cell: (x) => x.jumlah ?? "-" },
    { key: "tanggal", header: "Tanggal", cell: (x) => formatTanggal(x.tanggal) },
    { key: "berkas", header: "Berkas", cell: (x) => <BerkasLabel berkas={x.berkas} /> },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (x) => aksi("distribusi", x.id, `distribusi ${x.tujuan}`, () => setModal({ jenis: "distribusi", awal: x })),
    },
  ];

  return (
    <>
      <BlokPersetujuan
        id="bebas-babi"
        judul="Pernyataan Bebas Babi"
        persetujuan={pr.pernyataanBebasBabi}
        menyimpan={menyimpan}
        onSetuju={() =>
          simpanProses(
            { ...pr, pernyataanBebasBabi: { disetujuiPada: new Date().toISOString(), sumber: sumberPengguna() } },
            "Pernyataan bebas babi disetujui",
          )
        }
        isi={
          <div className="flex flex-col gap-3">
            <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[160px_minmax(0,1fr)]">
              <dt className="text-ink-muted">Nama</dt>
              <dd>{pu?.penanggungJawab.nama ?? "-"}</dd>
              <dt className="text-ink-muted">Jabatan</dt>
              <dd>Penanggung jawab usaha</dd>
              <dt className="text-ink-muted">NIB</dt>
              <dd className="font-mono">{pu?.nib ?? "-"}</dd>
              <dt className="text-ink-muted">Usaha</dt>
              <dd>{p.namaUsaha}</dd>
            </dl>
            <p>
              Menyatakan bahwa usaha kami tidak memakai bahan, fasilitas, dan peralatan yang mengandung babi atau
              turunannya, baik untuk produk yang didaftarkan maupun produk lain yang kami buat.
            </p>
          </div>
        }
      />

      <Seksi title="Layout atau Denah Ruang Produksi" onTambah={() => setModal({ jenis: "layout" })}>
        <DataTable
          caption="Layout ruang produksi"
          columns={kolomLayout}
          rows={pr.layout}
          getRowId={(x) => x.id}
          numbered
          emptyMessage="Belum ada denah. Unggah foto atau gambar dapur produksi."
        />
      </Seksi>

      <Seksi
        title="Catatan Penyimpanan Bahan dan Produk"
        description="Catat kapan bahan dan produk masuk serta keluar dari tempat penyimpanan."
        onTambah={() => setModal({ jenis: "penyimpanan" })}
      >
        <DataTable
          caption="Catatan penyimpanan"
          columns={kolomPenyimpanan}
          rows={pr.penyimpanan}
          getRowId={(x) => x.id}
          numbered
          emptyMessage="Belum ada catatan penyimpanan."
        />
      </Seksi>

      <Seksi title="Diagram Alur Proses Produksi" onTambah={() => setModal({ jenis: "alur" })}>
        {pr.alurProses.length === 0 ? (
          <p className="text-body-sm text-ink-muted">Belum ada alur proses. Tulis langkah pembuatan produk dari awal sampai siap dijual.</p>
        ) : (
          <div className="flex flex-col gap-4">
            {pr.alurProses.map((a) => (
              <Card
                key={a.id}
                className="bg-surface md:p-4"
                title={<DenganTanda sumber={a.sumber} bukti={a.berkas}>{a.judul}</DenganTanda>}
                actions={aksi("alurProses", a.id, a.judul, () => setModal({ jenis: "alur", awal: a }))}>
                {a.langkah.length > 0 ? (
                  <ol className="flex flex-col gap-2">
                    {a.langkah.map((l, i) => (
                      <li key={i} className="flex gap-3 text-body-sm text-ink">
                        <span className="flex size-6 shrink-0 items-center justify-center rounded-pill bg-brand-tint text-caption text-brand">
                          {i + 1}
                        </span>
                        <span className="pt-0.5">{l}</span>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <BerkasLabel berkas={a.berkas} />
                )}
              </Card>
            ))}
          </div>
        )}
      </Seksi>

      <Seksi title="Catatan Hasil Produksi" onTambah={() => setModal({ jenis: "hasil" })}>
        <DataTable
          caption="Catatan hasil produksi"
          columns={kolomHasil}
          rows={pr.hasilProduksi}
          getRowId={(x) => x.id}
          numbered
          emptyMessage={p.produk.length === 0 ? "Tambahkan produk dulu di tab Bahan." : "Belum ada catatan hasil produksi."}
        />
      </Seksi>

      <Seksi title="Catatan Distribusi atau Penjualan Produk" onTambah={() => setModal({ jenis: "distribusi" })}>
        <DataTable
          caption="Catatan distribusi"
          columns={kolomDistribusi}
          rows={pr.distribusi}
          getRowId={(x) => x.id}
          numbered
          emptyMessage="Belum ada catatan distribusi. Untuk warung, cukup tulis Dijual langsung di warung."
        />
      </Seksi>

      {modal?.jenis === "layout" && (
        <FormLayout opsiPabrik={opsiPabrik} awal={modal.awal} menyimpan={menyimpan} onTutup={tutup} onSimpan={(x) => simpanItem("layout", x, "Denah tersimpan")} />
      )}
      {modal?.jenis === "penyimpanan" && (
        <FormPenyimpanan
          opsiBahan={opsiBahan}
          opsiProduk={opsiProduk}
          awal={modal.awal}
          menyimpan={menyimpan}
          onTutup={tutup}
          onSimpan={(x) => simpanItem("penyimpanan", x, "Catatan penyimpanan tersimpan")}
        />
      )}
      {modal?.jenis === "alur" && (
        <FormAlur awal={modal.awal} menyimpan={menyimpan} onTutup={tutup} onSimpan={(x) => simpanItem("alurProses", x, "Alur proses tersimpan")} />
      )}
      {modal?.jenis === "hasil" && (
        <FormHasil
          opsiProduk={opsiProduk}
          awal={modal.awal}
          menyimpan={menyimpan}
          onTutup={tutup}
          onSimpan={(x) => simpanItem("hasilProduksi", x, "Hasil produksi tersimpan")}
        />
      )}
      {modal?.jenis === "distribusi" && (
        <FormDistribusi
          opsiProduk={opsiProduk}
          awal={modal.awal}
          menyimpan={menyimpan}
          onTutup={tutup}
          onSimpan={(x) => simpanItem("distribusi", x, "Catatan distribusi tersimpan")}
        />
      )}

      <KonfirmasiHapus
        nama={hapus.target?.nama ?? "catatan"}
        open={hapus.target !== null}
        onOpenChange={(o) => !o && hapus.tutup()}
        loading={menyimpan}
        onConfirm={async () => {
          const t = hapus.target;
          if (!t) return;
          const daftar = pr[t.kunci] as Array<{ id: string }>;
          if (await simpanProses({ ...pr, [t.kunci]: daftar.filter((x) => x.id !== t.id) }, "Catatan dihapus")) hapus.tutup();
        }}
      />
    </>
  );
}
