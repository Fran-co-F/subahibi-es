<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<script>
  import { onDestroy, onMount, tick } from "svelte";
  import { api } from "../lib/api.js";
  import { app, avisar, COLOR_ESTADO, ESTADOS, pct } from "../lib/estado.svelte.js";
  import Barra from "../lib/Barra.svelte";
  import VistaPrevia from "../lib/VistaPrevia.svelte";

  const ALTO_FILA = 64;
  const PREVIA = { fuente: "SubaHibi07Inq", tamano: 24, ancho: 880, lineas: 3, corte: "letra" };

  let grupos = $state([]);                 // [{grupo, escenarios: [{escenario, filas, estados}]}]
  let abiertos = $state({});
  let filtroEsc = $state("");
  let escenario = $state(null);
  let busqueda = $state("");
  let enTodo = $state(false);              // buscar en todo el proyecto
  let filtroEstados = $state([]);
  let filas = $state([]);
  let total = $state(0);
  let sel = $state(0);
  let cargando = $state(false);
  let pendientes = new Map();              // clave -> fila editada sin guardar
  let nPendientes = $state(0);
  let guardando = $state(false);
  let mostrado = $state({ enTodo: false, escenario: null });   // de dónde son las filas que están en pantalla
  let conflictos = $state({});             // clave -> {detalle, servidor}
  let previa = $state({ ...PREVIA });
  let lista = $state(), area = $state();
  let scroll = $state(0), altoLista = $state(600);
  let temporizador = null;

  let fila = $derived(filas[sel]);
  let visibles = $derived.by(() => {
    const desde = Math.max(0, Math.floor(scroll / ALTO_FILA) - 5);
    const hasta = Math.min(filas.length, Math.ceil((scroll + altoLista) / ALTO_FILA) + 5);
    return { desde, items: filas.slice(desde, hasta) };
  });

  onMount(async () => {
    try {
      const r = await api("GET", "resumen");
      grupos = r.grupos;
      const cfg = await api("GET", "config");
      if (cfg.vista_previa) previa = { ...PREVIA, ...cfg.vista_previa };
      const destino = app.ir?.escenario || grupos[0]?.escenarios[0]?.escenario;
      if (destino) await abrirEscenario(destino, app.ir?.clave);
      app.ir = null;
    } catch (e) { avisar(e.message, "error"); }
    window.addEventListener("keydown", teclas);
  });
  onDestroy(() => { window.removeEventListener("keydown", teclas); guardar(); });

  function grupoDe(esc) { return grupos.find((g) => g.escenarios.some((e) => e.escenario === esc))?.grupo; }

  async function abrirEscenario(esc, clave = null) {
    await guardar();
    escenario = esc;
    enTodo = false;
    abiertos[grupoDe(esc)] = true;
    await cargar(clave);
  }

  async function cargar(clave = null) {
    cargando = true;
    try {
      const q = new URLSearchParams();
      if (!enTodo && escenario) q.set("escenario", escenario);
      if (busqueda) q.set("q", busqueda);
      if (filtroEstados.length) q.set("estado", filtroEstados.join(","));
      if (enTodo) q.set("limit", "5000");
      const r = await api("GET", `filas?${q}`);
      filas = r.filas.map((f) => pendientes.get(f.clave) || f);
      total = r.total;
      mostrado = { enTodo, escenario };
      sel = Math.max(0, clave ? filas.findIndex((f) => f.clave === clave) : 0);
      await tick();
      if (lista) { lista.scrollTop = Math.max(0, sel * ALTO_FILA - altoLista / 3); scroll = lista.scrollTop; }
    } catch (e) { avisar(e.message, "error"); } finally { cargando = false; }
  }

  let buscarTimer;
  function alBuscar() { clearTimeout(buscarTimer); buscarTimer = setTimeout(() => guardar().then(() => cargar()), 250); }
  function alternarEstado(e) {
    filtroEstados = filtroEstados.includes(e) ? filtroEstados.filter((x) => x !== e) : [...filtroEstados, e];
    guardar().then(() => cargar());
  }

  function editar(campo, valor) {
    const f = filas[sel];
    if (!f || f[campo] === valor) return;
    const anterior = f.estado;
    f[campo] = valor;
    if (campo === "traduccion" && f.estado === "sin traducir" && valor) f.estado = "traducido";
    ajustarConteo(f.clave, anterior, f.estado);
    pendientes.set(f.clave, f);
    nPendientes = pendientes.size;
    clearTimeout(temporizador);
    temporizador = setTimeout(guardar, 1200);
  }

  function ajustarConteo(clave, antes, despues) {
    if (antes === despues) return;
    const esc = clave.slice(0, clave.lastIndexOf(":"));
    for (const g of grupos) for (const e of g.escenarios) if (e.escenario === esc) {
      e.estados[antes] = (e.estados[antes] || 1) - 1;
      e.estados[despues] = (e.estados[despues] || 0) + 1;
    }
  }

  // Un guardado por vez: si se edita mientras otro está en camino, se guarda después con la base nueva.
  let enCamino = null;
  async function guardar() {
    clearTimeout(temporizador);
    if (enCamino) { await enCamino; return guardar(); }
    if (!pendientes.size) return;
    enCamino = enviar();
    guardando = true;
    try { await enCamino; } finally { enCamino = null; guardando = false; }
  }

  async function enviar() {
    const lote = [...pendientes.values()].map((f) => ({ fila: f, cambio: { clave: f.clave, traduccion: f.traduccion, estado: f.estado, nota: f.nota, base: f.base } }));
    pendientes = new Map();
    nPendientes = 0;
    try {
      const r = await api("PUT", "filas", { cambios: lote.map((x) => x.cambio) });
      const enConflicto = new Map(r.conflictos.map((c) => [c.clave, c.detalle]));
      for (const { fila: f } of lote) {
        const s = r.filas[f.clave];
        if (!s) continue;
        if (enConflicto.has(f.clave)) conflictos[f.clave] = { detalle: enConflicto.get(f.clave), servidor: s };
        else if (pendientes.has(f.clave)) f.base = s.base;      // se volvió a editar mientras tanto: no pisar lo nuevo
        else Object.assign(f, s);
      }
      for (const e of r.errores) avisar(`${e.clave}: ${e.detalle}`, "error");
      if (r.conflictos.length) avisar(`${r.conflictos.length} fila(s) cambiaron también en el proyecto: revisalas`, "error");
    } catch (e) {
      for (const { fila: f } of lote) if (!pendientes.has(f.clave)) pendientes.set(f.clave, f);
      nPendientes = pendientes.size;
      avisar(`No se pudo guardar: ${e.message}`, "error");
    }
  }

  function resolver(clave, usarServidor) {
    const c = conflictos[clave];
    const f = filas.find((x) => x.clave === clave);
    if (usarServidor) Object.assign(f, c.servidor);
    else { f.base = c.servidor.base; pendientes.set(clave, f); nPendientes = pendientes.size; guardar(); }
    delete conflictos[clave];
  }

  async function mover(d) {
    if (!filas.length) return;
    sel = Math.min(filas.length - 1, Math.max(0, sel + d));
    await tick();
    const y = sel * ALTO_FILA;
    if (y < lista.scrollTop) lista.scrollTop = y;
    else if (y + ALTO_FILA > lista.scrollTop + altoLista) lista.scrollTop = y + ALTO_FILA - altoLista;
    area?.focus();
  }

  function confirmarYSeguir() {
    if (fila?.traduccion) editar("estado", "traducido");
    guardar();
    mover(1);
  }

  function teclas(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); confirmarYSeguir(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); guardar(); }
    else if (e.altKey && e.key === "ArrowDown") { e.preventDefault(); mover(1); }
    else if (e.altKey && e.key === "ArrowUp") { e.preventDefault(); mover(-1); }
  }

  async function guardarPrevia(c) {
    previa = c;
    try { await api("PUT", "config", { vista_previa: c }); } catch (e) { avisar(e.message, "error"); }
  }

  const listo = (est) => (est["traducido"] || 0) + (est["del parche"] || 0);
  const suma = (est) => Object.values(est).reduce((a, b) => a + b, 0);
  let gruposFiltrados = $derived(grupos.map((g) => ({ ...g, escenarios: g.escenarios.filter((e) => !filtroEsc || e.escenario.toLowerCase().includes(filtroEsc.toLowerCase())) }))
    .filter((g) => g.escenarios.length));
