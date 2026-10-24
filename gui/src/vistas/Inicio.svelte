<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<script>
  import { api, elegirArchivo, elegirCarpeta, enTauri } from "../lib/api.js";
  import { app, avisar } from "../lib/estado.svelte.js";

  let carpeta = $state("");
  let parche = $state("");
  let idioma = $state("es");
  let ocupado = $state(false);
  let crear = $state(false);

  async function abrir(ruta = carpeta) {
    ocupado = true;
    try {
      const p = await api("POST", "proyecto/abrir", { carpeta: ruta });
      app.info = { ...app.info, proyecto: p };
      app.vista = "panel";
    } catch (e) {
      if (e.status === 404) { crear = true; carpeta = ruta; avisar("Esa carpeta todavía no tiene proyecto: podés crearlo.", "ok"); }
      else avisar(e.message, "error");
    } finally { ocupado = false; }
  }

  async function crearProyecto() {
    ocupado = true;
    try {
      const p = await api("POST", "proyecto/crear", { carpeta, parche_viejo: parche || null, idioma });
      app.info = { ...app.info, proyecto: p };
      app.vista = "panel";
    } catch (e) { avisar(e.message, "error"); } finally { ocupado = false; }
  }

  async function elegir() {
    const r = await elegirCarpeta();
    if (r) { carpeta = r; await abrir(r); }
  }
</script>

<div class="inicio">
  <div class="cabeza">
    <h1>tl<span>·</span>organizer</h1>
    <p class="tenue">Organizá la traducción de una novela visual: texto, imágenes, revisión y parche.</p>
  </div>

  <div class="tarjeta bloque">
    <h2>Abrir un juego</h2>
    <p class="tenue">Elegí la carpeta donde está instalado el juego. Si todavía no tiene proyecto, lo creamos.</p>
    <div class="fila">
      <input placeholder="/ruta/a/la/carpeta/del/juego" bind:value={carpeta} onkeydown={(e) => e.key === "Enter" && abrir()} />
      {#if enTauri()}<button onclick={elegir} disabled={ocupado}>Elegir carpeta…</button>{/if}
      <button class="primario" onclick={() => abrir()} disabled={ocupado || !carpeta}>Abrir</button>
    </div>

    {#if crear}
      <div class="crear">
        <h3>Crear el proyecto en esta carpeta</h3>
        <label>Parche anterior (opcional, .zip)
          <div class="fila">
            <input placeholder="precarga la traducción vieja" bind:value={parche} />
            {#if enTauri()}<button onclick={async () => { const r = await elegirArchivo("Parche anterior"); if (r) parche = r; }}>Elegir…</button>{/if}
          </div>
        </label>
        <label>Idioma de la traducción
          <select bind:value={idioma}>
            <option value="es">Español</option><option value="en">Inglés</option><option value="pt">Portugués</option>
            <option value="fr">Francés</option><option value="it">Italiano</option><option value="de">Alemán</option>
          </select>
        </label>
        <div><button class="primario" onclick={crearProyecto} disabled={ocupado}>Crear proyecto</button></div>
      </div>
    {/if}
  </div>

  {#if app.info.recientes?.length}
    <div class="tarjeta bloque">
      <h2>Recientes</h2>
      <div class="recientes">
        {#each app.info.recientes as r}
          <button class="reciente" onclick={() => abrir(r)} disabled={ocupado}>
            <span class="nombre">{r.split(/[\\/]/).filter(Boolean).at(-1)}</span>
            <span class="tenue mono">{r}</span>
          </button>
        {/each}
      </div>
    </div>
  {/if}
  <p class="tenue pie">Motores disponibles: {app.info.motores.join(", ")}</p>
</div>

<style>
  .inicio { max-width: 720px; margin: 0 auto; padding: 56px 24px; display: grid; gap: 18px; }
  .cabeza h1 { font-size: 34px; letter-spacing: -0.03em; }
  .cabeza h1 span { color: var(--acento); }
  .bloque { padding: 22px; display: grid; gap: 12px; }
  .bloque p { margin: 0; }
  .fila { display: flex; gap: 8px; }
  .fila input { flex: 1; min-width: 0; }
  .crear { border-top: 1px solid var(--borde); padding-top: 14px; display: grid; gap: 12px; }
  label { display: grid; gap: 6px; font-weight: 500; }
  label select { justify-self: start; }
  .recientes { display: grid; gap: 6px; }
  .reciente { display: grid; text-align: left; gap: 2px; background: var(--panel-2); padding: 10px 14px; }
  .reciente .nombre { font-weight: 600; }
  .reciente .mono { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pie { text-align: center; font-size: 12px; }
</style>
