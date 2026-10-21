import { createContext, useCallback, useContext, useState } from "react";
import type { ReactNode } from "react";
import { Toast as RadixToast } from "radix-ui";
import { IconX } from "@tabler/icons-react";
import { StatusBadge } from "./StatusBadge.tsx";
import type { StatusTone } from "./StatusBadge.tsx";

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  tone: StatusTone;
}

type ShowToast = (toast: Omit<ToastItem, "id" | "tone"> & { tone?: StatusTone }) => void;

const ToastContext = createContext<ShowToast | null>(null);

const toneLabel: Record<StatusTone, string> = {
  ok: "Berhasil",
  warn: "Perhatian",
  risk: "Gagal",
  info: "Info",
  neutral: "Info",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const show = useCallback<ShowToast>(({ tone = "ok", ...rest }) => {
    setToasts((prev) => [...prev, { id: Date.now() + Math.random(), tone, ...rest }]);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      <RadixToast.Provider swipeDirection="right" duration={4000}>
        {children}
        {toasts.map((t) => (
          <RadixToast.Root
            key={t.id}
            onOpenChange={(open) => !open && setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            className="flex items-start gap-3 rounded-lg border border-line bg-surface-raised p-4"
          >
            <div className="flex min-w-0 flex-1 flex-col gap-1">
              <StatusBadge tone={t.tone} className="self-start">
                {toneLabel[t.tone]}
              </StatusBadge>
              <RadixToast.Title className="text-body-sm font-semibold text-ink">{t.title}</RadixToast.Title>
              {t.description && (
                <RadixToast.Description className="text-body-sm text-ink-muted">{t.description}</RadixToast.Description>
              )}
            </div>
            <RadixToast.Close aria-label="Tutup notifikasi" className="rounded-md p-1 text-ink-muted hover:bg-surface">
              <IconX size={16} stroke={1.75} />
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="fixed bottom-0 right-0 z-[60] flex w-full flex-col gap-2 p-4 outline-none md:max-w-sm" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast harus dipakai di dalam ToastProvider");
  return ctx;
}
