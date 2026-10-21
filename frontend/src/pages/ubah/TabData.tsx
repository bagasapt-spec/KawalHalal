import { useState } from "react";
import { Link } from "react-router";
import type { DataPengajuan } from "../../api/index.ts";
import { ProvenanceMark } from "../../components/kawal/ProvenanceMark.tsx";
import { StickyActionBar } from "../../components/layout/StickyActionBar.tsx";
import { Button, Card, Checkbox, DateInput, Field, Input, Select, hintId, useToast } from "../../components/ui/index.ts";
import { opsiAreaPemasaran, opsiJenisPendaftaran, opsiKlasifikasi } from "../../lib/opsi.ts";
import { sumberPengguna, useSimpanBagian } from "./shared.tsx";
import type { TabProps } from "./shared.tsx";

type KunciField = Exclude<keyof DataPengajuan, "sumberField">;
type Galat = Partial<Record<KunciField, string>>;

function periksa(d: DataPengajuan): Galat {
  const g: Galat = {};
  if (!d.nomorSurat.trim()) g.nomorSurat = "Nomor surat belum diisi. Tulis nomor surat permohonan Anda.";
  if (!d.tanggalSurat) g.tanggalSurat = "Tanggal surat belum diisi.";
  if (!d.jenisProduk) g.jenisProduk = "Pilih jenis produk.";
  if (!d.merek.trim()) g.merek = "Merek belum diisi. Tulis nama dagang yang dipakai di kemasan atau papan nama.";
  if (d.jenisPendaftaran === "fasilitasi" && !d.kodeFasilitasi?.trim())
    g.kodeFasilitasi = "Kode fasilitasi belum diisi. Tanyakan kodenya ke Pendamping PPH.";
  if (d.pabrikIds.length === 0) g.pabrikIds = "Pilih minimal satu pabrik atau dapur produksi.";
  if (d.penyeliaIds.length === 0) g.penyeliaIds = "Pilih minimal satu penyelia halal.";
  return g;
}

function toggle(daftar: string[], id: string, aktif: boolean) {
  return aktif ? [...daftar, id] : daftar.filter((x) => x !== id);
}

