import { useState } from "react";
import type { Berkas } from "../../api/index.ts";
import { Button, DateInput, Field, FileInput, Input, Modal, Select, hintId, keBerkas } from "../../components/ui/index.ts";
import type { SelectOption } from "../../components/ui/index.ts";
import { cn } from "../../lib/cn.ts";

/** Satu isian formulir, dipakai untuk menyusun modal tambah/ubah dari konfigurasi. */
export interface Isian {
  kunci: string;
  label: string;
  jenis?: "teks" | "tanggal" | "pilihan" | "berkas";
  opsi?: SelectOption[];
  wajib?: boolean;
  hint?: string;
  /** Lebar penuh di layar lebar. */
  penuh?: boolean;
  mono?: boolean;
  inputMode?: "numeric" | "tel" | "email";
  pola?: { regex: RegExp; pesan: string };
}

type Nilai = Record<string, string>;

function nilaiAwal(isian: Isian[], awal?: object): Nilai {
  const sumber = (awal ?? {}) as Record<string, unknown>;
  return Object.fromEntries(
    isian.map((i) => {
      const v = sumber[i.kunci];
      if (i.jenis === "berkas") return [i.kunci, (v as Berkas | undefined)?.nama ?? ""];
      return [i.kunci, v == null ? (i.jenis === "pilihan" ? (i.opsi?.[0]?.value ?? "") : "") : String(v)];
    }),
  );
}

export function FormEntitas({
  judul,
  isian,
  awal,
  onTutup,
  onSimpan,
  menyimpan,
}: {
  judul: string;
  isian: Isian[];
  awal?: object;
  onTutup: () => void;
  onSimpan: (hasil: Record<string, unknown>) => void;
  menyimpan: boolean;
}) {
  const [nilai, setNilai] = useState<Nilai>(() => nilaiAwal(isian, awal));
  const [dicoba, setDicoba] = useState(false);

  const galatDari = (i: Isian) => {
    const v = nilai[i.kunci].trim();
    if (i.wajib && !v) return `${i.label} belum diisi.`;
    if (v && i.pola && !i.pola.regex.test(v)) return i.pola.pesan;
    return undefined;
  };

  const simpan = () => {
    setDicoba(true);
    if (isian.some((i) => galatDari(i))) return;
    onSimpan(
      Object.fromEntries(
        isian.map((i) => {
          const v = nilai[i.kunci].trim();
          return [i.kunci, i.jenis === "berkas" ? (v ? { nama: v } : undefined) : v || undefined];
        }),
      ),
    );
  };

  const set = (kunci: string, v: string) => setNilai((n) => ({ ...n, [kunci]: v }));

  return (
    <Modal
      open
      onOpenChange={(o) => !o && onTutup()}
      title={judul}
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
      <div className="grid gap-4 md:grid-cols-2">
        {isian.map((i) => {
          const galat = dicoba ? galatDari(i) : undefined;
          const id = `fe-${i.kunci}`;
          const desc = galat || i.hint ? hintId(id) : undefined;
          return (
            <Field key={i.kunci} label={i.label} htmlFor={id} required={i.wajib} hint={i.hint} error={galat} className={cn(i.penuh && "md:col-span-2")}>
              {i.jenis === "pilihan" ? (
                <Select id={id} options={i.opsi ?? []} value={nilai[i.kunci]} invalid={Boolean(galat)} aria-describedby={desc} onValueChange={(v) => set(i.kunci, v)} />
              ) : i.jenis === "tanggal" ? (
                <DateInput id={id} value={nilai[i.kunci]} invalid={Boolean(galat)} aria-describedby={desc} onChange={(e) => set(i.kunci, e.target.value)} />
              ) : i.jenis === "berkas" ? (
                <FileInput
                  id={id}
                  accept=".jpg,.jpeg,.png,.pdf"
                  fileName={nilai[i.kunci] || null}
                  invalid={Boolean(galat)}
                  aria-describedby={desc}
                  onChange={(f) => set(i.kunci, keBerkas(f)?.nama ?? "")}
                />
              ) : (
                <Input
                  id={id}
                  value={nilai[i.kunci]}
                  inputMode={i.inputMode}
                  className={cn(i.mono && "font-mono")}
                  invalid={Boolean(galat)}
                  aria-describedby={desc}
                  onChange={(e) => set(i.kunci, e.target.value)}
                />
              )}
            </Field>
          );
        })}
      </div>
    </Modal>
  );
}
