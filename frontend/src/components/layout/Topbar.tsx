import { IconLogout, IconMenu2 } from "@tabler/icons-react";
import { IconButton } from "../ui/IconButton.tsx";

export interface TopbarProps {
  onMenuClick: () => void;
  onKeluar: () => void;
  /** Nama pelaku usaha yang sedang masuk (data demo). */
  userName: string;
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

export function Topbar({ onMenuClick, onKeluar, userName }: TopbarProps) {
  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 border-b border-line bg-surface-raised px-4 md:px-8">
      <IconButton
        label="Buka menu"
        icon={<IconMenu2 size={24} stroke={1.75} />}
        onClick={onMenuClick}
        className="-ml-2 lg:hidden"
      />
      <span className="text-h3 font-extrabold text-brand lg:hidden">SIHALAL</span>
      <div className="ml-auto flex items-center gap-3">
        <span className="hidden text-body-sm text-ink sm:inline">{userName}</span>
        <span
          aria-hidden="true"
          className="flex size-9 items-center justify-center rounded-pill bg-brand-tint text-label text-brand"
        >
          {initials(userName)}
        </span>
        <IconButton label="Keluar" icon={<IconLogout size={20} stroke={1.75} />} onClick={onKeluar} />
      </div>
    </header>
  );
}
