import { useState } from "react";
import type { ReactNode } from "react";
import { IconPencil } from "@tabler/icons-react";
import { usePelakuUsaha, useUbahPelakuUsaha } from "../../api/index.ts";
import type { AspekLegal, Outlet, Pabrik, PelakuUsaha as DataPelakuUsaha, PenyeliaHalal } from "../../api/index.ts";
import { PageHeader } from "../../components/layout/PageHeader.tsx";
import {
  AksiBaris,
  BerkasLabel,
  Button,
  Card,
  DataTable,
  KonfirmasiHapus,
  Seksi,
  buatId,
  useHapus,
  useToast,
} from "../../components/ui/index.ts";
import type { Column } from "../../components/ui/index.ts";
import { formatTanggal } from "../../lib/format.ts";
import { FormEntitas } from "./FormEntitas.tsx";
import type { Isian } from "./FormEntitas.tsx";

// ---------- Konfigurasi isian ----------

const opsiSkala = ["mikro", "kecil", "menengah", "besar"].map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }));
const labelSkala = Object.fromEntries(opsiSkala.map((o) => [o.value, o.label]));
const opsiStatusPabrik = [
  { value: "milik-sendiri", label: "Milik sendiri" },
  { value: "sewa", label: "Sewa" },
  { value: "maklon", label: "Maklon" },
];
const labelStatusPabrik = Object.fromEntries(opsiStatusPabrik.map((o) => [o.value, o.label]));
const opsiJenisLegal = ["NIB", "NPWP", "IUMK", "SIUP", "Lainnya"].map((j) => ({ value: j, label: j }));
const opsiAgama = ["Islam", "Kristen", "Katolik", "Hindu", "Buddha", "Konghucu"].map((a) => ({ value: a, label: a }));

const polaNib = { regex: /^\d{13}$/, pesan: "NIB terdiri dari 13 angka. Lihat di dokumen OSS Anda." };
const polaKodePos = { regex: /^\d{5}$/, pesan: "Kode pos terdiri dari 5 angka." };

const isianAlamat: Isian[] = [
  { kunci: "alamat", label: "Alamat", wajib: true, penuh: true },
  { kunci: "provinsi", label: "Provinsi", wajib: true },
  { kunci: "kabKota", label: "Kabupaten/Kota", wajib: true },
  { kunci: "kodePos", label: "Kode pos", wajib: true, inputMode: "numeric", pola: polaKodePos },
];

const isianProfil: Isian[] = [
  { kunci: "namaUsaha", label: "Nama usaha", wajib: true, penuh: true, hint: "Nama ini yang tercetak di sertifikat." },
  { kunci: "nib", label: "NIB", wajib: true, mono: true, inputMode: "numeric", pola: polaNib },
  { kunci: "skala", label: "Skala usaha", jenis: "pilihan", opsi: opsiSkala, wajib: true },
  ...isianAlamat,
];

const isianPj: Isian[] = [
  { kunci: "nama", label: "Nama", wajib: true, penuh: true },
  {
    kunci: "noHp",
    label: "Nomor HP",
    wajib: true,
    inputMode: "tel",
    pola: { regex: /^0\d{8,13}$/, pesan: "Nomor HP diawali 0 dan berisi 9 sampai 14 angka." },
  },
  {
    kunci: "email",
    label: "Email",
    wajib: true,
    inputMode: "email",
    pola: { regex: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, pesan: "Format email belum benar, contoh nama@contoh.com." },
  },
];

const isianLegal: Isian[] = [
  { kunci: "jenis", label: "Jenis dokumen", jenis: "pilihan", opsi: opsiJenisLegal, wajib: true },
  { kunci: "nomor", label: "Nomor dokumen", wajib: true, mono: true },
  { kunci: "tanggal", label: "Tanggal dokumen", jenis: "tanggal", wajib: true },
  { kunci: "masaBerlaku", label: "Masa berlaku", jenis: "tanggal", hint: "Kosongkan bila berlaku seterusnya." },
  { kunci: "instansiPenerbit", label: "Instansi penerbit", wajib: true, penuh: true },
];

