<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<script>
  import { api } from "../lib/api.js";
  import { abrirEnEditor, avisar } from "../lib/estado.svelte.js";

  const NOMBRES = {
    etiquetas: "Etiquetas sin cerrar", caracteres: "Caracteres que el juego no muestra", marcadores: "Marcadores distintos al original",
    sin_traducir: "Igual al original", restos: "Restos del idioma original", vacia: "Traducido pero vacío", control: "Caracteres invisibles",
    espacios: "Espacios de más", saltos: "Saltos de línea al principio/final", puntuacion: "¿ ¡ sin cerrar", largo: "Líneas largas", lineas: "Demasiadas líneas",
  };
  let res = $state(null);
  let corriendo = $state(false);
  let solo = $state(null);
  let maxCar = $state("");
  let maxLin = $state("");

  async function revisar() {
    corriendo = true;
    try {
      res = await api("POST", "revisar", { max_caracteres: +maxCar || null, max_lineas: +maxLin || null, limite: 20000 });
      solo = null;
    } catch (e) { avisar(e.message, "error"); } finally { corriendo = false; }
  }
  let lista = $derived(res ? res.problemas.filter((p) => !solo || p.codigo === solo) : []);
  let codigos = $derived(res ? Object.entries(res.por_codigo).sort((a, b) => (a[1].nivel === "error" ? -1 : 0) - (b[1].nivel === "error" ? -1 : 0) || b[1].filas - a[1].filas) : []);
</script>

<div class="revision">
  <header>
    <div>
      <h1>Revisión</h1>
      <p class="tenue">Busca problemas en todo lo traducido: etiquetas rotas, caracteres imposibles, restos sin traducir, puntuación…</p>
    </div>
    <div class="opciones">
      <label>Máx. caracteres por línea <input type="number" placeholder="—" bind:value={maxCar} /></label>
      <label>Máx. líneas <input type="number" placeholder="—" bind:value={maxLin} /></label>
      <button class="primario" onclick={revisar} disabled={corriendo}>{corriendo ? "Revisando…" : "Revisar"}</button>
    </div>
  </header>

  {#if res}
    <div class="resumen">
      <button class="chip" class:activo={!solo} onclick={() => (solo = null)}>Todo ({res.total.toLocaleString()})</button>
      {#each codigos as [codigo, c]}
        <button class="chip" class:activo={solo === codigo} class:error={c.nivel === "error"} onclick={() => (solo = codigo)}>
          {NOMBRES[codigo] || codigo} ({c.filas.toLocaleString()})
        </button>
      {/each}
    </div>
    {#if !res.total}
      <div class="tarjeta vacio">Sin problemas. 🎉</div>
    {:else}
      <div class="tarjeta tabla">
        {#each lista.slice(0, 1500) as p}
          <button class="prob" onclick={() => abrirEnEditor(p.clave)}>
            <span class="nivel" class:error={p.nivel === "error"}>{p.nivel}</span>
            <span class="mono clave">{p.clave}</span>
            <span class="detalle">{p.detalle}</span>
            <span class="texto tenue">{p.traduccion}</span>
          </button>
        {/each}
        {#if lista.length > 1500}<p class="tenue mas">… y {(lista.length - 1500).toLocaleString()} más (filtrá por tipo de problema)</p>{/if}
      </div>
    {/if}
  {:else}
    <div class="tarjeta vacio tenue">Apretá «Revisar». El informe completo también queda en <code>revision.tsv</code> en la carpeta de trabajo.</div>
  {/if}
</div>

<style>
  .revision { height: 100%; overflow: auto; padding: 26px 30px; display: grid; gap: 16px; align-content: start; }
  header { display: flex; justify-content: space-between; gap: 20px; flex-wrap: wrap; align-items: end; }
  header p { margin: 4px 0 0; }
  .opciones { display: flex; gap: 10px; align-items: end; }
  .opciones label { display: grid; gap: 3px; font-size: 12px; color: var(--texto-2); }
  .opciones input { width: 110px; }
  .resumen { display: flex; gap: 6px; flex-wrap: wrap; }
  .chip.error { color: var(--peligro); border-color: var(--peligro); }
  .vacio { padding: 28px; text-align: center; }
  .tabla { overflow: hidden; }
  .prob { display: grid; grid-template-columns: 54px 200px minmax(0, 1fr) minmax(0, 1fr); gap: 12px; width: 100%; text-align: left; background: none;
          border: none; border-bottom: 1px solid var(--borde); border-radius: 0; padding: 9px 14px; align-items: start; }
  .prob:hover { background: var(--panel-2); }
  .nivel { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--c-revisar); font-weight: 650; padding-top: 2px; }
  .nivel.error { color: var(--peligro); }
  .clave { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-top: 2px; }
  .texto { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
  .mas { padding: 10px 14px; margin: 0; }
</style>
