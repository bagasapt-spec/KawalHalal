import { NavLink } from "react-router";
import { cn } from "../../lib/cn.ts";
import { navSections } from "./nav.ts";

export interface SidebarProps {
  /** Dipanggil setelah memilih menu, untuk menutup drawer di mobile. */
  onNavigate?: () => void;
}

export function Sidebar({ onNavigate }: SidebarProps) {
  return (
    <div className="flex h-full flex-col bg-brand-deep text-on-deep">
      <div className="flex h-16 shrink-0 flex-col justify-center px-6">
        <span className="text-h3 font-extrabold tracking-wide">SIHALAL</span>
        <span className="text-caption text-on-deep/70">Tiruan · KawalHalal</span>
      </div>
      <nav aria-label="Menu utama" className="flex-1 overflow-y-auto px-3 pb-6">
        {navSections.map((section, i) => (
          <div key={section.title ?? i} className="mt-4 first:mt-2">
            {section.title && (
              <p className="px-3 pb-2 text-caption uppercase tracking-wider text-on-deep/60">{section.title}</p>
            )}
            <ul className="flex flex-col gap-1">
              {section.items.map(({ to, label, icon: Icon }) => (
                <li key={to}>
                  <NavLink
                    to={to}
                    end={to === "/"}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-label transition-colors",
                        isActive ? "bg-white/15 text-on-deep" : "text-on-deep/75 hover:bg-white/10 hover:text-on-deep",
                      )
                    }
                  >
                    <Icon size={20} stroke={1.75} aria-hidden="true" />
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
    </div>
  );
}
