import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Same-origin API calls in development: the browser never talks to the backend directly
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  build: { sourcemap: false }, // don't publish source maps in production builds
});
