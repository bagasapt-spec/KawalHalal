import { useState } from "react";
import { useNavigate } from "react-router";
import { RadioGroup } from "radix-ui";
import { useBuatPengajuan, usePelakuUsaha } from "../../api/index.ts";
import type { Jalur, JenisLayanan } from "../../api/index.ts";
import { Button, Field, Modal, Select, hintId, useToast } from "../../components/ui/index.ts";
import { labelJalur } from "../../lib/format.ts";

// SIHALAL asli menulis "belum pernah memiliki sertifikat" di kedua pilihan; di sini dibedakan
const pilihanLayanan: Array<{ value: JenisLayanan; judul: string; keterangan: string }> = [
  { value: "baru", judul: "Baru", keterangan: "Untuk produk yang belum pernah memiliki sertifikat halal." },
  {
    value: "pengembangan",
    judul: "Pengembangan",
    keterangan: "Untuk menambah produk baru ke sertifikat halal yang sudah dimiliki.",
  },
];

export interface AjukanLayananModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jalur: Jalur;
}

export function AjukanLayananModal({ open, onOpenChange, jalur }: AjukanLayananModalProps) {
  const pu = usePelakuUsaha();
  const buat = useBuatPengajuan();
  const navigate = useNavigate();
  const toast = useToast();
  const [layanan, setLayanan] = useState<JenisLayanan>("baru");
  const namaUsaha = pu.data?.namaUsaha ?? "";

  const ajukan = () =>
    buat.mutate(
      { jalur, jenisLayanan: layanan },
      {
        onSuccess: (p) => {
          onOpenChange(false);
          toast({ title: "Draf pengajuan dibuat", description: "Lengkapi isian di setiap tab lalu kirim pengajuan." });
          navigate(`/pengajuan/${p.id}`);
        },
        onError: (e) => toast({ tone: "risk", title: "Draf belum dibuat", description: e.message }),
      },
    );

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={`Ajukan Layanan ${labelJalur[jalur]}`}
      description="Pilih jenis layanan sesuai kondisi produk Anda."
      footer={
        <>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Batal
          </Button>
          <Button onClick={ajukan} loading={buat.isPending} disabled={!namaUsaha}>
            Buat draf
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-6">
        <fieldset>
          <legend className="mb-2 text-label text-ink">Jenis layanan</legend>
          <RadioGroup.Root
            value={layanan}
            onValueChange={(v) => setLayanan(v as JenisLayanan)}
            className="grid gap-3 sm:grid-cols-2"
          >
            {pilihanLayanan.map((p) => (
              <RadioGroup.Item
                key={p.value}
                value={p.value}
                className="flex items-start gap-3 rounded-lg border border-line-strong p-4 text-left transition-colors hover:bg-brand-tint/50 data-[state=checked]:border-brand data-[state=checked]:bg-brand-tint"
              >
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-pill border border-line-strong bg-surface-raised">
                  <RadioGroup.Indicator className="size-2.5 rounded-pill bg-brand" />
                </span>
                <span>
                  <span className="block text-body-sm font-semibold text-ink">{p.judul}</span>
                  <span className="mt-1 block text-caption text-ink-muted">{p.keterangan}</span>
                </span>
              </RadioGroup.Item>
            ))}
          </RadioGroup.Root>
        </fieldset>

        <Field
          label="Nama usaha atau kegiatan"
          htmlFor="nama-usaha"
          required
          hint="Nama ini yang tercetak di sertifikat. Ubah lewat menu Pelaku Usaha."
          error={pu.isError ? "Data pelaku usaha gagal dimuat. Tutup lalu buka lagi formulir ini." : undefined}
        >
          <Select
            id="nama-usaha"
            aria-describedby={hintId("nama-usaha")}
            value={namaUsaha || undefined}
            options={namaUsaha ? [{ value: namaUsaha, label: namaUsaha }] : []}
            placeholder={pu.isPending ? "Memuat..." : "Pilih nama usaha"}
            disabled
          />
        </Field>
      </div>
    </Modal>
  );
}
