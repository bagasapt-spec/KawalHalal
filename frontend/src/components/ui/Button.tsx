import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router";
import type { LinkProps } from "react-router";
import { IconLoader2 } from "@tabler/icons-react";
import { cn } from "../../lib/cn.ts";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const variants: Record<Variant, string> = {
  primary: "bg-brand text-on-brand hover:bg-brand-deep",
  secondary: "border border-line-strong bg-surface-raised text-ink hover:bg-brand-tint",
  ghost: "text-brand hover:bg-brand-tint",
  danger: "border border-status-risk bg-surface-raised text-status-risk hover:bg-status-risk-bg",
};

const sizes: Record<Size, string> = {
  sm: "h-8 gap-1 px-3",
  md: "h-11 gap-2 px-4",
};

function buttonClass(variant: Variant, size: Size, className?: string) {
  return cn(
    "inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-md text-label transition-colors",
    "disabled:cursor-not-allowed disabled:opacity-50",
    variants[variant],
    sizes[size],
    className,
  );
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /** Ikon di kiri label, ukuran 16px. */
  icon?: ReactNode;
  loading?: boolean;
}

/** Satu tombol primary per layar. Label berawal kata kerja, tanpa tanda baca. */
export function Button({
  variant = "primary",
  size = "md",
  icon,
  loading = false,
  disabled,
  type = "button",
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={buttonClass(variant, size, className)}
      {...rest}
    >
      {loading ? <IconLoader2 size={16} stroke={1.75} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}

export interface ButtonLinkProps extends LinkProps {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
}

/** Tautan antarhalaman yang tampil seperti tombol. */
export function ButtonLink({ variant = "primary", size = "md", icon, className, children, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buttonClass(variant, size, typeof className === "string" ? className : undefined)} {...rest}>
      {icon}
      {children}
    </Link>
  );
}
