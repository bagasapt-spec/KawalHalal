import { Link } from "react-router";
import { IconAlertTriangle, IconSparkles } from "@tabler/icons-react";
import type { Pengajuan } from "../../api/types.ts";
import { kumpulkanAsal, ringkasAsal } from "../../lib/asal.ts";
import { labelTab } from "../../lib/format.ts";
import { Card } from "../ui/Card.tsx";

interface AsalDataProps {
  p: Pengajuan;
  /** Tampilkan tautan ke tab Ubah Data untuk isian yang perlu diperiksa. */
  bisaDiubah: boolean;
}

/** Kartu ringkasan di Detail: berapa isian dari agen, dari pengguna, dan mana yang perlu diperiksa. */
export function KartuAsalData({ p, bisaDiubah }: AsalDataProps) {
  const r = ringkasAsal(kumpulkanAsal(p));
  if (r.agen === 0 && r.pengguna === 0) return null;

  return (
    <Card title="Asal data">
      <dl className="grid grid-cols-2 gap-3">
        <div className="rounded-md bg-brand-tint p-3">
          <dt className="flex items-center gap-1 text-caption text-brand">
            <IconSparkles size={14} stroke={1.75} aria-hidden="true" />
            Diisi KawalHalal
          </dt>
          <dd className="text-h2 tabular-nums text-ink">{r.agen}</dd>
        </div>
        <div className="rounded-md bg-surface p-3">
          <dt className="text-caption text-ink-muted">Diisi atau diubah Anda</dt>
          <dd className="text-h2 tabular-nums text-ink">{r.pengguna}</dd>
        </div>
      </dl>
      {r.rendah.length > 0 ? (
        <div className="mt-4">
          <p className="flex items-center gap-1 text-label text-status-warn">
            <IconAlertTriangle size={16} stroke={1.75} aria-hidden="true" />
            Perlu diperiksa ({r.rendah.length})
          </p>
          <ul className="mt-2 flex flex-col gap-2">
            {r.rendah.map((x, i) => (
              <li key={i} className="flex items-start justify-between gap-3 text-body-sm">
                <span className="min-w-0 text-ink">
                  {x.label}
                  <span className="block text-caption text-ink-muted">
                    Keyakinan {Math.round((x.sumber.keyakinan ?? 0) * 100)}% · {x.sumber.catatan ?? labelTab[x.tab]}
                  </span>
                </span>
                {bisaDiubah && (
                  <Link to={`/pengajuan/${p.id}/ubah?tab=${x.tab}`} className="shrink-0 text-label text-brand hover:underline">
                    Periksa
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        r.agen > 0 && <p className="mt-4 text-body-sm text-ink-muted">Tidak ada isian berkeyakinan rendah.</p>
      )}
    </Card>
  );
}

/** Banner di atas Ubah Data yang menjelaskan arti penanda KawalHalal. */
export function BannerAsalData({ p }: { p: Pengajuan }) {
  const r = ringkasAsal(kumpulkanAsal(p));
  if (r.agen === 0) return null;
  return (
    <div className="mb-6 flex gap-3 rounded-lg border border-line bg-brand-tint p-4 text-body-sm text-ink">
      <IconSparkles size={20} stroke={1.75} className="mt-0.5 shrink-0 text-brand" aria-hidden="true" />
      <p>
        KawalHalal mengisi <strong className="font-semibold">{r.agen} isian</strong> dari percakapan WhatsApp. Klik penanda{" "}
        <span className="inline-flex items-center gap-1 rounded-pill bg-surface-raised px-2 text-caption text-brand">
          <IconSparkles size={12} stroke={1.75} aria-hidden="true" />
          KawalHalal
        </span>{" "}
        untuk melihat asalnya, lalu ubah bila tidak sesuai.
        {r.rendah.length > 0 && (
          <span className="mt-1 block text-status-warn">
            {r.rendah.length} isian berkeyakinan rendah perlu diperiksa: {r.rendah.map((x) => x.label).join(", ")}.
          </span>
        )}
      </p>
    </div>
  );
}
