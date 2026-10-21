import { useState } from "react";
import { IconChecklist, IconInfoCircle, IconPencil } from "@tabler/icons-react";
import type { Bahan, BagianBahan, Berkas, CatatanPembelian, PemeriksaanBahan, Produk } from "../../api/index.ts";
import {
  Button,
  Checkbox,
  DataTable,
  DateInput,
  Field,
  FileInput,
  IconButton,
  Input,
  Modal,
  SegmentedToggle,
  Select,
  StatusBadge,
} from "../../components/ui/index.ts";
import type { Column } from "../../components/ui/index.ts";
import { formatTanggal } from "../../lib/format.ts";
import {
  labelJenisBahan,
  opsiJenisBahan,
  opsiKlasifikasi,
  opsiRincian,
  opsiSatuan,
  opsiTipeBahan,
} from "../../lib/opsi.ts";
import { statusBukti, statusKonfirmasi } from "../../lib/status.ts";
import {
  AksiBaris,
  BerkasLabel,
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

// ---------- Aturan bukti untuk isian manual ----------

function buktiManual(tipe: Bahan["tipe"], noSertifikat: string): Pick<Bahan, "bukti" | "alasanBukti"> {
  if (tipe === "tidak-bersertifikat") return { bukti: "ada", alasanBukti: "Bahan tidak bersertifikat, dicatat oleh pelaku usaha." };
  return noSertifikat
    ? { bukti: "ada", alasanBukti: "Nomor sertifikat diisi oleh pelaku usaha." }
    : { bukti: "kurang", alasanBukti: "Nomor sertifikat belum diisi. Lihat nomornya di kemasan lalu isi di sini." };
}

// ---------- Modal bahan ----------

function FormBahan({
  awal,
  onTutup,
  onSimpan,
  menyimpan,
}: {
  awal?: Bahan;
  onTutup: () => void;
  onSimpan: (b: Bahan) => void;
  menyimpan: boolean;
}) {
  const [mode, setMode] = useState<"unggah" | "manual">("manual");
  const [tipe, setTipe] = useState<Bahan["tipe"]>(awal?.tipe ?? "bersertifikat");
  const [jenis, setJenis] = useState<Bahan["jenis"]>(awal?.jenis ?? "bahan");
  const [nama, setNama] = useState(awal?.nama ?? "");
  const [produsen, setProdusen] = useState(awal?.produsen ?? "");
  const [noSertifikat, setNoSertifikat] = useState(awal?.noSertifikat ?? "");
  const [dicoba, setDicoba] = useState(false);
  const namaKosong = dicoba && !nama.trim();

  const simpan = () => {
    setDicoba(true);
    if (!nama.trim()) return;
    const no = tipe === "bersertifikat" ? noSertifikat.trim() : "";
    onSimpan({
      ...awal,
      id: awal?.id ?? buatId("b"),
      tipe,
      jenis,
      nama: nama.trim(),
      produsen: produsen.trim() || undefined,
      noSertifikat: no || undefined,
      ...buktiManual(tipe, no),
      konfirmasi: "terkonfirmasi",
      sumber: sumberPengguna(),
    });
  };

  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title={awal ? "Ubah Data Bahan" : "Tambah Data Bahan"}
      footer={
        <>
          <Button variant="secondary" onClick={onTutup}>
            Batal
          </Button>
          {mode === "manual" && (
            <Button onClick={simpan} loading={menyimpan}>
              Simpan
            </Button>
          )}
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {!awal && (
          <SegmentedToggle
            label="Cara menambah bahan"
            className="self-center"
            value={mode}
            onValueChange={setMode}
            options={[
              { value: "unggah", label: "Unggah File" },
              { value: "manual", label: "Tambah Manual" },
            ]}
          />
        )}
        {mode === "unggah" ? (
          <div className="flex gap-3 rounded-md bg-brand-tint p-4 text-body-sm text-ink">
            <IconInfoCircle size={20} stroke={1.75} className="shrink-0 text-brand" aria-hidden="true" />
            <p>
              Impor dari berkas XLSX belum tersedia di versi demo. Cara tercepat: kirim foto label kemasan ke WhatsApp
              KawalHalal, bahan akan ditambahkan ke tabel ini secara otomatis.
            </p>
          </div>
        ) : (
          <>
            {awal?.konfirmasi === "perlu-konfirmasi" && (
              <p className="rounded-md bg-status-warn-bg p-3 text-body-sm text-status-warn">
                {awal.alasanBukti ?? "Bahan ini perlu diperiksa."} Menyimpan formulir ini menandai bahan sebagai terkonfirmasi.
              </p>
            )}
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Tipe bahan" htmlFor="b-tipe" required>
                <Select id="b-tipe" options={opsiTipeBahan} value={tipe} onValueChange={(v) => setTipe(v as Bahan["tipe"])} />
              </Field>
              <Field label="Jenis" htmlFor="b-jenis" required>
                <Select id="b-jenis" options={opsiJenisBahan} value={jenis} onValueChange={(v) => setJenis(v as Bahan["jenis"])} />
              </Field>
            </div>
            <Field label="Nama bahan" htmlFor="b-nama" required error={namaKosong ? "Nama bahan belum diisi." : undefined}>
              <Input id="b-nama" value={nama} invalid={namaKosong} placeholder="Contoh: Kecap manis" onChange={(e) => setNama(e.target.value)} />
            </Field>
            <Field label="Produsen atau merek" htmlFor="b-produsen" hint="Tertera di kemasan atau nota pembelian.">
              <Input id="b-produsen" value={produsen} onChange={(e) => setProdusen(e.target.value)} />
            </Field>
            {tipe === "bersertifikat" && (
              <Field
                label="Nomor sertifikat halal"
                htmlFor="b-sertifikat"
                hint="Biasanya diawali ID, tertera di dekat logo halal pada kemasan. Kosongkan bila belum tahu."
              >
                <Input
                  id="b-sertifikat"
                  className="font-mono"
                  value={noSertifikat}
                  onChange={(e) => setNoSertifikat(e.target.value.toUpperCase())}
                />
              </Field>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

// ---------- Modal produk ----------

function FormProduk({
  awal,
  merekBawaan,
  onTutup,
  onSimpan,
  menyimpan,
}: {
  awal?: Produk;
  merekBawaan: string;
  onTutup: () => void;
  onSimpan: (p: Produk) => void;
  menyimpan: boolean;
}) {
  const [klasifikasi, setKlasifikasi] = useState(awal?.klasifikasi ?? "");
  const [rincian, setRincian] = useState(awal?.rincian ?? "");
  const [nama, setNama] = useState(awal?.nama ?? "");
  const [merek, setMerek] = useState(awal?.merek ?? merekBawaan);
  const [foto, setFoto] = useState<Berkas | undefined>(awal?.foto);
  const [dicoba, setDicoba] = useState(false);
  const galat = {
    klasifikasi: dicoba && !klasifikasi ? "Pilih klasifikasi produk." : undefined,
    rincian: dicoba && !rincian ? "Pilih rincian produk." : undefined,
    nama: dicoba && !nama.trim() ? "Nama produk belum diisi." : undefined,
  };

  const simpan = () => {
    setDicoba(true);
    if (!klasifikasi || !rincian || !nama.trim()) return;
    onSimpan({
      id: awal?.id ?? buatId("pr"),
      klasifikasi,
      rincian,
      nama: nama.trim(),
      merek: merek.trim() || undefined,
      foto,
      bahanIds: awal?.bahanIds ?? [],
      sumber: sumberPengguna(),
    });
  };

  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title={awal ? "Ubah Nama Produk" : "Tambah Nama Produk"}
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
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Klasifikasi produk" htmlFor="pr-klasifikasi" required error={galat.klasifikasi}>
            <Select
              id="pr-klasifikasi"
              options={opsiKlasifikasi}
              value={klasifikasi}
              invalid={Boolean(galat.klasifikasi)}
              onValueChange={(v) => {
                setKlasifikasi(v);
                setRincian("");
              }}
            />
          </Field>
          <Field label="Rincian produk" htmlFor="pr-rincian" required error={galat.rincian}>
            <Select
              id="pr-rincian"
              options={opsiRincian(klasifikasi)}
              value={rincian}
              invalid={Boolean(galat.rincian)}
              disabled={!klasifikasi}
              placeholder={klasifikasi ? "Pilih rincian" : "Pilih klasifikasi dulu"}
              onValueChange={setRincian}
            />
          </Field>
        </div>
        <Field label="Nama produk" htmlFor="pr-nama" required error={galat.nama}>
          <Input id="pr-nama" value={nama} invalid={Boolean(galat.nama)} maxLength={200} showCount onChange={(e) => setNama(e.target.value)} />
        </Field>
        <Field label="Merek" htmlFor="pr-merek">
          <Input id="pr-merek" value={merek} maxLength={200} showCount onChange={(e) => setMerek(e.target.value)} />
        </Field>
        <Field label="Foto produk" htmlFor="pr-foto" hint="Format JPG atau PNG.">
          <FileInput id="pr-foto" accept=".jpg,.jpeg,.png" fileName={foto?.nama} onChange={(f) => setFoto(keBerkas(f))} />
        </Field>
      </div>
    </Modal>
  );
}

function FormInputBahan({
  produk,
  semuaBahan,
  onTutup,
  onSimpan,
  menyimpan,
}: {
  produk: Produk;
  semuaBahan: Bahan[];
  onTutup: () => void;
  onSimpan: (bahanIds: string[]) => void;
  menyimpan: boolean;
}) {
  const [dipilih, setDipilih] = useState<string[]>(produk.bahanIds);
  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title="Input Bahan"
      description={`Pilih bahan yang dipakai untuk ${produk.nama}.`}
      footer={
        <>
          <Button variant="secondary" onClick={onTutup}>
            Batal
          </Button>
          <Button onClick={() => onSimpan(dipilih)} loading={menyimpan}>
            Simpan ({dipilih.length} bahan)
          </Button>
        </>
      }
    >
      {semuaBahan.length === 0 ? (
        <p className="text-body-sm text-ink-muted">Belum ada bahan. Tambahkan bahan di tabel Daftar Nama Bahan dan Kemasan.</p>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => setDipilih(semuaBahan.map((b) => b.id))}>
              Pilih semua
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setDipilih([])}>
              Kosongkan
            </Button>
          </div>
          {semuaBahan.map((b) => (
            <Checkbox
              key={b.id}
              id={`ib-${b.id}`}
              label={`${b.nama} (${labelJenisBahan[b.jenis]})`}
              checked={dipilih.includes(b.id)}
              onCheckedChange={(aktif) => setDipilih((d) => (aktif ? [...d, b.id] : d.filter((x) => x !== b.id)))}
            />
          ))}
        </div>
      )}
    </Modal>
  );
}

// ---------- Modal catatan per bahan ----------

function FormPembelian({
  bahan,
  awal,
  onTutup,
  onSimpan,
  menyimpan,
}: {
  bahan: Bahan;
  awal?: CatatanPembelian;
  onTutup: () => void;
  onSimpan: (c: CatatanPembelian) => void;
  menyimpan: boolean;
}) {
  const [jumlah, setJumlah] = useState(awal ? String(awal.jumlah) : "");
  const [satuan, setSatuan] = useState(awal?.satuan ?? "kg");
  const [tanggal, setTanggal] = useState(awal?.tanggal ?? "");
  const [berkas, setBerkas] = useState<Berkas | undefined>(awal?.berkas);
  const [dicoba, setDicoba] = useState(false);
  const angka = Number(jumlah);
  const galatJumlah = dicoba && !(angka > 0) ? "Isi jumlah lebih dari 0." : undefined;
  const galatTanggal = dicoba && !tanggal ? "Tanggal pembelian belum diisi." : undefined;

  const simpan = () => {
    setDicoba(true);
    if (!(angka > 0) || !tanggal) return;
    onSimpan({ id: awal?.id ?? buatId("cp"), bahanId: bahan.id, jumlah: angka, satuan, tanggal, berkas, sumber: sumberPengguna() });
  };

  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title="Catatan Pembelian Bahan"
      description={bahan.nama}
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
        <div className="grid grid-cols-[minmax(0,1fr)_120px] gap-3">
          <Field label="Jumlah" htmlFor="cp-jumlah" required error={galatJumlah}>
            <Input id="cp-jumlah" type="number" min={0} step="any" inputMode="decimal" value={jumlah} invalid={Boolean(galatJumlah)} onChange={(e) => setJumlah(e.target.value)} />
          </Field>
          <Field label="Satuan" htmlFor="cp-satuan" required>
            <Select id="cp-satuan" options={opsiSatuan} value={satuan} onValueChange={setSatuan} />
          </Field>
        </div>
        <Field label="Tanggal pembelian" htmlFor="cp-tanggal" required error={galatTanggal}>
          <DateInput id="cp-tanggal" value={tanggal} invalid={Boolean(galatTanggal)} onChange={(e) => setTanggal(e.target.value)} />
        </Field>
        <Field label="Foto atau berkas nota" htmlFor="cp-berkas" hint="Format JPG, PNG, atau PDF.">
          <FileInput id="cp-berkas" accept=".jpg,.jpeg,.png,.pdf" fileName={berkas?.nama} onChange={(f) => setBerkas(keBerkas(f))} />
        </Field>
      </div>
    </Modal>
  );
}

function FormPemeriksaan({
  bahan,
  awal,
  lokasiBawaan,
  onTutup,
  onSimpan,
  menyimpan,
}: {
  bahan: Bahan;
  awal?: PemeriksaanBahan;
  lokasiBawaan: string;
  onTutup: () => void;
  onSimpan: (c: PemeriksaanBahan) => void;
  menyimpan: boolean;
}) {
  const [lokasi, setLokasi] = useState(awal?.lokasi ?? lokasiBawaan);
  const [tanggal, setTanggal] = useState(awal?.tanggal ?? "");
  const [berkas, setBerkas] = useState<Berkas | undefined>(awal?.berkas);
  const [dicoba, setDicoba] = useState(false);
  const galatLokasi = dicoba && !lokasi.trim() ? "Lokasi pemeriksaan belum diisi." : undefined;
  const galatTanggal = dicoba && !tanggal ? "Tanggal pemeriksaan belum diisi." : undefined;

  const simpan = () => {
    setDicoba(true);
    if (!lokasi.trim() || !tanggal) return;
    onSimpan({ id: awal?.id ?? buatId("pm"), bahanId: bahan.id, lokasi: lokasi.trim(), tanggal, berkas, sumber: sumberPengguna() });
  };

  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title="Formulir Pemeriksaan Bahan"
      description={bahan.nama}
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
        <Field label="Lokasi pemeriksaan" htmlFor="pm-lokasi" required error={galatLokasi}>
          <Input id="pm-lokasi" value={lokasi} invalid={Boolean(galatLokasi)} onChange={(e) => setLokasi(e.target.value)} />
        </Field>
        <Field label="Tanggal pemeriksaan" htmlFor="pm-tanggal" required error={galatTanggal}>
          <DateInput id="pm-tanggal" value={tanggal} invalid={Boolean(galatTanggal)} onChange={(e) => setTanggal(e.target.value)} />
        </Field>
        <Field label="Berkas pemeriksaan" htmlFor="pm-berkas" hint="Opsional. Format JPG, PNG, atau PDF.">
          <FileInput id="pm-berkas" accept=".jpg,.jpeg,.png,.pdf" fileName={berkas?.nama} onChange={(f) => setBerkas(keBerkas(f))} />
        </Field>
      </div>
    </Modal>
  );
}

// ---------- Tab ----------

type KeadaanModal =
  | { jenis: "bahan"; awal?: Bahan }
  | { jenis: "produk"; awal?: Produk }
  | { jenis: "input-bahan"; produk: Produk }
  | { jenis: "pembelian"; bahan: Bahan; awal?: CatatanPembelian }
  | { jenis: "pemeriksaan"; bahan: Bahan; awal?: PemeriksaanBahan };

function StatusCatatan({ ada }: { ada: boolean }) {
  return ada ? <StatusBadge tone="ok">Tercatat</StatusBadge> : <StatusBadge tone="warn">Belum dicatat</StatusBadge>;
}

export default function TabBahan({ p, pu }: TabProps) {
  const { simpan, menyimpan } = useSimpanBagian(p.id);
  const [modal, setModal] = useState<KeadaanModal | null>(null);
  const hapusBahan = useHapus<Bahan>();
  const hapusProduk = useHapus<Produk>();
  const b = p.bahan;
  const tutup = () => setModal(null);

  const simpanBahan = (isi: BagianBahan, pesan: string) => simpan({ bagian: "bahan", isi }, pesan);
  const simpanProduk = (isi: Produk[], pesan: string) => simpan({ bagian: "produk", isi }, pesan);
  const ganti = <T extends { id: string }>(daftar: T[], item: T) =>
    daftar.some((x) => x.id === item.id) ? daftar.map((x) => (x.id === item.id ? item : x)) : [...daftar, item];

  // ----- Kolom -----

  const kolomBahan: Column<Bahan>[] = [
    {
      key: "nama",
      header: "Nama Bahan",
      primary: true,
      cell: (x) => (
        <DenganTanda sumber={x.sumber} bukti={x.fotoSumber}>
          {x.nama}
        </DenganTanda>
      ),
    },
    { key: "jenis", header: "Jenis", cell: (x) => labelJenisBahan[x.jenis] },
    { key: "produsen", header: "Produsen", cell: (x) => x.produsen ?? "-" },
    {
      key: "sertifikat",
      header: "No. Sertifikat Halal",
      cell: (x) => (x.noSertifikat ? <span className="font-mono text-mono">{x.noSertifikat}</span> : "-"),
    },
    {
      key: "bukti",
      header: "Bukti",
      cell: (x) => (
        <div className="flex flex-col items-start gap-1">
          <StatusBadge tone={statusBukti[x.bukti].tone}>{statusBukti[x.bukti].label}</StatusBadge>
          {x.konfirmasi === "perlu-konfirmasi" && (
            <StatusBadge tone={statusKonfirmasi[x.konfirmasi].tone}>{statusKonfirmasi[x.konfirmasi].label}</StatusBadge>
          )}
          {x.bukti !== "ada" && x.alasanBukti && <span className="text-caption text-ink-muted">{x.alasanBukti}</span>}
          {x.fotoSumber && (
            <span className="text-caption">
              <BerkasLabel berkas={x.fotoSumber} />
            </span>
          )}
        </div>
      ),
    },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (x) => (
        <AksiBaris nama={x.nama} onUbah={() => setModal({ jenis: "bahan", awal: x })} onHapus={() => hapusBahan.minta(x)} />
      ),
    },
  ];

  const kolomProduk: Column<Produk>[] = [
    {
      key: "nama",
      header: "Nama Produk",
      primary: true,
      cell: (x) => (
        <DenganTanda sumber={x.sumber} bukti={x.foto}>
          {x.nama}
        </DenganTanda>
      ),
    },
    { key: "rincian", header: "Klasifikasi", cell: (x) => `${x.klasifikasi} · ${x.rincian}` },
    { key: "foto", header: "Foto Produk", cell: (x) => <BerkasLabel berkas={x.foto} /> },
    {
      key: "jumlah",
      header: "Jumlah Bahan",
      cell: (x) => (x.bahanIds.length > 0 ? `${x.bahanIds.length} bahan` : <StatusBadge tone="warn">Belum diisi</StatusBadge>),
    },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (x) => (
        <div className="flex justify-end gap-1">
          <IconButton
            label={`Input bahan ${x.nama}`}
            tone="brand"
            icon={<IconChecklist size={18} stroke={1.75} />}
            onClick={() => setModal({ jenis: "input-bahan", produk: x })}
          />
          <AksiBaris nama={x.nama} onUbah={() => setModal({ jenis: "produk", awal: x })} onHapus={() => hapusProduk.minta(x)} />
        </div>
      ),
    },
  ];

  const kolomPembelian: Column<Bahan>[] = [
    { key: "nama", header: "Nama Bahan", primary: true, cell: (x) => x.nama },
    {
      key: "jumlah",
      header: "Jumlah",
      cell: (x) => {
        const c = b.catatanPembelian.find((c) => c.bahanId === x.id);
        return c ? (
          <DenganTanda sumber={c.sumber} bukti={c.berkas}>
            {c.jumlah} {c.satuan}
          </DenganTanda>
        ) : (
          "-"
        );
      },
    },
    { key: "tanggal", header: "Tanggal Pembelian", cell: (x) => formatTanggal(b.catatanPembelian.find((c) => c.bahanId === x.id)?.tanggal) },
    { key: "berkas", header: "Nota", cell: (x) => <BerkasLabel berkas={b.catatanPembelian.find((c) => c.bahanId === x.id)?.berkas} /> },
    { key: "status", header: "Status", cell: (x) => <StatusCatatan ada={b.catatanPembelian.some((c) => c.bahanId === x.id)} /> },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (x) => (
        <IconButton
          label={`Ubah catatan pembelian ${x.nama}`}
          tone="brand"
          icon={<IconPencil size={18} stroke={1.75} />}
          onClick={() => setModal({ jenis: "pembelian", bahan: x, awal: b.catatanPembelian.find((c) => c.bahanId === x.id) })}
        />
      ),
    },
  ];

  const kolomPemeriksaan: Column<Bahan>[] = [
    { key: "nama", header: "Nama Bahan", primary: true, cell: (x) => x.nama },
    {
      key: "lokasi",
      header: "Lokasi",
      cell: (x) => {
        const c = b.pemeriksaan.find((c) => c.bahanId === x.id);
        return c ? <DenganTanda sumber={c.sumber}>{c.lokasi}</DenganTanda> : "-";
      },
    },
    { key: "tanggal", header: "Tanggal Pemeriksaan", cell: (x) => formatTanggal(b.pemeriksaan.find((c) => c.bahanId === x.id)?.tanggal) },
    { key: "berkas", header: "Berkas", cell: (x) => <BerkasLabel berkas={b.pemeriksaan.find((c) => c.bahanId === x.id)?.berkas} /> },
    { key: "status", header: "Status", cell: (x) => <StatusCatatan ada={b.pemeriksaan.some((c) => c.bahanId === x.id)} /> },
    {
      key: "aksi",
      header: "Aksi",
      action: true,
      align: "right",
      cell: (x) => (
        <IconButton
          label={`Ubah pemeriksaan ${x.nama}`}
          tone="brand"
          icon={<IconPencil size={18} stroke={1.75} />}
          onClick={() => setModal({ jenis: "pemeriksaan", bahan: x, awal: b.pemeriksaan.find((c) => c.bahanId === x.id) })}
        />
      ),
    },
  ];

  const belumBeli = b.daftarBahan.filter((x) => !b.catatanPembelian.some((c) => c.bahanId === x.id)).length;
  const belumPeriksa = b.daftarBahan.filter((x) => !b.pemeriksaan.some((c) => c.bahanId === x.id)).length;

  return (
    <>
      <Seksi
        title="Daftar Nama Bahan dan Kemasan"
        description="Semua bahan, kemasan, dan bahan pembersih yang dipakai. Status bukti menunjukkan kelengkapan dokumen, bukan penetapan halal."
        onTambah={() => setModal({ jenis: "bahan" })}
      >
        <DataTable
          caption="Daftar nama bahan dan kemasan"
          columns={kolomBahan}
          rows={b.daftarBahan}
          getRowId={(x) => x.id}
          numbered
          emptyMessage="Belum ada bahan. Tambahkan manual, atau kirim foto label lewat WhatsApp KawalHalal."
        />
      </Seksi>

      <Seksi
        title="Daftar Nama Produk"
        description="Setelah menambah produk, pilih bahan yang dipakai lewat tombol Input Bahan di kolom Aksi."
        onTambah={() => setModal({ jenis: "produk" })}
      >
        <DataTable
          caption="Daftar nama produk"
          columns={kolomProduk}
          rows={p.produk}
          getRowId={(x) => x.id}
          numbered
          emptyMessage="Belum ada produk. Tambahkan produk yang ingin disertifikasi."
        />
      </Seksi>

      <Seksi
        title="Catatan Pembelian Bahan"
        description={
          belumBeli > 0 ? `${belumBeli} bahan belum punya catatan pembelian.` : "Setiap bahan sudah punya catatan pembelian."
        }
      >
        <DataTable
          caption="Catatan pembelian bahan"
          columns={kolomPembelian}
          rows={b.daftarBahan}
          getRowId={(x) => x.id}
          numbered
          emptyMessage="Tambahkan bahan dulu di tabel Daftar Nama Bahan dan Kemasan."
        />
      </Seksi>

      <Seksi
        title="Formulir Pemeriksaan Bahan"
        description={
          belumPeriksa > 0 ? `${belumPeriksa} bahan belum diperiksa saat diterima.` : "Setiap bahan sudah dicatat pemeriksaannya."
        }
      >
        <DataTable
          caption="Formulir pemeriksaan bahan"
          columns={kolomPemeriksaan}
          rows={b.daftarBahan}
          getRowId={(x) => x.id}
          numbered
          emptyMessage="Tambahkan bahan dulu di tabel Daftar Nama Bahan dan Kemasan."
        />
      </Seksi>

      {modal?.jenis === "bahan" && (
        <FormBahan
          awal={modal.awal}
          menyimpan={menyimpan}
          onTutup={tutup}
          onSimpan={async (x) => {
            if (await simpanBahan({ ...b, daftarBahan: ganti(b.daftarBahan, x) }, `${x.nama} tersimpan`)) tutup();
          }}
        />
      )}
      {modal?.jenis === "produk" && (
        <FormProduk
          awal={modal.awal}
          merekBawaan={p.data.merek}
          menyimpan={menyimpan}
          onTutup={tutup}
          onSimpan={async (x) => {
            if (await simpanProduk(ganti(p.produk, x), `${x.nama} tersimpan`)) tutup();
          }}
        />
      )}
      {modal?.jenis === "input-bahan" && (
        <FormInputBahan
          produk={modal.produk}
          semuaBahan={b.daftarBahan}
          menyimpan={menyimpan}
          onTutup={tutup}
          onSimpan={async (bahanIds) => {
            const pr = modal.produk;
            if (await simpanProduk(ganti(p.produk, { ...pr, bahanIds }), `Bahan ${pr.nama} tersimpan`)) tutup();
          }}
        />
      )}
      {modal?.jenis === "pembelian" && (
        <FormPembelian
          bahan={modal.bahan}
          awal={modal.awal}
          menyimpan={menyimpan}
          onTutup={tutup}
          onSimpan={async (c) => {
            if (await simpanBahan({ ...b, catatanPembelian: ganti(b.catatanPembelian, c) }, "Catatan pembelian tersimpan")) tutup();
          }}
        />
      )}
      {modal?.jenis === "pemeriksaan" && (
        <FormPemeriksaan
          bahan={modal.bahan}
          awal={modal.awal}
          lokasiBawaan={pu?.pabrik.find((x) => p.data.pabrikIds.includes(x.id))?.nama ?? pu?.pabrik[0]?.nama ?? ""}
          menyimpan={menyimpan}
          onTutup={tutup}
          onSimpan={async (c) => {
            if (await simpanBahan({ ...b, pemeriksaan: ganti(b.pemeriksaan, c) }, "Pemeriksaan bahan tersimpan")) tutup();
          }}
        />
      )}

      <KonfirmasiHapus
        nama={hapusBahan.target?.nama ?? "bahan"}
        open={hapusBahan.target !== null}
        onOpenChange={(o) => !o && hapusBahan.tutup()}
        loading={menyimpan}
        catatan="Bahan ini juga dihapus dari catatan pembelian, pemeriksaan, dan daftar bahan setiap produk."
        onConfirm={async () => {
          const id = hapusBahan.target?.id;
          if (!id) return;
          const ok = await simpanBahan(
            {
              daftarBahan: b.daftarBahan.filter((x) => x.id !== id),
              catatanPembelian: b.catatanPembelian.filter((x) => x.bahanId !== id),
              pemeriksaan: b.pemeriksaan.filter((x) => x.bahanId !== id),
            },
            "Bahan dihapus",
          );
          if (ok && p.produk.some((x) => x.bahanIds.includes(id))) {
            await simpan({ bagian: "produk", isi: p.produk.map((x) => ({ ...x, bahanIds: x.bahanIds.filter((y) => y !== id) })) }, "Daftar bahan produk diperbarui");
          }
          hapusBahan.tutup();
        }}
      />
      <KonfirmasiHapus
        nama={hapusProduk.target?.nama ?? "produk"}
        open={hapusProduk.target !== null}
        onOpenChange={(o) => !o && hapusProduk.tutup()}
        loading={menyimpan}
        catatan="Produk ini juga dihapus dari pemetaan produk dan pabrik."
        onConfirm={async () => {
          const id = hapusProduk.target?.id;
          if (!id) return;
          const ok = await simpanProduk(p.produk.filter((x) => x.id !== id), "Produk dihapus");
          if (ok && p.pemetaan.some((x) => x.produkId === id)) {
            await simpan({ bagian: "pemetaan", isi: p.pemetaan.filter((x) => x.produkId !== id) }, "Pemetaan diperbarui");
          }
          hapusProduk.tutup();
        }}
      />
    </>
  );
}
