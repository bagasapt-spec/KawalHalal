import type { ReactNode } from "react";
import { Dialog } from "radix-ui";
import { IconX } from "@tabler/icons-react";
import { cn } from "../../lib/cn.ts";
import { IconButton } from "./IconButton.tsx";

const sizes = {
  sm: "md:w-[min(92vw,420px)]",
  md: "md:w-[min(92vw,600px)]",
  lg: "md:w-[min(92vw,840px)]",
} as const;

export interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  /** Tombol di kanan bawah: Batal lalu aksi utama. */
  footer?: ReactNode;
  size?: keyof typeof sizes;
  children: ReactNode;
}

/** Layar penuh di mobile, kotak di tengah mulai md. */
export function Modal({ open, onOpenChange, title, description, footer, size = "md", children }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/40" />
        <Dialog.Content
          className={cn(
            "fixed inset-0 z-50 flex flex-col bg-surface-raised",
            "md:inset-auto md:left-1/2 md:top-1/2 md:max-h-[85vh] md:-translate-x-1/2 md:-translate-y-1/2 md:rounded-lg md:border md:border-line",
            sizes[size],
          )}
        >
          <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-4 md:px-6">
            <div className="min-w-0">
              <Dialog.Title className="text-h3 text-ink">{title}</Dialog.Title>
              {description ? (
                <Dialog.Description className="mt-1 text-body-sm text-ink-muted">{description}</Dialog.Description>
              ) : (
                <Dialog.Description className="sr-only">{title}</Dialog.Description>
              )}
            </div>
            <Dialog.Close asChild>
              <IconButton label="Tutup" icon={<IconX size={20} stroke={1.75} />} className="-mr-2 -mt-1" />
            </Dialog.Close>
          </header>
          <div className="flex-1 overflow-y-auto px-4 py-4 md:px-6">{children}</div>
          {footer && (
            <footer className="flex justify-end gap-2 border-t border-line px-4 py-3 md:px-6">{footer}</footer>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
