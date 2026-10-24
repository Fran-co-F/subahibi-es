// SPDX-License-Identifier: GPL-3.0-or-later
// Estado global de la interfaz (runas de Svelte 5).
export const app = $state({
  info: null,            // /api/info
  vista: "panel",        // panel | editor | revision | galeria
  ir: null,              // {escenario, clave}: pedido de abrir el editor en una fila
  aviso: null,           // {tipo: "ok"|"error", texto}
});

export const ESTADOS = ["sin traducir", "del parche", "revisar", "traducido"];
export const COLOR_ESTADO = {
  "sin traducir": "var(--c-sin)", "del parche": "var(--c-parche)", revisar: "var(--c-revisar)", traducido: "var(--c-ok)",
};

export function avisar(texto, tipo = "ok") {
  app.aviso = { texto, tipo };
  setTimeout(() => { if (app.aviso?.texto === texto) app.aviso = null; }, tipo === "error" ? 8000 : 3500);
}

export function abrirEnEditor(clave) {
  const escenario = clave.slice(0, clave.lastIndexOf(":"));
  app.ir = { escenario, clave };
  app.vista = "editor";
}

export const pct = (a, b) => (b ? Math.round((1000 * a) / b) / 10 : 0);
