import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Production build lands in backend/static so FastAPI serves the app and API from one URL.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "../backend/static", emptyOutDir: true },
  server: { proxy: { "/api": "http://localhost:8000" } },
});
