import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Teruskan /api ke FastAPI lokal (backend/main.py, uvicorn :8000)
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
