import { IconCircle, IconCircleCheck, IconCircleDot } from "@tabler/icons-react";
import type { RiwayatStatus, StatusPengajuan } from "../../api/index.ts";
import { StatusBadge } from "../../components/ui/index.ts";
import { cn } from "../../lib/cn.ts";
import { formatWaktu } from "../../lib/format.ts";
import { statusPengajuan, urutanStatus } from "../../lib/status.ts";

const keterangan: Record<StatusPengajuan, string> = {
  draf: "Pelaku usaha melengkapi data pengajuan",
  terkirim: "Menunggu diterima Pendamping PPH",
  "verifikasi-pendamping": "Pendamping PPH memverifikasi dan memvalidasi data",
  "verifikasi-bpjph": "BPJPH memeriksa kelengkapan dokumen",
  dikembalikan: "Verifikator meminta perbaikan",
  "sttd-terbit": "Surat Tanda Terima Dokumen terbit",
  "sidang-fatwa": "Komite Fatwa memeriksa hasil verifikasi",
  "sh-terbit": "Sertifikat bisa diunduh",
};

type Keadaan = "selesai" | "aktif" | "menunggu";

export function StatusTimeline({ status, riwayat }: { status: StatusPengajuan; riwayat: RiwayatStatus[] }) {
  const terbalik = [...riwayat].reverse();
  const dikembalikan = status === "dikembalikan";
  // Saat dikembalikan, tahap aktif tetap tahap terakhir sebelum pengembalian
  const tahapAktif = dikembalikan ? (terbalik.find((r) => r.status !== "dikembalikan")?.status ?? "draf") : status;
  const indeksAktif = urutanStatus.indexOf(tahapAktif);
  const catatanKembali = dikembalikan ? terbalik.find((r) => r.status === "dikembalikan")?.catatan : undefined;

  return (
    <div className="flex flex-col gap-4">
      {dikembalikan && (
        <div className="flex flex-col gap-2 rounded-md bg-status-warn-bg p-3">
          <StatusBadge tone="warn" className="self-start">
            Dikembalikan
          </StatusBadge>
          <p className="text-body-sm text-ink">{catatanKembali ?? "Periksa catatan verifikator lalu perbaiki data."}</p>
        </div>
      )}
      <ol className="flex flex-col">
        {urutanStatus.map((s, i) => {
          const keadaan: Keadaan =
            i < indeksAktif || (i === indeksAktif && s === "sh-terbit") ? "selesai" : i === indeksAktif ? "aktif" : "menunggu";
          const waktu = terbalik.find((r) => r.status === s)?.waktu;
          const terakhir = i === urutanStatus.length - 1;
          return (
            <li key={s} className="flex gap-3" aria-current={keadaan === "aktif" ? "step" : undefined}>
              <div className="flex flex-col items-center">
                {keadaan === "selesai" && <IconCircleCheck size={20} stroke={1.75} className="shrink-0 text-status-ok" aria-hidden="true" />}
                {keadaan === "aktif" && (
                  <IconCircleDot
                    size={20}
                    stroke={1.75}
                    className={cn("shrink-0", dikembalikan ? "text-status-warn" : "text-brand")}
                    aria-hidden="true"
                  />
                )}
                {keadaan === "menunggu" && <IconCircle size={20} stroke={1.75} className="shrink-0 text-line-strong" aria-hidden="true" />}
                {!terakhir && <span className={cn("my-1 w-px flex-1", keadaan === "selesai" ? "bg-status-ok" : "bg-line")} />}
              </div>
              <div className={cn("min-w-0", !terakhir && "pb-4")}>
                <p className={cn("text-label", keadaan === "menunggu" ? "text-ink-muted" : "text-ink")}>
                  {statusPengajuan[s].label}
                  <span className="sr-only">
                    {keadaan === "selesai" ? ", selesai" : keadaan === "aktif" ? ", tahap saat ini" : ", belum"}
                  </span>
                </p>
                <p className="text-caption text-ink-muted">{waktu ? formatWaktu(waktu) : keterangan[s]}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
