import { ToggleGroup } from "radix-ui";
import { cn } from "../../lib/cn.ts";

export interface SegmentedToggleProps<T extends string> {
  label: string;
  options: Array<{ value: T; label: string }>;
  value: T;
  onValueChange: (value: T) => void;
  className?: string;
}

/** Pilihan dua atau tiga mode, misalnya Unggah File / Tambah Manual. */
export function SegmentedToggle<T extends string>({ label, options, value, onValueChange, className }: SegmentedToggleProps<T>) {
  return (
    <ToggleGroup.Root
      type="single"
      aria-label={label}
      value={value}
      onValueChange={(v) => v && onValueChange(v as T)}
      className={cn("inline-flex rounded-pill bg-brand-tint p-1", className)}
    >
      {options.map((opt) => (
        <ToggleGroup.Item
          key={opt.value}
          value={opt.value}
          className="h-8 rounded-pill px-4 text-label text-brand transition-colors data-[state=on]:bg-brand data-[state=on]:text-on-brand"
        >
          {opt.label}
        </ToggleGroup.Item>
      ))}
    </ToggleGroup.Root>
  );
}
