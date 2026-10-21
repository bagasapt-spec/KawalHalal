import { Select as RadixSelect } from "radix-ui";
import { IconCheck, IconChevronDown } from "@tabler/icons-react";
import { cn } from "../../lib/cn.ts";
import { fieldBase } from "./Field.tsx";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps {
  id?: string;
  options: SelectOption[];
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  invalid?: boolean;
  className?: string;
  "aria-describedby"?: string;
}

export function Select({
  id,
  options,
  value,
  defaultValue,
  onValueChange,
  placeholder = "Pilih salah satu",
  disabled,
  invalid,
  className,
  ...rest
}: SelectProps) {
  return (
    <RadixSelect.Root value={value} defaultValue={defaultValue} onValueChange={onValueChange} disabled={disabled}>
      <RadixSelect.Trigger
        id={id}
        aria-invalid={invalid || undefined}
        aria-describedby={rest["aria-describedby"]}
        className={cn(
          fieldBase,
          "flex h-11 items-center justify-between gap-2 text-left data-[placeholder]:text-ink-muted/70",
          className,
        )}
      >
        <span className="min-w-0 truncate">
          <RadixSelect.Value placeholder={placeholder} />
        </span>
        <RadixSelect.Icon>
          <IconChevronDown size={16} stroke={1.75} className="text-ink-muted" />
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          sideOffset={4}
          className="z-50 max-h-72 w-[var(--radix-select-trigger-width)] overflow-hidden rounded-sm border border-line bg-surface-raised"
        >
          <RadixSelect.Viewport className="p-1">
            {options.map((opt) => (
              <RadixSelect.Item
                key={opt.value}
                value={opt.value}
                className="flex cursor-pointer select-none items-center justify-between gap-2 rounded-sm px-3 py-2 text-body-sm text-ink outline-none data-[highlighted]:bg-brand-tint data-[state=checked]:font-semibold"
              >
                <RadixSelect.ItemText>{opt.label}</RadixSelect.ItemText>
                <RadixSelect.ItemIndicator>
                  <IconCheck size={16} stroke={1.75} className="text-brand" />
                </RadixSelect.ItemIndicator>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}
