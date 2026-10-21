import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { Tabs as RadixTabs } from "radix-ui";
import { IconCircleCheck } from "@tabler/icons-react";
import { cn } from "../../lib/cn.ts";

export interface TabItem {
  value: string;
  label: string;
  /** Kelengkapan isian tab, ditampilkan sebagai "3/6" atau ikon centang. */
  progress?: { done: number; total: number };
}

export interface TabsProps {
  label: string;
  items: TabItem[];
  value: string;
  onValueChange: (value: string) => void;
  children: ReactNode;
  className?: string;
}

function Progress({ done, total }: { done: number; total: number }) {
  if (total > 0 && done >= total) {
    return (
      <span className="text-status-ok">
        <IconCircleCheck size={16} stroke={1.75} aria-hidden="true" />
        <span className="sr-only">, lengkap</span>
      </span>
    );
  }
  return (
    <span className="rounded-pill bg-surface px-2 text-caption text-ink-muted">
      {done}/{total}
      <span className="sr-only"> terisi</span>
    </span>
  );
}

export function Tabs({ label, items, value, onValueChange, children, className }: TabsProps) {
  const listRef = useRef<HTMLDivElement>(null);

  // Di layar sempit daftar tab bisa digeser; pastikan tab aktif selalu terlihat
  useEffect(() => {
    const list = listRef.current;
    const aktif = list?.querySelector<HTMLElement>("[data-state=active]");
    if (!list || !aktif) return;
    // List berposisi relative, jadi offsetLeft tab sudah relatif terhadap list
    const kiri = aktif.offsetLeft;
    if (kiri < list.scrollLeft || kiri + aktif.offsetWidth > list.scrollLeft + list.clientWidth) {
      list.scrollTo({ left: kiri - 16 });
    }
  }, [value]);

  return (
    <RadixTabs.Root value={value} onValueChange={onValueChange} className={className}>
      <RadixTabs.List
        ref={listRef}
        aria-label={label}
        // relative: elemen sr-only di tab yang tergulir tetap terkurung, tidak melebarkan halaman
        className="relative -mx-4 flex gap-1 overflow-x-auto border-b border-line px-4 md:mx-0 md:px-0"
      >
        {items.map((item) => (
          <RadixTabs.Trigger
            key={item.value}
            value={item.value}
            className={cn(
              "-mb-px flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 border-transparent px-3 py-3 text-label text-ink-muted",
              "hover:text-ink data-[state=active]:border-brand data-[state=active]:text-brand",
            )}
          >
            {item.label}
            {item.progress && <Progress {...item.progress} />}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {children}
    </RadixTabs.Root>
  );
}

export function TabPanel({ value, children, className }: { value: string; children: ReactNode; className?: string }) {
  return (
    <RadixTabs.Content value={value} className={cn("mt-6 flex flex-col gap-6", className)}>
      {children}
    </RadixTabs.Content>
  );
}
