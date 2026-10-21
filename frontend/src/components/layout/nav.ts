import type { ComponentType } from "react";
import {
  IconBuildingStore,
  IconComponents,
  IconFilePencil,
  IconFileText,
  IconLayoutDashboard,
  IconProgressCheck,
  IconReceipt,
  IconRosetteDiscountCheck,
} from "@tabler/icons-react";
import type { IconProps } from "@tabler/icons-react";

export interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<IconProps>;
}

export interface NavSection {
  title?: string;
  items: NavItem[];
}

// Satu entri per menu (SIHALAL asli punya dua entri "Pengajuan Self Declare"), istilah seluruhnya Bahasa Indonesia
export const navSections: NavSection[] = [
  {
    items: [
      { to: "/", label: "Dashboard", icon: IconLayoutDashboard },
      { to: "/pelaku-usaha", label: "Pelaku Usaha", icon: IconBuildingStore },
    ],
  },
  {
    title: "Sertifikasi Halal",
    items: [
      { to: "/pengajuan", label: "Pengajuan Self Declare", icon: IconRosetteDiscountCheck },
      { to: "/pengajuan-reguler", label: "Pengajuan Reguler", icon: IconFileText },
      { to: "/status", label: "Status Permohonan", icon: IconProgressCheck },
      { to: "/tagihan", label: "Tagihan", icon: IconReceipt },
      { to: "/revisi-sh", label: "Revisi Sertifikat", icon: IconFilePencil },
    ],
  },
  ...(import.meta.env.DEV
    ? [{ title: "Pengembang", items: [{ to: "/komponen", label: "Komponen UI", icon: IconComponents }] }]
    : []),
];
