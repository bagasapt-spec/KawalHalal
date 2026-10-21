import { useState } from "react";
import type { ReactNode } from "react";
import { useParams } from "react-router";
import { IconDownload, IconPencil, IconSend } from "@tabler/icons-react";
import { ApiError, api, useKirimPengajuan, usePelakuUsaha, usePengajuan } from "../../api/index.ts";
import type { JenisDokumen, Pengajuan, PelakuUsaha } from "../../api/index.ts";
import { KartuAsalData } from "../../components/kawal/AsalData.tsx";
import { AuditTrail } from "../../components/kawal/AuditTrail.tsx";
import { DenganTanda } from "../../components/kawal/ProvenanceMark.tsx";
import { BerkasLabel } from "../../components/ui/BerkasLabel.tsx";
import { KelengkapanMeter } from "../../components/kawal/KelengkapanMeter.tsx";
import { PageHeader } from "../../components/layout/PageHeader.tsx";
import { Button, ButtonLink, Card, ConfirmDialog, StatusBadge, useToast } from "../../components/ui/index.ts";
import { hitungKelengkapan, lengkap, totalKelengkapan } from "../../lib/kelengkapan.ts";
import {
  formatTanggal,
  formatWaktu,
  labelArea,
  labelJalur,
  labelLayanan,
  labelPendaftaran,
  labelTab,
  urutanTab,
} from "../../lib/format.ts";
import { statusBukti, statusPengajuan } from "../../lib/status.ts";
import { StatusTimeline } from "./StatusTimeline.tsx";

const dokumen: Array<{ jenis: JenisDokumen; nama: string }> = [
  { jenis: "surat-permohonan", nama: "Surat Permohonan" },
  { jenis: "sjph", nama: "Manual SJPH" },
];

function bisaDiubah(p: Pengajuan) {
  return p.status === "draf" || p.status === "dikembalikan";
}

function namaDariId<T extends { id: string; nama: string }>(semua: T[] | undefined, ids: string[]) {
  const nama = (semua ?? []).filter((x) => ids.includes(x.id)).map((x) => x.nama);
  return nama.length > 0 ? nama.join(", ") : "-";
}

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

