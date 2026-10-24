// SPDX-License-Identifier: GPL-3.0-or-later
// Cliente de la API local (src/tl_organizer/nucleo/api.py).  Dónde está la API:
//   - página servida por `tl-organizer gui`: window.TL_ORGANIZER (misma dirección, token incluido);
//   - app de Tauri: el comando «backend» (Rust levanta Python y elige puerto y token);
//   - `npm run dev` en el navegador: VITE_API_URL y VITE_API_TOKEN (de `tl-organizer servir`).
let base = null;

export async function conectar() {
  if (window.TL_ORGANIZER) base = window.TL_ORGANIZER;
  else if (window.__TAURI_INTERNALS__) {
    const { invoke } = await import("@tauri-apps/api/core");
    base = await invoke("backend");
  } else base = { url: import.meta.env.VITE_API_URL || "", token: import.meta.env.VITE_API_TOKEN || "" };
  // el servidor puede tardar un momento en arrancar (Tauri lo lanza junto con la ventana)
  for (let i = 0; ; i++) {
    try {
      return await api("GET", "info");
    } catch (e) {
      if (i > 60 || e.status) throw e;
      await new Promise((r) => setTimeout(r, 250));
    }
  }
}

export const enTauri = () => !!window.__TAURI_INTERNALS__;

export async function api(metodo, ruta, cuerpo) {
  const r = await fetch(`${base.url}/api/${ruta}`, {
    method: metodo,
    headers: { "X-TL-Token": base.token, ...(cuerpo !== undefined ? { "Content-Type": "application/json" } : {}) },
    body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
  });
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) {
    const e = new Error(datos.error || `error ${r.status}`);
    e.status = r.status;
    throw e;
  }
  return datos;
}

export function urlImagen(cual, nombre, version = "") {
  return `${base.url}/api/galeria/${cual}/${encodeURIComponent(nombre)}?token=${encodeURIComponent(base.token)}&v=${version}`;
}

export async function subirImagen(nombre, archivo) {
  const r = await fetch(`${base.url}/api/galeria/traducida/${encodeURIComponent(nombre)}`, {
    method: "PUT",
    headers: { "X-TL-Token": base.token },
    body: archivo,
  });
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(datos.error || `error ${r.status}`);
  return datos;
}

export async function elegirCarpeta() {
  if (!enTauri()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  return await open({ directory: true, multiple: false, title: "Carpeta de instalación del juego" });
}

export async function elegirArchivo(titulo) {
  if (!enTauri()) return null;
  const { open } = await import("@tauri-apps/plugin-dialog");
  return await open({ directory: false, multiple: false, title: titulo, filters: [{ name: "Parche", extensions: ["zip"] }] });
}

// Una tarea larga (exportar, build…): la lanza y va pasando el registro a onLog hasta que termina.
export async function correrTarea(tipo, opciones, onLog) {
  let t = await api("POST", "tareas", { tipo, opciones });
  let desde = 0;
  for (;;) {
    t = await api("GET", `tareas/${t.id}?desde=${desde}`);
    for (const l of t.log) onLog(l);
    desde = t.total_log;
    if (t.estado !== "corriendo") return t;
    await new Promise((r) => setTimeout(r, 400));
  }
}

// Pregunta sí/no: diálogo nativo en Tauri (window.confirm no siempre está disponible en el webview).
export async function confirmar(texto) {
  if (!enTauri()) return window.confirm(texto);
  const { ask } = await import("@tauri-apps/plugin-dialog");
  return await ask(texto, { title: "tl-organizer", kind: "warning" });
}
