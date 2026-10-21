import { useState } from "react";
import type { ChangeEvent, InputHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/cn.ts";
import { fieldBase } from "./Field.tsx";

function useCharCount(value: unknown, defaultValue: unknown) {
  const [uncontrolled, setUncontrolled] = useState(String(defaultValue ?? "").length);
  // Hitung dari isi sebenarnya (SIHALAL asli menampilkan "0/200" walau field sudah terisi)
  const count = value !== undefined ? String(value ?? "").length : uncontrolled;
  const track = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setUncontrolled(e.target.value.length);
  return { count, track };
}

function Counter({ count, max }: { count: number; max: number }) {
  return (
    <span className={cn("self-end text-caption", count > max ? "text-status-risk" : "text-ink-muted")}>
      {count}/{max}
    </span>
  );
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
  /** Tampilkan penghitung karakter; butuh maxLength. */
  showCount?: boolean;
}

export function Input({ invalid, showCount, className, onChange, ...rest }: InputProps) {
  const { count, track } = useCharCount(rest.value, rest.defaultValue);
  const input = (
    <input
      aria-invalid={invalid || undefined}
      className={cn(fieldBase, "h-11", className)}
      onChange={(e) => {
        track(e);
        onChange?.(e);
      }}
      {...rest}
    />
  );
  if (!showCount || !rest.maxLength) return input;
  return (
    <div className="flex flex-col gap-1">
      {input}
      <Counter count={count} max={rest.maxLength} />
    </div>
  );
}

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
  showCount?: boolean;
}

export function Textarea({ invalid, showCount, className, onChange, rows = 4, ...rest }: TextareaProps) {
  const { count, track } = useCharCount(rest.value, rest.defaultValue);
  return (
    <div className="flex flex-col gap-1">
      <textarea
        rows={rows}
        aria-invalid={invalid || undefined}
        className={cn(fieldBase, "py-2", className)}
        onChange={(e) => {
          track(e);
          onChange?.(e);
        }}
        {...rest}
      />
      {showCount && rest.maxLength && <Counter count={count} max={rest.maxLength} />}
    </div>
  );
}

export function DateInput({ className, ...rest }: Omit<InputProps, "type" | "showCount">) {
  return <Input type="date" className={cn("pr-2", className)} {...rest} />;
}
