import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// FastAPI mounts /assets -> dist/assets and serves index.html for every other path.
// Vite's default assetsDir is "assets", so with base "/" the emitted URLs are
// /assets/index-xxx.js — exactly what the existing mount serves. (Do NOT set base to
// "/assets/": that double-prefixes to /assets/assets/.)
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    // `npm run dev` proxies API + media to the FastAPI backend on :8000.
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/out": "http://127.0.0.1:8000",
      "/work": "http://127.0.0.1:8000",
    },
  },
});
