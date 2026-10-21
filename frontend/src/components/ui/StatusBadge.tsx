import type { ReactNode } from "react";
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconCircleDashed,
  IconCircleX,
  IconInfoCircle,
} from "@tabler/icons-react";
import { cn } from "../../lib/cn.ts";

export type StatusTone = "ok" | "warn" | "risk" | "info" | "neutral";

const tones: Record<StatusTone, { cls: string; icon: ReactNode }> = {
  ok: { cls: "bg-status-ok-bg text-status-ok", icon: <IconCircleCheck size={16} stroke={1.75} /> },
  warn: { cls: "bg-status-warn-bg text-status-warn", icon: <IconAlertTriangle size={16} stroke={1.75} /> },
  risk: { cls: "bg-status-risk-bg text-status-risk", icon: <IconCircleX size={16} stroke={1.75} /> },
  info: { cls: "bg-status-info-bg text-status-info", icon: <IconInfoCircle size={16} stroke={1.75} /> },
  neutral: { cls: "bg-brand-tint text-ink", icon: <IconCircleDashed size={16} stroke={1.75} /> },
};

export interface StatusBadgeProps {
  tone: StatusTone;
  children: ReactNode;
  /** Ganti ikon bawaan tone bila perlu. */
  icon?: ReactNode;
  className?: string;
}

/** Status selalu ikon + label, tidak hanya warna. */
export function StatusBadge({ tone, children, icon, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-pill px-2 py-1 text-label",
        tones[tone].cls,
        className,
      )}
    >
      <span className="shrink-0" aria-hidden="true">
        {icon ?? tones[tone].icon}
      </span>
      {children}
    </span>
  );
}