function KartuKelengkapan({ p }: { p: Pengajuan }) {
  const k = hitungKelengkapan(p);
  const total = totalKelengkapan(k);
  const ubah = bisaDiubah(p);
  return (
    <Card
      title="Kelengkapan isian"
      description={
        lengkap(total)
          ? "Semua isian wajib sudah terpenuhi."
          : ubah
            ? "Lengkapi tab yang belum selesai sebelum mengirim pengajuan."
            : "Isian saat pengajuan dikirim."
      }
    >
      <KelengkapanMeter skor={total} label="Kelengkapan seluruh pengajuan" />
      <ul className="mt-4 divide-y divide-line">
        {urutanTab.map((tab) => {
          const skor = k[tab];
          const ok = lengkap(skor);
          return (
            <li key={tab} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 last:pb-0">
              <span className="min-w-0 flex-1 basis-40 text-body-sm text-ink">{labelTab[tab]}</span>
              <KelengkapanMeter skor={skor} label={`Kelengkapan tab ${labelTab[tab]}`} className="w-32" />
              {ok ? (
                <StatusBadge tone="ok" className="w-24 justify-center">
                  Lengkap
                </StatusBadge>
              ) : ubah ? (
                <ButtonLink to={`/pengajuan/${p.id}/ubah?tab=${tab}`} variant="ghost" size="sm" className="w-24">
                  Lengkapi
                </ButtonLink>
              ) : (
                <StatusBadge tone="warn" className="w-24 justify-center">
                  Kurang
                </StatusBadge>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function KartuCelahBukti({ p }: { p: Pengajuan }) {
  const perlu = p.bahan.daftarBahan.filter((b) => b.bukti !== "ada");
  return (
    <Card
      title="Bukti bahan yang perlu dilengkapi"
      description="Ditandai dari foto dan pesan WhatsApp. Status ini menunjukkan kelengkapan bukti, bukan penetapan halal."
      actions={
        bisaDiubah(p) && perlu.length > 0 ? (
          <ButtonLink to={`/pengajuan/${p.id}/ubah?tab=bahan`} variant="secondary" size="sm">
            Buka tab Bahan
          </ButtonLink>
        ) : undefined
      }
    >
      {perlu.length === 0 ? (
        <p className="text-body-sm text-ink-muted">
          {p.bahan.daftarBahan.length === 0 ? "Belum ada bahan yang dicatat." : "Semua bahan sudah punya bukti."}
        </p>
      ) : (
        <ul className="divide-y divide-line">
          {perlu.map((b) => (
            <li key={b.id} className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:gap-4">
              <StatusBadge tone={statusBukti[b.bukti].tone} className="self-start">
                {statusBukti[b.bukti].label}
              </StatusBadge>
              <div className="min-w-0">
                <p className="text-body-sm font-semibold text-ink">
                  <DenganTanda sumber={b.sumber} bukti={b.fotoSumber}>
                    {b.nama}
                  </DenganTanda>
                </p>
                {b.alasanBukti && <p className="text-body-sm text-ink-muted">{b.alasanBukti}</p>}
                <p className="mt-1 text-caption">
                  {b.fotoSumber ? <BerkasLabel berkas={b.fotoSumber} /> : <span className="text-ink-muted">Belum ada foto bukti</span>}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function KartuData({ p, pu }: { p: Pengajuan; pu: PelakuUsaha | undefined }) {
  const d = p.data;
  const t = (k: keyof typeof d.sumberField, nilai: ReactNode) =>
    nilai ? <DenganTanda sumber={d.sumberField[k]}>{nilai}</DenganTanda> : "";
  return (
    <Card title="Pengajuan Sertifikasi Halal">
      <Rincian
        items={[
          ["Nomor daftar", p.nomorDaftar ? <span className="font-mono text-mono">{p.nomorDaftar}</span> : "Diberikan setelah dikirim"],
          ["Jalur dan layanan", `${labelJalur[p.jalur]} · ${labelLayanan[p.jenisLayanan]}`],
          ["Nama usaha", p.namaUsaha],
          ["Nomor surat permohonan", t("nomorSurat", d.nomorSurat)],
          ["Tanggal surat", t("tanggalSurat", d.tanggalSurat ? formatTanggal(d.tanggalSurat) : "")],
          ["Jenis produk", t("jenisProduk", d.jenisProduk)],
          ["Merek", t("merek", d.merek)],
          ["Area pemasaran", t("areaPemasaran", labelArea[d.areaPemasaran])],
          [
            "Jenis pendaftaran",
            t(
              "jenisPendaftaran",
              d.jenisPendaftaran === "fasilitasi" && d.kodeFasilitasi
                ? `${labelPendaftaran[d.jenisPendaftaran]} (${d.kodeFasilitasi})`
                : labelPendaftaran[d.jenisPendaftaran],
            ),
          ],
          ...(p.jalur === "self-declare"
            ? ([["Pendamping PPH", t("pendampingPph", d.pendampingPph ?? "")]] as Array<[string, ReactNode]>)
            : []),
          ["Pabrik", namaDariId(pu?.pabrik, d.pabrikIds)],
          ["Outlet", namaDariId(pu?.outlet, d.outletIds)],
          ["Penyelia halal", namaDariId(pu?.penyeliaHalal, d.penyeliaIds)],
          ["Jumlah produk", `${p.produk.length} produk, ${p.bahan.daftarBahan.length} bahan`],
        ]}
      />
    </Card>
  );
}

function KartuDokumen({ p }: { p: Pengajuan }) {
  return (
    <Card title="Formulir unduhan">
      <ul className="flex flex-col gap-3">
        {dokumen.map(({ jenis, nama }) => {
          const url = api.urlDokumen(p.id, jenis);
          return (
            <li key={jenis} className="flex items-center justify-between gap-3">
              <span className="text-body-sm text-ink">{nama}</span>
              {url ? (
                <a
                  href={url}
                  download
                  className="inline-flex h-8 items-center gap-1 rounded-md border border-line-strong px-3 text-label text-ink hover:bg-brand-tint"
                >
                  <IconDownload size={16} stroke={1.75} aria-hidden="true" />
                  Unduh
                </a>
              ) : (
                <span className="text-caption text-ink-muted">Tersedia saat backend aktif</span>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function Kerangka() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Memuat pengajuan">
      <div className="h-10 w-64 animate-pulse rounded-sm bg-line" />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="h-80 animate-pulse rounded-lg bg-line lg:col-span-2" />
        <div className="h-80 animate-pulse rounded-lg bg-line" />
      </div>
    </div>
  );
}

export default function DetailPengajuan() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  // Live: perubahan dari agen KawalHalal langsung tampil tanpa muat ulang
  const q = usePengajuan(id, { live: true });
  const pu = usePelakuUsaha();
  const kirim = useKirimPengajuan(id ?? "");
  const [konfirmasi, setKonfirmasi] = useState(false);

  if (q.isPending) return <Kerangka />;

  if (q.isError) {
    const tidakAda = q.error instanceof ApiError && q.error.status === 404;
    return (
      <>
        <PageHeader title={tidakAda ? "Pengajuan tidak ditemukan" : "Pengajuan gagal dimuat"} back={{ to: "/pengajuan", label: "Daftar pengajuan" }} />
        <Card>
          <p role="alert" className="text-body text-ink-muted">
            {q.error.message}
          </p>
          {!tidakAda && (
            <Button variant="secondary" className="mt-4" onClick={() => q.refetch()}>
              Coba lagi
            </Button>
          )}
        </Card>
      </>
    );
  }

  const p = q.data;
  const ubah = bisaDiubah(p);
  const daftarUrl = p.jalur === "reguler" ? "/pengajuan-reguler" : "/pengajuan";

  const kirimSekarang = () =>
    kirim.mutate(undefined, {
      onSuccess: (hasil) => {
        setKonfirmasi(false);
        toast({
          tone: "info",
          title: "Pengajuan terkirim",
          description: `Nomor daftar ${hasil.nomorDaftar}. Pendamping PPH akan memverifikasi data Anda.`,
        });
      },
      onError: (e) => {
        setKonfirmasi(false);
        toast({ tone: "risk", title: "Pengajuan belum bisa dikirim", description: e.message });
      },
    });

  return (
    <>
      <PageHeader
        title={p.nomorDaftar ?? "Draf pengajuan"}
        back={{ to: daftarUrl, label: `Pengajuan ${labelJalur[p.jalur]}` }}
        meta={<StatusBadge tone={statusPengajuan[p.status].tone}>{statusPengajuan[p.status].label}</StatusBadge>}
        description={`${labelJalur[p.jalur]} · ${labelLayanan[p.jenisLayanan]} · diperbarui ${formatWaktu(p.diperbarui)}`}
        actions={
          ubah && (
            <>
              <ButtonLink to={`/pengajuan/${p.id}/ubah`} variant="secondary" icon={<IconPencil size={16} stroke={1.75} />}>
                Ubah Data
              </ButtonLink>
              <Button icon={<IconSend size={16} stroke={1.75} />} onClick={() => setKonfirmasi(true)}>
                Kirim
              </Button>
            </>
          )
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-6 lg:col-span-2">
          {ubah && <KartuKelengkapan p={p} />}
          <KartuCelahBukti p={p} />
          <KartuData p={p} pu={pu.data} />
          {!ubah && <KartuKelengkapan p={p} />}
        </div>
        <div className="flex min-w-0 flex-col gap-6">
          <Card title="Status pendaftaran">
            <StatusTimeline status={p.status} riwayat={p.riwayat} />
          </Card>
          <KartuAsalData p={p} bisaDiubah={ubah} />
          <KartuDokumen p={p} />
          <Card title="Riwayat aktivitas">
            <AuditTrail entri={p.audit} batas={6} />
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={konfirmasi}
        onOpenChange={setKonfirmasi}
        title="Kirim pengajuan"
        description="Setelah dikirim, data tidak bisa diubah sampai ada hasil verifikasi Pendamping PPH. Pastikan seluruh isian sudah benar."
        confirmLabel="Kirim pengajuan"
        loading={kirim.isPending}
        onConfirm={kirimSekarang}
      />
    </>
  );
}
