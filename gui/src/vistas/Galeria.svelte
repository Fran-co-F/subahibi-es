<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<script>
  import { onMount } from "svelte";
  import { api, subirImagen, urlImagen } from "../lib/api.js";
  import { avisar } from "../lib/estado.svelte.js";

  let datos = $state(null);
  let filtro = $state("pendientes");
  let pantalla = $state("");
  let version = $state(Date.now());
  let arrastrando = $state(null);

  async function cargar() {
    try { datos = await api("GET", "galeria"); } catch (e) { avisar(e.message, "error"); }
  }
  onMount(cargar);

  const FILTROS = {
    pendientes: (i) => !["traducida", "sin_japones"].includes(i.estado),
    todas: () => true,
    traducida: (i) => i.estado === "traducida",
    sin_clasificar: (i) => i.estado === "sin_clasificar",
  };
  let pantallas = $derived(datos ? [...new Set(datos.imagenes.map((i) => i.pantalla))].sort() : []);
  let lista = $derived(datos ? datos.imagenes.filter((i) => FILTROS[filtro](i) && (!pantalla || i.pantalla === pantalla)) : []);

  async function soltar(img, e) {
    e.preventDefault();
    arrastrando = null;
    const archivo = e.dataTransfer.files[0];
    if (!archivo) return;
    try {
      await subirImagen(img.nombre, archivo);
      img.estado = "traducida";
      img.traducida = true;
      version = Date.now();
      avisar(`${img.nombre}: traducida`);
    } catch (err) { avisar(`${img.nombre}: ${err.message}`, "error"); }
  }

  async function cambiarEstado(img, estado) {
    try {
      await api("PUT", "galeria/estado", { nombre: img.nombre, estado, nota: img.nota || "" });
      img.estado = estado;
    } catch (e) { avisar(e.message, "error"); }
  }
</script>

<div class="galeria">
  <header>
    <div>
      <h1>Imágenes de interfaz</h1>
      <p class="tenue">Arrastrá la imagen traducida (PNG o BMP, mismo tamaño que el original) sobre su tarjeta.</p>
    </div>
    <div class="filtros">
      {#each [["pendientes", "Pendientes"], ["sin_clasificar", "Sin clasificar"], ["traducida", "Traducidas"], ["todas", "Todas"]] as [id, nombre]}
        <button class="chip" class:activo={filtro === id} onclick={() => (filtro = id)}>{nombre}</button>
      {/each}
      <select bind:value={pantalla}>
        <option value="">Todas las pantallas</option>
        {#each pantallas as p}<option value={p}>{p}</option>{/each}
      </select>
    </div>
  </header>

  {#if datos}
    <p class="tenue cuenta">{lista.length} de {datos.imagenes.length} imágenes</p>
    <div class="grilla">
      {#each lista as img (img.nombre)}
        <div class="tarjeta carta" class:sobre={arrastrando === img.nombre}
             ondragover={(e) => { e.preventDefault(); arrastrando = img.nombre; }} ondragleave={() => (arrastrando = null)}
             ondrop={(e) => soltar(img, e)} role="group" aria-label={img.nombre}>
          <div class="imagenes" class:doble={img.traducida}>
            <img loading="lazy" src={urlImagen("original", img.nombre)} alt="original" />
            {#if img.traducida}<img loading="lazy" src={urlImagen("traducida", img.nombre, version)} alt="traducida" />{/if}
          </div>
          <div class="pie">
            <span class="mono nombre" title={img.nombre}>{img.nombre}</span>
            <span class="tenue">{img.pantalla}</span>
            {#if img.traducida}
              <span class="etiqueta ok">traducida</span>
            {:else}
              <select value={img.estado} onchange={(e) => cambiarEstado(img, e.currentTarget.value)}>
                {#each Object.entries(datos.etiquetas).filter(([k]) => k !== "traducida") as [k, v]}<option value={k}>{v}</option>{/each}
              </select>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <p class="tenue">Cargando…</p>
  {/if}
</div>

<style>
  .galeria { height: 100%; overflow: auto; padding: 26px 30px; }
  header { display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap; align-items: end; margin-bottom: 12px; }
  header p { margin: 4px 0 0; }
  .filtros { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
  .cuenta { font-size: 12px; }
  .grilla { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
  .carta { overflow: hidden; display: flex; flex-direction: column; transition: outline .1s; }
  .carta.sobre { outline: 3px dashed var(--acento); outline-offset: 2px; }
  .imagenes { display: grid; gap: 1px; background: repeating-conic-gradient(var(--panel-2) 0% 25%, var(--panel) 0% 50%) 50% / 16px 16px; min-height: 120px; place-items: center; padding: 8px; }
  .imagenes.doble { grid-template-columns: 1fr 1fr; }
  img { max-width: 100%; max-height: 180px; object-fit: contain; }
  .pie { display: grid; grid-template-columns: 1fr auto; gap: 4px 8px; padding: 10px 12px; border-top: 1px solid var(--borde); align-items: center; }
  .nombre { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .pie select { grid-column: 1 / -1; padding: 3px 6px; font-size: 13px; }
  .pie .etiqueta.ok { grid-column: 1 / -1; justify-self: start; color: var(--c-ok); border-color: var(--c-ok); }
</style>
