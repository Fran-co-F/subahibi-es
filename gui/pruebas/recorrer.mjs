// SPDX-License-Identifier: GPL-3.0-or-later
// Recorre las cuatro pantallas de la interfaz en jsdom contra una API de verdad, y falla si hay errores de JavaScript.
//   1. un proyecto exportado y la API:  cd CARPETA_DEL_JUEGO && TL_ORGANIZER_TOKEN=prueba tl-organizer servir   (anota la URL)
//   2. cd gui && npm run prueba -- http://127.0.0.1:PUERTO
// Edita una fila y la deja como estaba.  (jsdom no tiene canvas ni ResizeObserver: se reemplazan por versiones mínimas.)
import { JSDOM, VirtualConsole } from "jsdom";
import fs from "fs";
const app = new URL("../dist-pruebas/app.js", import.meta.url).pathname;
const base = process.argv[2];
if (!base) { console.error("uso: npm run prueba -- http://127.0.0.1:PUERTO"); process.exit(2); }
const errores = [];
const vc = new VirtualConsole();
vc.on("jsdomError", (e) => { if (!/getContext|Not implemented/.test(String(e))) errores.push("jsdom: " + e.message); });
vc.on("error", (...a) => errores.push("console.error: " + a.join(" ")));
const dom = new JSDOM(`<!doctype html><html><body><div id="app"></div></body></html>`, {
  runScripts: "dangerously", pretendToBeVisual: true, url: "http://127.0.0.1/", virtualConsole: vc,
  beforeParse(w) {
    w.TL_ORGANIZER = { url: base, token: "prueba" };
    w.fetch = (u, o) => fetch(u, o);
    w.HTMLCanvasElement.prototype.getContext = () => ({ font: "", measureText: (s) => ({ width: s.length * 12 }) });
    w.confirm = () => true;
    w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
  },
});
const w = dom.window, d = w.document;
w.addEventListener("error", (e) => errores.push("error: " + e.message));
w.addEventListener("unhandledrejection", (e) => errores.push("promesa: " + (e.reason?.stack || e.reason)));
const espera = (ms) => new Promise((r) => setTimeout(r, ms));
async function hasta(cond, que, ms = 8000) {
  for (let t = 0; t < ms; t += 100) { if (cond()) return; await espera(100); }
  throw new Error("no apareció: " + que + "\n" + texto().slice(0, 700) + "\nERRORES: " + errores.join("\n"));
}
const script = d.createElement("script"); script.textContent = fs.readFileSync(app, "utf8"); d.head.appendChild(script);
const texto = () => d.querySelector("#app").textContent + (d.querySelector(".aviso")?.textContent || "");
const boton = (t) => [...d.querySelectorAll("button")].find((b) => b.textContent.trim().startsWith(t));

await hasta(() => texto().includes("listo para el parche"), "panel");
console.log("PANEL:", texto().match(/[\d.]+%listo para el parche/)?.[0], "| grupos:", d.querySelectorAll(".grupo").length, "| acciones:", !!boton("Armar parche"));

boton("Traducir").click();
await hasta(() => d.querySelectorAll(".fila").length > 0, "filas del editor");
console.log("EDITOR:", d.querySelector(".info").textContent.trim().replace(/\s+/g, " "), "| filas dibujadas:", d.querySelectorAll(".fila").length,
            "| detalle:", d.querySelector(".detalle .mono")?.textContent);
// editar la fila seleccionada y guardar con Ctrl+S
const ta = d.querySelector("textarea"); const antes = ta.value;
ta.value = antes + " (editado por la prueba)"; ta.dispatchEvent(new w.Event("input", { bubbles: true }));
await hasta(() => texto().includes("1 sin guardar"), "pendiente");
w.dispatchEvent(new w.KeyboardEvent("keydown", { key: "s", ctrlKey: true }));
await hasta(() => d.querySelector(".guardado").textContent === "todo guardado", "guardado");
console.log("EDITAR: guardado ok; vista previa:", d.querySelector(".ventana .texto")?.textContent.slice(0, 60));
// volver al texto anterior (para no ensuciar el proyecto de demostración)
d.querySelector("textarea").value = antes; d.querySelector("textarea").dispatchEvent(new w.Event("input", { bubbles: true }));
w.dispatchEvent(new w.KeyboardEvent("keydown", { key: "s", ctrlKey: true }));
await hasta(() => d.querySelector(".guardado").textContent === "todo guardado", "guardado 2");
// buscar en todo el proyecto
const buscar = d.querySelector(".buscar"); buscar.value = "Jabberwock"; buscar.dispatchEvent(new w.Event("input", { bubbles: true }));
d.querySelector(".todo input").click();
await hasta(() => /filas en todo el proyecto/.test(d.querySelector(".info").textContent) && !/cargando/.test(d.querySelector(".info").textContent), "búsqueda global");
console.log("BUSCAR:", d.querySelector(".info").textContent.trim().replace(/\s+/g, " "));

boton("Revisar").click();
await hasta(() => boton("Revisar") && d.querySelector(".revision"), "revision");
[...d.querySelectorAll(".revision button")].find((b) => b.textContent.trim() === "Revisar").click();
await hasta(() => d.querySelectorAll(".prob").length > 0, "problemas", 30000);
console.log("REVISAR:", [...d.querySelectorAll(".resumen .chip")].slice(0, 4).map((c) => c.textContent.trim()).join(" | "));
d.querySelector(".prob").click();
await hasta(() => d.querySelector(".detalle .mono")?.textContent === "3_0705:00135", "saltar al editor");
console.log("IR A LA FILA:", d.querySelector(".detalle .mono").textContent, "->", d.querySelector("textarea").value.slice(0, 50));

boton("Imágenes").click();
await hasta(() => d.querySelectorAll(".carta").length > 0, "galeria");
console.log("GALERIA:", d.querySelector(".cuenta").textContent.trim(), "| primera:", d.querySelector(".carta .nombre").textContent, d.querySelector(".carta img").src.replace(/token=[^&]+/, "token=…").slice(-70));
console.log(errores.length ? "ERRORES:\n" + errores.join("\n") : "sin errores de JavaScript");
process.exit(errores.length ? 1 : 0);
