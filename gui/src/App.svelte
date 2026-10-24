<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<script>
  import { onMount } from "svelte";
  import { conectar } from "./lib/api.js";
  import { app } from "./lib/estado.svelte.js";
  import Inicio from "./vistas/Inicio.svelte";
  import Panel from "./vistas/Panel.svelte";
  import Editor from "./vistas/Editor.svelte";
  import Revision from "./vistas/Revision.svelte";
  import Galeria from "./vistas/Galeria.svelte";

  let error = $state(null);
  onMount(async () => {
    try { app.info = await conectar(); } catch (e) { error = e.message; }
  });

  const VISTAS = [
    { id: "panel", nombre: "Panel", icono: "M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" },
    { id: "editor", nombre: "Traducir", icono: "M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 0 0 0-1.41l-2.34-2.34a1 1 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z" },
    { id: "revision", nombre: "Revisar", icono: "M9 16.17 4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" },
    { id: "galeria", nombre: "Imágenes", icono: "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2zM8.5 13.5l2.5 3 3.5-4.5 4.5 6H5l3.5-4.5z" },
  ];
  let proyecto = $derived(app.info?.proyecto);
</script>

{#if error}
  <div class="centro">
    <div class="tarjeta caja">
      <h2>No pude conectar con tl-organizer</h2>
      <p class="tenue">{error}</p>
      <p class="tenue">La app de escritorio lanza <code>python -m tl_organizer servir</code>: comprobá que Python y tl-organizer estén instalados.</p>
    </div>
  </div>
{:else if !app.info}
  <div class="centro tenue">Conectando…</div>
{:else if !proyecto}
  <Inicio />
{:else}
  <div class="marco">
    <nav>
      <div class="logo">tl<span>·</span>organizer</div>
      {#each VISTAS as v}
        <button class="nav" class:activo={app.vista === v.id} onclick={() => (app.vista = v.id)}
                disabled={v.id !== "panel" && !proyecto.exportado}>
          <svg viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d={v.icono} /></svg>
          {v.nombre}
        </button>
      {/each}
      <div class="pie">
        <div class="juego" title={proyecto.raiz}>{proyecto.juego}</div>
        <div class="tenue mono">{proyecto.motor} · {proyecto.idiomas[0]} → {proyecto.idiomas[1]}</div>
        <button class="cambiar" onclick={() => (app.info = { ...app.info, proyecto: null })}>Cambiar de proyecto</button>
      </div>
    </nav>
    <main>
      {#if app.vista === "panel"}<Panel />
      {:else if app.vista === "editor"}<Editor />
      {:else if app.vista === "revision"}<Revision />
      {:else if app.vista === "galeria"}<Galeria />{/if}
    </main>
  </div>
{/if}

{#if app.aviso}
  <div class="aviso" class:error={app.aviso.tipo === "error"}>{app.aviso.texto}</div>
{/if}

<style>
  .centro { height: 100%; display: grid; place-items: center; padding: 24px; }
  .caja { padding: 28px; max-width: 520px; }
  .marco { display: grid; grid-template-columns: 210px 1fr; height: 100%; }
  nav { background: var(--panel); border-right: 1px solid var(--borde); display: flex; flex-direction: column; padding: 16px 10px; gap: 2px; }
  .logo { font-weight: 750; font-size: 17px; padding: 4px 12px 18px; letter-spacing: -0.02em; }
  .logo span { color: var(--acento); }
  .nav { display: flex; align-items: center; gap: 10px; background: none; border: none; padding: 9px 12px; text-align: left; color: var(--texto-2); }
  .nav:hover:not(:disabled) { background: var(--panel-2); color: var(--texto); }
  .nav.activo { background: var(--acento-2); color: var(--acento); font-weight: 600; }
  .pie { margin-top: auto; padding: 12px; border-top: 1px solid var(--borde); display: grid; gap: 4px; }
  .juego { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .cambiar { margin-top: 8px; font-size: 12px; padding: 4px 8px; }
  main { overflow: hidden; min-width: 0; }
  .aviso { position: fixed; bottom: 18px; left: 50%; transform: translateX(-50%); background: var(--texto); color: var(--panel);
           padding: 10px 18px; border-radius: 10px; box-shadow: var(--sombra); max-width: 70vw; z-index: 50; }
  .aviso.error { background: var(--peligro); color: #fff; }
</style>
