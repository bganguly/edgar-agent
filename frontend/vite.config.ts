import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/chat": "http://localhost:8000",
      "/sessions": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/companies": "http://localhost:8000",
      "/filings": "http://localhost:8000",
      "/aggregates": "http://localhost:8000",
      "/dataset-bounds": "http://localhost:8000",
    },
  },
});