export default function TabData({ p, pu }: TabProps) {
  const toast = useToast();
  const { simpan, menyimpan } = useSimpanBagian(p.id);
  // Salinan lokal: isian tidak ikut berubah oleh polling selama pengguna mengetik
  const [d, setD] = useState<DataPengajuan>(p.data);
  const [galat, setGalat] = useState<Galat>({});
  const berubah = JSON.stringify(d) !== JSON.stringify(p.data);

  const set = <K extends KunciField>(kunci: K, nilai: DataPengajuan[K]) => {
    setD((lama) => ({ ...lama, [kunci]: nilai, sumberField: { ...lama.sumberField, [kunci]: sumberPengguna() } }));
    setGalat((g) => ({ ...g, [kunci]: undefined }));
  };

  const kirimSimpan = async () => {
    const g = periksa(d);
    setGalat(g);
    if (Object.keys(g).length > 0) {
      toast({ tone: "warn", title: "Isian belum lengkap", description: "Perbaiki isian bertanda merah lalu simpan lagi." });
      return;
    }
    await simpan({ bagian: "data", isi: d }, "Data pengajuan tersimpan");
  };

  const aria = (k: KunciField) => (galat[k] ? hintId(k) : undefined);
  // Penanda hilang begitu pengguna mengubah isian (sumberField diganti oleh set)
  const tanda = (k: KunciField) => <ProvenanceMark sumber={d.sumberField[k]} />;

  return (
    <>
      <Card title="Data Pengajuan" description="Isian bertanda * wajib diisi.">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Nomor surat permohonan" htmlFor="nomorSurat" aside={tanda("nomorSurat")} required error={galat.nomorSurat}>
            <Input
              id="nomorSurat"
              value={d.nomorSurat}
              invalid={Boolean(galat.nomorSurat)}
              aria-describedby={aria("nomorSurat")}
              placeholder="Contoh: 001/BPS/X/2026"
              onChange={(e) => set("nomorSurat", e.target.value)}
            />
          </Field>
          <Field label="Tanggal surat permohonan" htmlFor="tanggalSurat" aside={tanda("tanggalSurat")} required error={galat.tanggalSurat}>
            <DateInput
              id="tanggalSurat"
              value={d.tanggalSurat}
              invalid={Boolean(galat.tanggalSurat)}
              aria-describedby={aria("tanggalSurat")}
              onChange={(e) => set("tanggalSurat", e.target.value)}
            />
          </Field>
          <Field label="Jenis produk" htmlFor="jenisProduk" aside={tanda("jenisProduk")} required error={galat.jenisProduk}>
            <Select
              id="jenisProduk"
              options={opsiKlasifikasi}
              value={d.jenisProduk}
              invalid={Boolean(galat.jenisProduk)}
              aria-describedby={aria("jenisProduk")}
              onValueChange={(v) => set("jenisProduk", v)}
            />
          </Field>
          <Field label="Merek" htmlFor="merek" aside={tanda("merek")} required error={galat.merek}>
            <Input
              id="merek"
              value={d.merek}
              invalid={Boolean(galat.merek)}
              aria-describedby={aria("merek")}
              maxLength={100}
              onChange={(e) => set("merek", e.target.value)}
            />
          </Field>
          <Field label="Area pemasaran" htmlFor="areaPemasaran" aside={tanda("areaPemasaran")} required>
            <Select
              id="areaPemasaran"
              options={opsiAreaPemasaran}
              value={d.areaPemasaran}
              onValueChange={(v) => set("areaPemasaran", v as DataPengajuan["areaPemasaran"])}
            />
          </Field>
          <Field label="Jenis pendaftaran" htmlFor="jenisPendaftaran" aside={tanda("jenisPendaftaran")} required>
            <Select
              id="jenisPendaftaran"
              options={opsiJenisPendaftaran}
              value={d.jenisPendaftaran}
              onValueChange={(v) => set("jenisPendaftaran", v as DataPengajuan["jenisPendaftaran"])}
            />
          </Field>
          {d.jenisPendaftaran === "fasilitasi" && (
            <Field
              label="Kode fasilitasi"
              htmlFor="kodeFasilitasi" aside={tanda("kodeFasilitasi")}
              required
              error={galat.kodeFasilitasi}
              hint="Kode program fasilitasi dari penyelenggara, misalnya SEHATI."
            >
              <Input
                id="kodeFasilitasi"
                value={d.kodeFasilitasi ?? ""}
                invalid={Boolean(galat.kodeFasilitasi)}
                aria-describedby={hintId("kodeFasilitasi")}
                onChange={(e) => set("kodeFasilitasi", e.target.value)}
              />
            </Field>
          )}
          {p.jalur === "self-declare" && (
            <Field label="Pendamping PPH" htmlFor="pendampingPph" aside={tanda("pendampingPph")} hint="Nama pendamping yang memverifikasi pengajuan Anda.">
              <Input
                id="pendampingPph"
                value={d.pendampingPph ?? ""}
                aria-describedby={hintId("pendampingPph")}
                onChange={(e) => set("pendampingPph", e.target.value)}
              />
            </Field>
          )}
        </div>
      </Card>

      <Card
        title="Penanggung jawab"
        description={
          <>
            Diambil dari data pelaku usaha.{" "}
            <Link to="/pelaku-usaha" className="text-brand underline">
              Ubah di menu Pelaku Usaha
            </Link>
          </>
        }
      >
        {pu ? (
          <dl className="grid gap-4 sm:grid-cols-3">
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
        ) : (
          <p className="text-body-sm text-ink-muted">Memuat data pelaku usaha...</p>
        )}
      </Card>

      <Card title="Pabrik, outlet, dan penyelia halal" description="Pilih yang terlibat dalam produk yang didaftarkan.">
        <div className="grid gap-6 md:grid-cols-3">
          {(
            [
              ["pabrikIds", "Pabrik atau dapur", pu?.pabrik ?? [], true],
              ["outletIds", "Outlet", pu?.outlet ?? [], false],
              ["penyeliaIds", "Penyelia halal", pu?.penyeliaHalal ?? [], true],
            ] as const
          ).map(([kunci, judul, daftar, wajib]) => (
            <fieldset key={kunci} aria-describedby={galat[kunci] ? hintId(kunci) : undefined}>
              <legend className="mb-2 text-label text-ink">
                {judul}
                {wajib && <span className="ml-1 text-status-risk" aria-hidden="true">*</span>}
                <ProvenanceMark sumber={d.sumberField[kunci]} className="ml-2" />
              </legend>
              {daftar.length === 0 ? (
                <p className="text-body-sm text-ink-muted">Belum ada data. Tambahkan di menu Pelaku Usaha.</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {daftar.map((x) => (
                    <Checkbox
                      key={x.id}
                      id={`${kunci}-${x.id}`}
                      label={x.nama}
                      checked={d[kunci].includes(x.id)}
                      onCheckedChange={(aktif) => set(kunci, toggle(d[kunci], x.id, aktif))}
                    />
                  ))}
                </div>
              )}
              {galat[kunci] && (
                <p id={hintId(kunci)} role="alert" className="mt-2 text-caption text-status-risk">
                  {galat[kunci]}
                </p>
              )}
            </fieldset>
          ))}
        </div>
      </Card>

      <StickyActionBar>
        {!berubah && <span className="mr-auto self-center text-caption text-ink-muted">Belum ada perubahan.</span>}
        {berubah && (
          <Button
            variant="secondary"
            onClick={() => {
              setD(p.data);
              setGalat({});
            }}
          >
            Batalkan perubahan
          </Button>
        )}
        <Button onClick={kirimSimpan} loading={menyimpan} disabled={!berubah}>
          Simpan
        </Button>
      </StickyActionBar>
    </>
  );
}
