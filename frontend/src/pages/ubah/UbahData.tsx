import { useParams, useSearchParams } from "react-router";
import { IconArrowLeft, IconArrowRight } from "@tabler/icons-react";
import { usePelakuUsaha, usePengajuan } from "../../api/index.ts";
import type { Pengajuan } from "../../api/index.ts";
import { BannerAsalData } from "../../components/kawal/AsalData.tsx";
import { PageHeader } from "../../components/layout/PageHeader.tsx";
import { Button, ButtonLink, Card, StatusBadge, TabPanel, Tabs } from "../../components/ui/index.ts";
import type { TabItem } from "../../components/ui/index.ts";
import { hitungKelengkapan } from "../../lib/kelengkapan.ts";
import { labelJalur, labelTab } from "../../lib/format.ts";
import { statusPengajuan } from "../../lib/status.ts";
import TabBahan from "./TabBahan.tsx";
import TabData from "./TabData.tsx";
import TabDokumen from "./TabDokumen.tsx";
import TabKomitmen from "./TabKomitmen.tsx";
import TabPemantauan from "./TabPemantauan.tsx";
import TabProduk from "./TabProduk.tsx";
import TabProses from "./TabProses.tsx";

const urutan = ["data", "komitmen", "bahan", "proses", "produk", "pemantauan", "dokumen"] as const;
type KunciTab = (typeof urutan)[number];

function bacaTab(nilai: string | null): KunciTab {
  return (urutan as readonly string[]).includes(nilai ?? "") ? (nilai as KunciTab) : "data";
}

function itemTab(p: Pengajuan): TabItem[] {
  const k = hitungKelengkapan(p);
  return urutan.map((t) => ({
    value: t,
    label: t === "dokumen" ? "Dokumen" : labelTab[t],
    progress: t === "dokumen" ? undefined : k[t],
  }));
}

export default function UbahData() {
  const { id } = useParams<{ id: string }>();
  const [params, setParams] = useSearchParams();
  const tab = bacaTab(params.get("tab"));
  // Live: isian dari agen KawalHalal ikut muncul selama halaman terbuka
  const q = usePengajuan(id, { live: true });
  const pu = usePelakuUsaha();

  const pindah = (t: string) => {
    setParams({ tab: t }, { replace: true });
    window.scrollTo({ top: 0 });
  };

  if (q.isPending) {
    return <div className="h-96 animate-pulse rounded-lg bg-line" aria-busy="true" aria-label="Memuat pengajuan" />;
  }

  if (q.isError) {
    return (
      <>
        <PageHeader title="Ubah Data" back={{ to: "/pengajuan", label: "Daftar pengajuan" }} />
        <Card>
          <p role="alert" className="text-body text-ink-muted">
            {q.error.message}
          </p>
        </Card>
      </>
    );
  }

  const p = q.data;
  const detailUrl = `/pengajuan/${p.id}`;

  if (p.status !== "draf" && p.status !== "dikembalikan") {
    return (
      <>
        <PageHeader title="Ubah Data" back={{ to: detailUrl, label: "Detail pengajuan" }} />
        <Card>
          <p className="text-body text-ink-muted">
            Pengajuan ini sudah dikirim sehingga datanya tidak bisa diubah. Tunggu hasil verifikasi, atau perbaiki bila
            pengajuan dikembalikan.
          </p>
          <ButtonLink to={detailUrl} variant="secondary" className="mt-4">
            Lihat detail pengajuan
          </ButtonLink>
        </Card>
      </>
    );
  }

  const indeks = urutan.indexOf(tab);
  const sebelum = urutan[indeks - 1];
  const sesudah = urutan[indeks + 1];
  const props = { p, pu: pu.data };

  return (
    <>
      <PageHeader
        title="Ubah Data"
        back={{ to: detailUrl, label: "Detail pengajuan" }}
        meta={<StatusBadge tone={statusPengajuan[p.status].tone}>{statusPengajuan[p.status].label}</StatusBadge>}
        description={`${labelJalur[p.jalur]} · ${p.namaUsaha}${p.nomorDaftar ? ` · ${p.nomorDaftar}` : ""}`}
      />

      <BannerAsalData p={p} />

      <Tabs label="Bagian pengajuan" items={itemTab(p)} value={tab} onValueChange={pindah}>
        <TabPanel value="data">
          <TabData {...props} />
        </TabPanel>
        <TabPanel value="komitmen">
          <TabKomitmen {...props} />
        </TabPanel>
        <TabPanel value="bahan">
          <TabBahan {...props} />
        </TabPanel>
        <TabPanel value="proses">
          <TabProses {...props} />
        </TabPanel>
        <TabPanel value="produk">
          <TabProduk {...props} />
        </TabPanel>
        <TabPanel value="pemantauan">
          <TabPemantauan {...props} />
        </TabPanel>
        <TabPanel value="dokumen">
          <TabDokumen {...props} />
        </TabPanel>
      </Tabs>

      <nav aria-label="Pindah tab" className="mt-6 flex flex-wrap justify-between gap-2 border-t border-line pt-4">
        {sebelum ? (
          <Button variant="ghost" icon={<IconArrowLeft size={16} stroke={1.75} />} onClick={() => pindah(sebelum)}>
            {sebelum === "dokumen" ? "Dokumen" : labelTab[sebelum]}
          </Button>
        ) : (
          <span />
        )}
        {sesudah ? (
          <Button variant="ghost" onClick={() => pindah(sesudah)}>
            {sesudah === "dokumen" ? "Dokumen" : labelTab[sesudah]}
            <IconArrowRight size={16} stroke={1.75} aria-hidden="true" />
          </Button>
        ) : (
          <ButtonLink to={detailUrl} variant="secondary">
            Selesai, kembali ke detail
          </ButtonLink>
        )}
      </nav>
    </>
  );
}
