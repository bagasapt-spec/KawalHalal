import type { ReactNode } from "react";
import { Checkbox as RadixCheckbox } from "radix-ui";
import { IconCheck } from "@tabler/icons-react";
import { cn } from "../../lib/cn.ts";

export interface CheckboxProps {
  id: string;
  label: ReactNode;
  checked?: boolean;
  defaultChecked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}

export function Checkbox({ id, label, checked, defaultChecked, onCheckedChange, disabled, className }: CheckboxProps) {
  return (
    <div className={cn("flex items-start gap-2", className)}>
      <RadixCheckbox.Root
        id={id}
        checked={checked}
        defaultChecked={defaultChecked}
        disabled={disabled}
        onCheckedChange={(v) => onCheckedChange?.(v === true)}
        className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-sm border border-line-strong bg-surface-raised disabled:opacity-50 data-[state=checked]:border-brand data-[state=checked]:bg-brand"
      >
        <RadixCheckbox.Indicator>
          <IconCheck size={14} stroke={2.5} className="text-on-brand" />
        </RadixCheckbox.Indicator>
      </RadixCheckbox.Root>
      <label htmlFor={id} className="text-body-sm text-ink">
        {label}
      </label>
    </div>
  );
}