</script>

<div class="editor">
  <aside>
    <input class="filtro" placeholder="Buscar escenario…" bind:value={filtroEsc} />
    <div class="escenarios">
      {#each gruposFiltrados as g}
        <button class="grupo" onclick={() => (abiertos[g.grupo] = !abiertos[g.grupo])}>
          <span>{abiertos[g.grupo] || filtroEsc ? "▾" : "▸"}</span> <span class="mono">{g.grupo}</span>
          <span class="tenue cuenta">{g.escenarios.length}</span>
        </button>
        {#if abiertos[g.grupo] || filtroEsc}
          {#each g.escenarios as e}
            <button class="esc" class:activo={!enTodo && e.escenario === escenario} onclick={() => abrirEscenario(e.escenario)}>
              <span class="nombre">{e.escenario}</span>
              <span class="tenue pc">{pct(listo(e.estados), suma(e.estados))}%</span>
              <Barra estados={e.estados} alto={4} />
            </button>
          {/each}
        {/if}
      {/each}
    </div>
  </aside>

  <section class="centro">
    <div class="barra-herr">
      <input class="buscar" placeholder="Buscar en original, traducción, clave o nota…" bind:value={busqueda} oninput={alBuscar} />
      <label class="todo"><input type="checkbox" bind:checked={enTodo} onchange={() => guardar().then(() => cargar())} /> todo el proyecto</label>
      <div class="chips">
        {#each ESTADOS as e}
          <button class="chip" class:activo={filtroEstados.includes(e)} onclick={() => alternarEstado(e)}>
            <span class="punto" style:background={COLOR_ESTADO[e]}></span> {e}
          </button>
        {/each}
      </div>
    </div>
    <div class="info tenue">
      {#if cargando}cargando…{:else}{total.toLocaleString()} filas{mostrado.enTodo ? " en todo el proyecto" : mostrado.escenario ? ` en ${mostrado.escenario}` : ""}{total > filas.length ? ` (se muestran ${filas.length})` : ""}{/if}
      <span class="guardado">{nPendientes ? `${nPendientes} sin guardar…` : guardando ? "guardando…" : "todo guardado"}</span>
    </div>
    <div class="lista" bind:this={lista} bind:clientHeight={altoLista} onscroll={() => (scroll = lista.scrollTop)}>
      <div style:height="{filas.length * ALTO_FILA}px" style:position="relative">
        {#each visibles.items as f, i (f.clave)}
          {@const idx = visibles.desde + i}
          <button class="fila" class:sel={idx === sel} class:conflicto={conflictos[f.clave]} style:top="{idx * ALTO_FILA}px"
                  onclick={() => { sel = idx; area?.focus(); }}>
            <span class="punto" style:background={COLOR_ESTADO[f.estado]} title={f.estado}></span>
            <span class="clave mono">{f.clave.split(":").at(-1)}{enTodo ? ` · ${f.clave.slice(0, f.clave.lastIndexOf(":"))}` : ""}</span>
            <span class="orig">{f.original}</span>
            <span class="trad" class:vacia={!f.traduccion}>{f.traduccion || "—"}</span>
          </button>
        {/each}
      </div>
    </div>
  </section>

  <section class="detalle">
    {#if fila}
      <div class="cab">
        <span class="mono">{fila.clave}</span>
        <span class="etiqueta">{fila.tipo}</span>
        <span class="tenue nav-filas">{sel + 1} / {filas.length}</span>
      </div>
      {#if conflictos[fila.clave]}
        <div class="aviso-conflicto">
          <b>Esta fila cambió también en el proyecto</b> (por ejemplo, en una hoja o tras un git pull).
          <div>En el proyecto: «{conflictos[fila.clave].servidor.traduccion}» ({conflictos[fila.clave].servidor.estado})</div>
          <div class="botones">
            <button onclick={() => resolver(fila.clave, true)}>Usar la del proyecto</button>
            <button class="primario" onclick={() => resolver(fila.clave, false)}>Quedarme con la mía</button>
          </div>
        </div>
      {/if}
      <div class="original">{fila.original}</div>
      <textarea bind:this={area} value={fila.traduccion} rows="5" placeholder="Traducción…"
                oninput={(e) => editar("traduccion", e.currentTarget.value)}></textarea>
      <div class="estados">
        {#each ESTADOS as e}
          <button class="chip" class:activo={fila.estado === e} onclick={() => editar("estado", e)}>
            <span class="punto" style:background={COLOR_ESTADO[e]}></span> {e}
          </button>
        {/each}
      </div>
      <input class="nota" placeholder="Nota" value={fila.nota} oninput={(e) => editar("nota", e.currentTarget.value)} />
      <div class="botones">
        <button onclick={() => mover(-1)} title="Alt+↑">↑ Anterior</button>
        <button onclick={() => mover(1)} title="Alt+↓">Siguiente ↓</button>
        <button onclick={() => editar("traduccion", fila.original)} title="Copiar el original a la traducción">Copiar original</button>
        <button class="primario" onclick={confirmarYSeguir} title="Ctrl+Enter">Traducido y siguiente</button>
      </div>
      <VistaPrevia texto={fila.traduccion || fila.original} config={previa} onconfig={guardarPrevia} />
      <p class="tenue atajos">Ctrl+Enter: traducido y siguiente · Alt+↑/↓: moverse · Ctrl+S: guardar ya. Se guarda solo mientras escribís.</p>
    {:else}
      <p class="tenue">Elegí un escenario a la izquierda.</p>
    {/if}
  </section>
</div>

<style>
  .editor { display: grid; grid-template-columns: 250px minmax(0, 1fr) minmax(380px, 34%); height: 100%; }
  aside { border-right: 1px solid var(--borde); display: flex; flex-direction: column; min-height: 0; background: var(--panel); }
  .filtro { margin: 12px; }
  .escenarios { overflow: auto; padding: 0 8px 12px; }
  .grupo { display: flex; gap: 6px; width: 100%; background: none; border: none; padding: 7px 6px; text-align: left; font-weight: 600; }
  .grupo .cuenta { margin-left: auto; font-weight: 400; font-size: 12px; }
  .esc { display: grid; grid-template-columns: 1fr auto; gap: 3px 8px; width: 100%; background: none; border: 1px solid transparent; padding: 6px 8px 7px 22px; text-align: left; border-radius: 8px; }
  .esc:hover { background: var(--panel-2); }
  .esc.activo { background: var(--acento-2); border-color: var(--acento); }
  .esc .nombre { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
  .esc .pc { font-size: 12px; }
  .esc :global(.barra) { grid-column: 1 / -1; }
  .centro { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
  .barra-herr { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 12px 14px 6px; }
  .buscar { flex: 1; min-width: 220px; }
  .todo { display: flex; gap: 5px; align-items: center; font-size: 13px; white-space: nowrap; }
  .chips { display: flex; gap: 5px; flex-wrap: wrap; }
  .info { display: flex; padding: 2px 16px 8px; font-size: 12px; }
  .guardado { margin-left: auto; }
  .lista { flex: 1; overflow: auto; border-top: 1px solid var(--borde); }
  .fila { position: absolute; left: 0; right: 0; height: 64px; display: grid; grid-template-columns: 10px 70px minmax(0, 1fr) minmax(0, 1fr); gap: 4px 12px;
          align-items: start; padding: 9px 14px; background: none; border: none; border-bottom: 1px solid var(--borde); border-radius: 0; text-align: left; }
  .fila:hover { background: var(--panel-2); }
  .fila.sel { background: var(--acento-2); box-shadow: inset 3px 0 0 var(--acento); }
  .fila.conflicto { box-shadow: inset 3px 0 0 var(--peligro); }
  .fila .punto { margin-top: 5px; }
  .clave { color: var(--texto-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding-top: 1px; }
  .orig, .trad { overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; font-size: 13px; line-height: 1.4; white-space: pre-line; }
  .trad.vacia { color: var(--texto-2); }
  .detalle { border-left: 1px solid var(--borde); background: var(--panel); padding: 16px 18px; overflow: auto; display: flex; flex-direction: column; gap: 12px; }
  .cab { display: flex; align-items: center; gap: 8px; }
  .nav-filas { margin-left: auto; font-size: 12px; }
  .original { white-space: pre-wrap; font-size: 15px; line-height: 1.6; padding: 12px 14px; background: var(--panel-2); border-radius: 8px; border: 1px solid var(--borde); }
  textarea { resize: vertical; font-size: 15px; line-height: 1.55; min-height: 110px; }
  .estados, .botones { display: flex; gap: 6px; flex-wrap: wrap; }
  .botones .primario { margin-left: auto; }
  .aviso-conflicto { border: 1px solid var(--peligro); border-radius: 8px; padding: 10px 12px; display: grid; gap: 6px; font-size: 13px; }
  .atajos { font-size: 12px; margin: 0; }
</style>
