<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<script>
  import { onMount } from "svelte";
  import { api, confirmar, correrTarea } from "../lib/api.js";
  import { app, avisar, COLOR_ESTADO, ESTADOS, pct } from "../lib/estado.svelte.js";
  import Barra from "../lib/Barra.svelte";

  let resumen = $state(null);
  let tarea = $state(null);          // {tipo, log: [], estado}
  let anchoWrap = $state(44);
  let p = $derived(app.info.proyecto);

  async function cargar() {
    try {
      resumen = await api("GET", "resumen");
      app.info = { ...app.info, ...(await api("GET", "info")) };
    } catch (e) { avisar(e.message, "error"); }
  }
  onMount(cargar);

  const total = (est) => Object.values(est || {}).reduce((a, b) => a + b, 0);
  const listo = (est) => (est?.["traducido"] || 0) + (est?.["del parche"] || 0);
  const grupoEstados = (g) => g.escenarios.reduce((acc, e) => { for (const [k, v] of Object.entries(e.estados)) acc[k] = (acc[k] || 0) + v; return acc; }, {});

  async function correr(tipo, opciones = {}, pregunta = null) {
    if (pregunta && !(await confirmar(pregunta))) return;
    tarea = { tipo, log: [], estado: "corriendo" };
    try {
      const t = await correrTarea(tipo, opciones, (l) => tarea.log.push(l));
      tarea.estado = t.estado;
      if (t.estado === "ok") avisar(`«${tipo}» terminó en ${t.segundos} s`);
      else { tarea.log.push(t.error); avisar(t.error, "error"); }
    } catch (e) { tarea.estado = "error"; tarea.log.push(e.message); avisar(e.message, "error"); }
    await cargar();
  }
</script>

<div class="panel">
  <header>
    <div>
      <h1>{p.juego}</h1>
      <div class="tenue mono">{p.raiz}</div>
    </div>
    <div class="etiquetas">
      <span class="etiqueta">perfil {p.perfil}</span>
      <span class="etiqueta">motor {p.motor}</span>
      {#if p.version}<span class="etiqueta">{p.version}</span>{/if}
      <span class="etiqueta">{p.idiomas[0]} → {p.idiomas[1]}</span>
    </div>
  </header>

  {#if resumen && !resumen.exportado}
    <div class="tarjeta vacio">
      <h2>Primer paso: exportar</h2>
      <p class="tenue">Saca el texto y las imágenes de interfaz del juego para poder traducirlos{p.parche_viejo ? ", con el parche anterior precargado" : ""}.</p>
      <button class="primario" onclick={() => correr("exportar")} disabled={tarea?.estado === "corriendo"}>Exportar</button>
    </div>
  {:else if resumen}
    {@const n = total(resumen.estados)}
    <section class="tarjeta avance">
      <div class="numeros">
        <div><div class="grande">{pct(listo(resumen.estados), n)}%</div><div class="tenue">listo para el parche</div></div>
        {#each ESTADOS as e}
          <div><div class="medio"><span class="punto" style:background={COLOR_ESTADO[e]}></span> {(resumen.estados[e] || 0).toLocaleString()}</div><div class="tenue">{e}</div></div>
        {/each}
        <div><div class="medio">{resumen.imagenes_traducidas}</div><div class="tenue">imágenes traducidas</div></div>
      </div>
      <Barra estados={resumen.estados} alto={12} />
    </section>

    <div class="columnas">
      <section class="tarjeta grupos">
        <h2>Por archivo</h2>
        <div class="lista">
          {#each resumen.grupos as g}
            {@const est = grupoEstados(g)}
            <div class="grupo">
              <span class="mono">{g.grupo}</span>
              <Barra estados={est} />
              <span class="tenue num">{pct(listo(est), total(est))}%</span>
              <span class="tenue num">{total(est).toLocaleString()} filas</span>
            </div>
          {/each}
        </div>
      </section>

      <section class="tarjeta acciones">
        <h2>Acciones</h2>
        <div class="botones">
          <button class="primario" onclick={() => correr("build")} disabled={tarea?.estado === "corriendo"}>Armar parche</button>
          <button onclick={() => correr("jugable")} disabled={tarea?.estado === "corriendo"} title="Carpeta de prueba con enlaces al juego">Armar carpeta jugable</button>
          {#if p.instalado}
            <button onclick={() => correr("desinstalar")} disabled={tarea?.estado === "corriendo"}>Desinstalar del juego</button>
          {:else}
            <button onclick={() => correr("instalar")} disabled={tarea?.estado === "corriendo" || !p.build}>Instalar en el juego</button>
          {/if}
          <div class="wrap">
            <button onclick={() => correr("wrap", { max_caracteres: anchoWrap })} disabled={tarea?.estado === "corriendo"}>Cortar líneas</button>
            <label class="tenue">a <input type="number" min="10" max="200" bind:value={anchoWrap} /> caracteres</label>
          </div>
          <button class="peligro" onclick={() => correr("exportar", { forzar: true }, "Exportar de nuevo reemplaza la traducción actual (queda una copia en backup/). ¿Seguir?")}
                  disabled={tarea?.estado === "corriendo"}>Exportar de nuevo…</button>
        </div>
        {#if tarea}
          <div class="registro">
            <div class="titulo"><b>{tarea.tipo}</b> <span class="tenue">{tarea.estado === "corriendo" ? "en curso…" : tarea.estado}</span></div>
            <pre>{tarea.log.join("\n") || "…"}</pre>
          </div>
        {/if}
      </section>
    </div>
  {:else}
    <p class="tenue">Cargando…</p>
  {/if}
</div>

<style>
  .panel { height: 100%; overflow: auto; padding: 26px 30px; display: grid; gap: 18px; align-content: start; }
  header { display: flex; justify-content: space-between; align-items: end; gap: 16px; flex-wrap: wrap; }
  .etiquetas { display: flex; gap: 6px; flex-wrap: wrap; }
  .vacio { padding: 28px; display: grid; gap: 10px; justify-items: start; }
  .vacio p { margin: 0; }
  .avance { padding: 20px 22px; display: grid; gap: 16px; }
  .numeros { display: flex; gap: 34px; flex-wrap: wrap; align-items: end; }
  .grande { font-size: 36px; font-weight: 750; letter-spacing: -0.03em; line-height: 1; }
  .medio { font-size: 20px; font-weight: 650; display: flex; align-items: center; gap: 7px; }
  .columnas { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(320px, 1fr); gap: 18px; }
  .grupos, .acciones { padding: 18px 20px; display: grid; gap: 12px; align-content: start; }
  .lista { display: grid; gap: 8px; }
  .grupo { display: grid; grid-template-columns: 90px 1fr 52px 92px; gap: 12px; align-items: center; }
  .num { text-align: right; font-size: 13px; }
  .botones { display: grid; gap: 8px; }
  .botones > button { justify-self: stretch; text-align: left; }
  .wrap { display: flex; gap: 8px; align-items: center; }
  .wrap input { width: 64px; padding: 4px 6px; }
  .registro { border: 1px solid var(--borde); border-radius: 8px; overflow: hidden; }
  .titulo { padding: 6px 10px; background: var(--panel-2); font-size: 13px; }
  pre { margin: 0; padding: 10px; max-height: 260px; overflow: auto; font: 12px/1.5 var(--mono); white-space: pre-wrap; word-break: break-word; }
  @media (max-width: 1050px) { .columnas { grid-template-columns: 1fr; } }
</style>
