import { useRef } from "react";
import { IconPaperclip, IconTrash, IconUpload } from "@tabler/icons-react";
import { cn } from "../../lib/cn.ts";
import { Button } from "./Button.tsx";
import { IconButton } from "./IconButton.tsx";

export interface FileInputProps {
  id: string;
  /** Nama berkas yang sudah ada (dari server atau pilihan pengguna). */
  fileName?: string | null;
  onChange: (file: File | null) => void;
  accept?: string;
  disabled?: boolean;
  invalid?: boolean;
  "aria-describedby"?: string;
}

export function FileInput({ id, fileName, onChange, accept, disabled, invalid, ...rest }: FileInputProps) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div
      className={cn(
        "flex min-h-11 items-center gap-2 rounded-sm border border-dashed border-line-strong bg-surface-raised px-3 py-1",
        invalid && "border-status-risk",
      )}
    >
      <input
        ref={ref}
        id={id}
        type="file"
        accept={accept}
        disabled={disabled}
        aria-describedby={rest["aria-describedby"]}
        className="sr-only"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
      {fileName ? (
        <>
          <IconPaperclip size={16} stroke={1.75} className="shrink-0 text-ink-muted" />
          <span className="min-w-0 flex-1 truncate text-body-sm text-ink">{fileName}</span>
          <IconButton
            label={`Hapus ${fileName}`}
            tone="danger"
            icon={<IconTrash size={16} stroke={1.75} />}
            disabled={disabled}
            onClick={() => {
              if (ref.current) ref.current.value = "";
              onChange(null);
            }}
          />
        </>
      ) : (
        <>
          <span className="flex-1 text-body-sm text-ink-muted">Belum ada berkas</span>
          <Button
            size="sm"
            variant="secondary"
            icon={<IconUpload size={16} stroke={1.75} />}
            disabled={disabled}
            onClick={() => ref.current?.click()}
          >
            Pilih berkas
          </Button>
        </>
      )}
    </div>
  );
}
