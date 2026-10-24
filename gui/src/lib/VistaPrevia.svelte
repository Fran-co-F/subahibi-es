<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- La ventana de texto del juego: corta las líneas como el motor (por letra, o por palabra si se usó «Cortar líneas»)
     con la fuente, el tamaño y el ancho configurados. -->
<script>
  let { texto = "", config, onconfig } = $props();
  let editando = $state(false);
  let borrador = $state({});

  const ctx = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;

  function cortar(t, c) {
    ctx.font = `${c.tamano}px "${c.fuente}", system-ui, sans-serif`;
    const cabe = (s) => ctx.measureText(s).width <= c.ancho;
    const out = [];
    for (const parrafo of t.split("\n")) {
      let linea = "";
      if (c.corte === "palabra") {
        for (const p of parrafo.split(" ")) {
          const prueba = linea ? linea + " " + p : p;
          if (linea && !cabe(prueba)) { out.push(linea); linea = p; } else linea = prueba;
        }
      } else {
        for (const ch of parrafo) {                       // como el motor: corta donde la letra ya no entra
          if (linea && !cabe(linea + ch)) { out.push(linea); linea = ch.trimStart(); } else linea += ch;
        }
      }
      out.push(linea);
    }
    return out;
  }

  let lineas = $derived(ctx && config ? cortar(texto || "", config) : []);
  let excede = $derived(config?.lineas && lineas.length > config.lineas);

  function abrirConfig() { borrador = { ...config }; editando = true; }
  function guardar() {
    onconfig({ ...borrador, tamano: +borrador.tamano, ancho: +borrador.ancho, lineas: +borrador.lineas });
    editando = false;
  }
</script>

<div class="previa">
  <div class="cabeza">
    <span class="tenue">Vista previa</span>
    <span class="tenue">{lineas.length} línea{lineas.length === 1 ? "" : "s"}{config?.lineas ? ` de ${config.lineas}` : ""}</span>
    {#if excede}<span class="exceso">no entra en la ventana</span>{/if}
    <button class="mini" onclick={abrirConfig} title="Fuente, tamaño y ancho de la ventana">⚙</button>
  </div>
  <div class="ventana" style:width="{config.ancho + 32}px">
    <div class="texto" style:font-family={`"${config.fuente}", system-ui, sans-serif`} style:font-size="{config.tamano}px">
      {#each lineas as l, i}<div class:fuera={config.lineas && i >= config.lineas}>{l || " "}</div>{/each}
    </div>
  </div>
  {#if editando}
    <div class="config">
      <label>Fuente <input bind:value={borrador.fuente} /></label>
      <label>Tamaño (px) <input type="number" bind:value={borrador.tamano} /></label>
      <label>Ancho (px) <input type="number" bind:value={borrador.ancho} /></label>
      <label>Líneas <input type="number" bind:value={borrador.lineas} /></label>
      <label>Corte
        <select bind:value={borrador.corte}><option value="letra">por letra (el motor)</option><option value="palabra">por palabra</option></select>
      </label>
      <div class="acciones"><button onclick={() => (editando = false)}>Cancelar</button><button class="primario" onclick={guardar}>Guardar</button></div>
      <p class="tenue">La fuente tiene que estar instalada en el sistema. Se guarda en el proyecto.</p>
    </div>
  {/if}
</div>

<style>
  .previa { display: grid; gap: 6px; }
  .cabeza { display: flex; align-items: center; gap: 10px; font-size: 12px; }
  .exceso { color: var(--peligro); font-weight: 600; }
  .mini { margin-left: auto; padding: 1px 8px; font-size: 13px; }
  .ventana { max-width: 100%; overflow-x: auto; border-radius: 10px; padding: 14px 16px; min-height: 64px;
             background: linear-gradient(180deg, rgb(18 22 40 / 92%), rgb(10 12 24 / 96%)); box-shadow: inset 0 0 0 1px rgb(255 255 255 / 8%); }
  .texto { color: #f3f4fa; white-space: pre; line-height: 1.35; text-shadow: 0 1px 2px rgb(0 0 0 / 60%); }
  .fuera { color: #ff9d7a; opacity: .75; }
  .config { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; padding: 10px; border: 1px solid var(--borde); border-radius: 8px; background: var(--panel-2); }
  .config label { display: grid; gap: 3px; font-size: 12px; }
  .config input, .config select { padding: 4px 6px; }
  .config .acciones { display: flex; gap: 6px; align-items: end; }
  .config p { grid-column: 1 / -1; margin: 0; font-size: 12px; }
</style>
