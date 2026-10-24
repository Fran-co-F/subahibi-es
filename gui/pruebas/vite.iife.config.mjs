// SPDX-License-Identifier: GPL-3.0-or-later
// Compila la interfaz como un único script clásico (sin módulos ES) para poder montarla en jsdom (ver recorrer.mjs).
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { fileURLToPath } from "url";

export default defineConfig({
  root: fileURLToPath(new URL("..", import.meta.url)),
  plugins: [svelte()],
  logLevel: "error",                                  // (avisos de import.meta en iife: inofensivos acá)
  build: {
    outDir: fileURLToPath(new URL("../dist-pruebas", import.meta.url)),
    emptyOutDir: true,
    cssCodeSplit: false,
    rolldownOptions: { output: { format: "iife", entryFileNames: "app.js" } },
  },
});
