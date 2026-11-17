import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.VITE_DEV_API || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          recharts: ["recharts"],
          motion: ["motion"],
          "face-api": ["face-api.js"],
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api/, ""),
      },
      "/resume": apiTarget,
      "/session": apiTarget,
      "/health": apiTarget,
      "/transcribe": apiTarget,
    },
  },
});
