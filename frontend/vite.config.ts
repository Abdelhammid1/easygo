import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy API + websocket to the Flask backend (docker: localhost:8080).
const BACKEND = process.env.VITE_BACKEND ?? "http://localhost:8080";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/socket.io": { target: BACKEND, ws: true, changeOrigin: true },
    },
  },
});
