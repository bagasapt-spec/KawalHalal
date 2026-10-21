import { useState } from "react";
import { Outlet, useNavigate } from "react-router";
import { keluar } from "../../lib/sesi.ts";
import { Dialog } from "radix-ui";
import { IconX } from "@tabler/icons-react";
import { MockBanner } from "../kawal/MockBanner.tsx";
import { IconButton } from "../ui/IconButton.tsx";
import { Sidebar } from "./Sidebar.tsx";
import { Topbar } from "./Topbar.tsx";

/** Sidebar tetap mulai lg; di bawahnya sidebar menjadi drawer. */
export function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="min-h-dvh bg-surface">
      <MockBanner />
      <div className="flex">
        <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 lg:block">
          <Sidebar />
        </aside>

        <Dialog.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/40 lg:hidden" />
            <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] lg:hidden">
              <Dialog.Title className="sr-only">Menu utama</Dialog.Title>
              <Dialog.Description className="sr-only">Navigasi halaman SIHALAL</Dialog.Description>
              <Sidebar onNavigate={() => setDrawerOpen(false)} />
              <Dialog.Close asChild>
                <IconButton
                  label="Tutup menu"
                  tone="inverse"
                  icon={<IconX size={20} stroke={1.75} />}
                  className="absolute right-3 top-3"
                />
              </Dialog.Close>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>

        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar
            userName="Bakso Pak Sam"
            onMenuClick={() => setDrawerOpen(true)}
            onKeluar={() => {
              keluar();
              navigate("/login", { replace: true });
            }}
          />
          <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-6 md:px-8 md:py-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
