import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendTarget = "http://127.0.0.1:8000";

const proxyCommon = {
  target: backendTarget,
  timeout: 120000,
  proxyTimeout: 120000,
};

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": proxyCommon,
      "/locations": proxyCommon,
      "/compare-bill": proxyCommon,
      "/upload-bill": proxyCommon,
      "/upload-prescription": proxyCommon,
      "/upload-clinical-document": proxyCommon,
      "/analyze-treatment": proxyCommon,
      "/cghs": proxyCommon,
      "/health": proxyCommon,
    },
  },
});