const isianPabrik: Isian[] = [
  { kunci: "nama", label: "Nama pabrik atau dapur", wajib: true },
  { kunci: "status", label: "Status pabrik", jenis: "pilihan", opsi: opsiStatusPabrik, wajib: true },
  ...isianAlamat,
];

const isianOutlet: Isian[] = [{ kunci: "nama", label: "Nama outlet", wajib: true, penuh: true }, ...isianAlamat];

const isianPenyelia: Isian[] = [
  { kunci: "nama", label: "Nama", wajib: true },
  { kunci: "agama", label: "Agama", jenis: "pilihan", opsi: opsiAgama, wajib: true },
  {
    kunci: "noKtp",
    label: "Nomor KTP",
    wajib: true,
    mono: true,
    inputMode: "numeric",
    pola: { regex: /^\d{16}$/, pesan: "Nomor KTP terdiri dari 16 angka." },
  },
  { kunci: "berkasKtp", label: "Foto KTP", jenis: "berkas" },
  { kunci: "noSertifikat", label: "Nomor sertifikat penyelia", hint: "Wajib untuk usaha menengah dan besar." },
  { kunci: "tanggalSertifikat", label: "Tanggal sertifikat", jenis: "tanggal" },
  { kunci: "noSk", label: "Nomor SK penetapan", hint: "SK dari pimpinan usaha yang menunjuk penyelia halal." },
  { kunci: "tanggalSk", label: "Tanggal SK", jenis: "tanggal" },
];

// ---------- Halaman ----------

type KunciDaftar = "aspekLegal" | "pabrik" | "outlet" | "penyeliaHalal";

interface ConfigDaftar {
  judul: string;
  isian: Isian[];
  awalan: string;
}

const configDaftar: Record<KunciDaftar, ConfigDaftar> = {
  aspekLegal: { judul: "Aspek Legal", isian: isianLegal, awalan: "al" },
  pabrik: { judul: "Pabrik", isian: isianPabrik, awalan: "pb" },
  outlet: { judul: "Outlet", isian: isianOutlet, awalan: "ot" },
  penyeliaHalal: { judul: "Penyelia Halal", isian: isianPenyelia, awalan: "py" },
};

type KeadaanModal =
  | { jenis: "profil" }
  | { jenis: "pj" }
  | { jenis: "daftar"; kunci: KunciDaftar; awal?: { id: string } };

