import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/resume": "http://localhost:8000",
      "/session": "http://localhost:8000",
      "/dashboard": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
