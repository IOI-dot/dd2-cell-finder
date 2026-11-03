import path from "node:path";
import tailwind from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const backend = "http://127.0.0.1:8123";

export default defineConfig({
  plugins: [react(), tailwind()],
  resolve: {
    alias: {
      "@openuidev/devtools": path.resolve(__dirname, "src/no-devtools.ts"), // it would load a script from a CDN in development
    },
    dedupe: ["react", "react-dom"],
  },
  server: { proxy: { "/api": backend, "/agent": backend } },
});
