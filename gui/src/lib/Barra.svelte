<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
<!-- Barra apilada con la proporción de filas en cada estado. -->
<script>
  import { COLOR_ESTADO } from "./estado.svelte.js";
  let { estados = {}, alto = 8 } = $props();
  const ORDEN = ["traducido", "del parche", "revisar", "sin traducir"];
  let total = $derived(Object.values(estados).reduce((a, b) => a + b, 0));
</script>

<div class="barra" style:height="{alto}px" title={ORDEN.filter((e) => estados[e]).map((e) => `${e}: ${estados[e]}`).join(" · ")}>
  {#each ORDEN as e}
    {#if estados[e]}<div style:width="{(100 * estados[e]) / total}%" style:background={COLOR_ESTADO[e]}></div>{/if}
  {/each}
</div>

<style>
  .barra { display: flex; border-radius: 999px; overflow: hidden; background: var(--panel-2); min-width: 40px; gap: 1px; }
</style>
