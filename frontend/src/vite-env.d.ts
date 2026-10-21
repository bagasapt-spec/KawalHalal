/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "mock" memakai fixture di browser, "http" memanggil FastAPI lewat proxy /api. Bawaan: mock. */
  readonly VITE_API_MODE?: "mock" | "http";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
