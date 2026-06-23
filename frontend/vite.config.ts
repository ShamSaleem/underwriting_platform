import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build straight into the backend's static dir so one container serves everything.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8080",
    },
  },
});
