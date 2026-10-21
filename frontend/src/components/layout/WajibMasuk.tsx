import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { ambilSesi } from "../../lib/sesi.ts";

/** Arahkan ke halaman masuk bila belum ada sesi, lalu kembali ke halaman asal setelah masuk. */
export function WajibMasuk({ children }: { children: ReactNode }) {
  const lokasi = useLocation();
  if (!ambilSesi()) {
    return <Navigate to="/login" replace state={{ dari: lokasi.pathname + lokasi.search }} />;
  }
  return children;
}
