import { IconInfoCircle } from "@tabler/icons-react";

/** Penanda tetap bahwa ini tiruan untuk demo, bukan SIHALAL resmi. */
export function MockBanner() {
  return (
    <div className="flex items-center justify-center gap-2 bg-brand-tint px-4 py-1 text-center text-caption text-brand">
      <IconInfoCircle size={16} stroke={1.75} className="shrink-0" aria-hidden="true" />
      Tiruan untuk demo KawalHalal. Bukan SIHALAL resmi.
    </div>
  );
}
