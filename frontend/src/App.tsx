import { Route, Routes } from "react-router";
import { AppShell } from "./components/layout/AppShell.tsx";
import { WajibMasuk } from "./components/layout/WajibMasuk.tsx";
import Dashboard from "./pages/Dashboard.tsx";
import Komponen from "./pages/Komponen.tsx";
import Login from "./pages/Login.tsx";
import NotFound from "./pages/NotFound.tsx";
import RevisiSh from "./pages/RevisiSh.tsx";
import Tagihan from "./pages/Tagihan.tsx";
import PelakuUsaha from "./pages/pelaku/PelakuUsaha.tsx";
import DaftarPengajuan from "./pages/pengajuan/DaftarPengajuan.tsx";
import DetailPengajuan from "./pages/pengajuan/DetailPengajuan.tsx";
import StatusPermohonan from "./pages/pengajuan/StatusPermohonan.tsx";
import UbahData from "./pages/ubah/UbahData.tsx";

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<Login />} />
      <Route
        element={
          <WajibMasuk>
            <AppShell />
          </WajibMasuk>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="pelaku-usaha" element={<PelakuUsaha />} />
        <Route path="pengajuan" element={<DaftarPengajuan jalur="self-declare" />} />
        <Route path="pengajuan-reguler" element={<DaftarPengajuan jalur="reguler" />} />
        <Route path="pengajuan/:id" element={<DetailPengajuan />} />
        <Route path="pengajuan/:id/ubah" element={<UbahData />} />
        <Route path="status" element={<StatusPermohonan />} />
        <Route path="tagihan" element={<Tagihan />} />
        <Route path="revisi-sh" element={<RevisiSh />} />
        {import.meta.env.DEV && <Route path="komponen" element={<Komponen />} />}
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
