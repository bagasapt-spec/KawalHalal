import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn.ts";

type Tone = "neutral" | "brand" | "danger" | "inverse";

const tones: Record<Tone, string> = {
  neutral: "text-ink-muted hover:bg-surface hover:text-ink",
  brand: "text-brand hover:bg-brand-tint",
  danger: "text-status-risk hover:bg-status-risk-bg",
  inverse: "text-on-deep hover:bg-white/10",
};

export interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Wajib: dibacakan pembaca layar dan muncul sebagai tooltip. */
  label: string;
  icon: ReactNode;
  tone?: Tone;
}

export function IconButton({ label, icon, tone = "neutral", type = "button", className, ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex size-9 shrink-0 items-center justify-center rounded-md transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-50",
        tones[tone],
        className,
      )}
      {...rest}
    >
      {icon}
    </button>
  );
}