function Rincian({ items }: { items: Array<[string, ReactNode]> }) {
  return (
    <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
      {items.map(([dt, dd]) => (
        <div key={dt} className="min-w-0">
          <dt className="text-caption text-ink-muted">{dt}</dt>
          <dd className="break-words text-body-sm text-ink">{dd || "-"}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function PelakuUsaha() {
  const q = usePelakuUsaha();
  const ubah = useUbahPelakuUsaha();
  const toast = useToast();
  const [modal, setModal] = useState<KeadaanModal | null>(null);
  const hapus = useHapus<{ kunci: KunciDaftar; id: string; nama: string }>();

  if (q.isPending) return <div className="h-96 animate-pulse rounded-lg bg-line" aria-busy="true" aria-label="Memuat data pelaku usaha" />;
  if (q.isError) {
    return (
      <>
        <PageHeader title="Pelaku Usaha" />
        <Card>
          <p role="alert" className="text-body text-ink-muted">
            {q.error.message}
          </p>
          <Button variant="secondary" className="mt-4" onClick={() => q.refetch()}>
            Coba lagi
          </Button>
        </Card>
      </>
    );
  }

  const pu = q.data;
  const tutup = () => setModal(null);

  const simpan = async (baru: DataPelakuUsaha, pesan: string) => {
    try {
      await ubah.mutateAsync(baru);
      toast({ title: pesan });
      tutup();
      return true;
    } catch (e) {
      toast({ tone: "risk", title: "Perubahan belum tersimpan", description: (e as Error).message });
      return false;
    }
  };

  const simpanItem = (kunci: KunciDaftar, item: { id: string; nama?: string }) => {
    const daftar = pu[kunci] as Array<{ id: string }>;
    const ada = daftar.some((x) => x.id === item.id);
    const baru = ada ? daftar.map((x) => (x.id === item.id ? item : x)) : [...daftar, item];
    return simpan({ ...pu, [kunci]: baru }, `${configDaftar[kunci].judul} tersimpan`);
  };

  const aksi = (kunci: KunciDaftar, item: { id: string }, nama: string) => (
    <AksiBaris
      nama={nama}
      onUbah={() => setModal({ jenis: "daftar", kunci, awal: item })}
      onHapus={() => hapus.minta({ kunci, id: item.id, nama })}
    />
  );

  const alamatLengkap = (a: { alamat: string; kabKota: string; provinsi: string; kodePos: string }) =>
    `${a.alamat}, ${a.kabKota}, ${a.provinsi} ${a.kodePos}`;

  const kolomLegal: Column<AspekLegal>[] = [
    { key: "jenis", header: "Jenis", primary: true, cell: (x) => x.jenis },
    { key: "nomor", header: "Nomor Dokumen", cell: (x) => <span className="font-mono text-mono">{x.nomor}</span> },
    { key: "tanggal", header: "Tanggal", cell: (x) => formatTanggal(x.tanggal) },
    { key: "berlaku", header: "Masa Berlaku", cell: (x) => (x.masaBerlaku ? formatTanggal(x.masaBerlaku) : "Seterusnya") },
    { key: "instansi", header: "Instansi Penerbit", cell: (x) => x.instansiPenerbit },
    { key: "aksi", header: "Aksi", action: true, align: "right", cell: (x) => aksi("aspekLegal", x, `${x.jenis} ${x.nomor}`) },
  ];

  const kolomPabrik: Column<Pabrik>[] = [
    { key: "nama", header: "Nama", primary: true, cell: (x) => x.nama },
    { key: "alamat", header: "Alamat", cell: alamatLengkap },
    { key: "status", header: "Status", cell: (x) => labelStatusPabrik[x.status] },
    { key: "aksi", header: "Aksi", action: true, align: "right", cell: (x) => aksi("pabrik", x, x.nama) },
  ];

  const kolomOutlet: Column<Outlet>[] = [
    { key: "nama", header: "Nama", primary: true, cell: (x) => x.nama },
    { key: "alamat", header: "Alamat", cell: alamatLengkap },
    { key: "aksi", header: "Aksi", action: true, align: "right", cell: (x) => aksi("outlet", x, x.nama) },
  ];

  const kolomPenyelia: Column<PenyeliaHalal>[] = [
    { key: "nama", header: "Nama", primary: true, cell: (x) => x.nama },
    { key: "ktp", header: "No. KTP", cell: (x) => <span className="font-mono text-mono">{x.noKtp}</span> },
    { key: "agama", header: "Agama", cell: (x) => x.agama },
    { key: "sertifikat", header: "No. Sertifikat", cell: (x) => x.noSertifikat ?? "-" },
    { key: "sk", header: "No. SK", cell: (x) => x.noSk ?? "-" },
    { key: "berkas", header: "Foto KTP", cell: (x) => <BerkasLabel berkas={x.berkasKtp} /> },
    { key: "aksi", header: "Aksi", action: true, align: "right", cell: (x) => aksi("penyeliaHalal", x, x.nama) },
  ];

  const tombolUbah = (onClick: () => void, nama: string) => (
    <Button size="sm" variant="secondary" icon={<IconPencil size={16} stroke={1.75} />} onClick={onClick} aria-label={`Ubah ${nama}`}>
      Ubah
    </Button>
  );

  const tabel = <T extends { id: string }>(kunci: KunciDaftar, kolom: Column<T>[], kosong: string, deskripsi?: string) => (
    <Seksi title={configDaftar[kunci].judul} description={deskripsi} onTambah={() => setModal({ jenis: "daftar", kunci })}>
      <DataTable
        caption={configDaftar[kunci].judul}
        columns={kolom}
        rows={pu[kunci] as unknown as T[]}
        getRowId={(x) => x.id}
        numbered
        emptyMessage={kosong}
      />
    </Seksi>
  );

  return (
    <>
      <PageHeader title="Pelaku Usaha" description="Data usaha Anda dipakai otomatis di setiap pengajuan sertifikasi halal." />

      <div className="flex flex-col gap-6">
        <div className="grid gap-6 lg:grid-cols-3">
          <Card title="Profil usaha" className="lg:col-span-2" actions={tombolUbah(() => setModal({ jenis: "profil" }), "profil usaha")}>
            <Rincian
              items={[
                ["Nama usaha", pu.namaUsaha],
                ["NIB", <span className="font-mono text-mono">{pu.nib}</span>],
                ["Skala usaha", labelSkala[pu.skala]],
                ["Alamat", alamatLengkap(pu)],
              ]}
            />
          </Card>
          <Card title="Penanggung jawab" actions={tombolUbah(() => setModal({ jenis: "pj" }), "penanggung jawab")}>
            <dl className="flex flex-col gap-4">
              {[
                ["Nama", pu.penanggungJawab.nama],
                ["Nomor HP", pu.penanggungJawab.noHp],
                ["Email", pu.penanggungJawab.email],
              ].map(([dt, dd]) => (
                <div key={dt} className="min-w-0">
                  <dt className="text-caption text-ink-muted">{dt}</dt>
                  <dd className="break-words text-body-sm text-ink">{dd}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>

        {tabel("aspekLegal", kolomLegal, "Belum ada dokumen legal. Tambahkan NIB Anda.", "Dokumen perizinan usaha, minimal NIB berbasis risiko dari OSS.")}
        {tabel("pabrik", kolomPabrik, "Belum ada pabrik. Tambahkan dapur atau tempat produksi Anda.", "Tempat produk dibuat, termasuk dapur rumah.")}
        {tabel("outlet", kolomOutlet, "Belum ada outlet.", "Tempat produk dijual, misalnya warung atau kios.")}
        {tabel(
          "penyeliaHalal",
          kolomPenyelia,
          "Belum ada penyelia halal. Untuk usaha mikro, pemilik bisa menjadi penyelia.",
          "Orang yang mengawasi proses produk halal. Untuk usaha mikro bisa pemilik sendiri.",
        )}
      </div>

      {modal?.jenis === "profil" && (
        <FormEntitas
          judul="Ubah Profil Usaha"
          isian={isianProfil}
          awal={pu}
          menyimpan={ubah.isPending}
          onTutup={tutup}
          onSimpan={(h) => simpan({ ...pu, ...(h as Partial<DataPelakuUsaha>) }, "Profil usaha tersimpan")}
        />
      )}
      {modal?.jenis === "pj" && (
        <FormEntitas
          judul="Ubah Penanggung Jawab"
          isian={isianPj}
          awal={pu.penanggungJawab}
          menyimpan={ubah.isPending}
          onTutup={tutup}
          onSimpan={(h) =>
            simpan({ ...pu, penanggungJawab: { ...pu.penanggungJawab, ...(h as Partial<DataPelakuUsaha["penanggungJawab"]>) } }, "Penanggung jawab tersimpan")
          }
        />
      )}
      {modal?.jenis === "daftar" && (
        <FormEntitas
          judul={`${modal.awal ? "Ubah" : "Tambah"} Data ${configDaftar[modal.kunci].judul}`}
          isian={configDaftar[modal.kunci].isian}
          awal={modal.awal}
          menyimpan={ubah.isPending}
          onTutup={tutup}
          onSimpan={(h) => simpanItem(modal.kunci, { ...h, id: modal.awal?.id ?? buatId(configDaftar[modal.kunci].awalan) })}
        />
      )}

      <KonfirmasiHapus
        nama={hapus.target?.nama ?? "data"}
        open={hapus.target !== null}
        onOpenChange={(o) => !o && hapus.tutup()}
        loading={ubah.isPending}
        catatan="Data ini dihapus dari profil pelaku usaha dan tidak bisa dipilih lagi di pengajuan baru."
        onConfirm={async () => {
          const t = hapus.target;
          if (!t) return;
          const daftar = pu[t.kunci] as Array<{ id: string }>;
          if (await simpan({ ...pu, [t.kunci]: daftar.filter((x) => x.id !== t.id) }, `${t.nama} dihapus`)) hapus.tutup();
        }}
      />
    </>
  );
}
