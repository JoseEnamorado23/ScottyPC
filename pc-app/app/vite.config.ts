import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Puerto fijo que espera tauri.conf.json (devUrl) y que el sidecar admite por CORS.
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: { port: 5173, strictPort: true, watch: { ignored: ["**/src-tauri/**"] } },
  envPrefix: ["VITE_", "TAURI_ENV_"],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/pruebas/preparacion.ts"],
    css: false,
    testTimeout: 20000,
  },
});
