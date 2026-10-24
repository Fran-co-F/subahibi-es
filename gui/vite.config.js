// SPDX-License-Identifier: GPL-3.0-or-later
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

// En desarrollo la API la levanta Tauri (o `tl-organizer servir`); ver src/lib/api.js.
export default defineConfig({
  plugins: [svelte()],
  clearScreen: false,
  server: { port: 5173, strictPort: true },
  envPrefix: ["VITE_", "TAURI_"],
  build: { outDir: "dist", target: "es2022" },
});
