import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": backendTarget,
      "/locations": backendTarget,
      "/compare-bill": backendTarget,
      "/upload-bill": backendTarget,
      "/cghs": backendTarget,
      "/health": backendTarget,
    },
  },
});
