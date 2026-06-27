import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3002,
    proxy: {
      "/api": "http://localhost:5002",
    },
  },
  build: {
    outDir: "../backend/static",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          mui: ["@mui/material", "@mui/icons-material", "@emotion/react", "@emotion/styled"],
          charts: ["recharts"],
        },
      },
    },
  },
});
