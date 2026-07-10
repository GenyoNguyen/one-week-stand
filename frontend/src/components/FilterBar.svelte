<script>
  import { PROPERTIES, COMPARE_MODES, HORIZONS, DATA_ASOF, DATA_SOURCE } from '../lib/constants.js';
  import { propertyFilter, horizon, compareMode } from '../lib/stores.js';
</script>

<div class="bar">
  <div class="group">
    <select class="prop" bind:value={$propertyFilter} aria-label="Property">
      <option value="ALL">All properties</option>
      {#each PROPERTIES as p}
        <option value={p.id}>{p.name}</option>
      {/each}
    </select>

    <div class="pills" role="group" aria-label="Horizon">
      {#each HORIZONS as h}
        <button class:active={$horizon === h} on:click={() => horizon.set(h)}>{h}d</button>
      {/each}
    </div>

    <div class="pills" role="group" aria-label="Comparison">
      {#each COMPARE_MODES as m}
        <button class:active={$compareMode === m.id} on:click={() => compareMode.set(m.id)}>
          {m.label}
        </button>
      {/each}
    </div>
  </div>

  <div class="fresh num">Data to {DATA_ASOF} · {DATA_SOURCE}</div>
</div>

<style>
  .bar {
    position: sticky;
    top: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 10px 28px;
    background: color-mix(in srgb, var(--paper) 88%, transparent);
    backdrop-filter: blur(6px);
    border-bottom: 1px solid var(--hairline);
  }
  .group {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  select.prop {
    font-family: inherit;
    font-size: 13px;
    font-weight: 500;
    color: var(--ink);
    background: var(--panel);
    border: 1px solid var(--hairline-strong);
    border-radius: var(--radius);
    padding: 5px 8px;
  }
  .pills {
    display: inline-flex;
    border: 1px solid var(--hairline-strong);
    border-radius: var(--radius);
    overflow: hidden;
    background: var(--panel);
  }
  .pills button {
    border: none;
    background: none;
    padding: 5px 11px;
    font-size: 12.5px;
    font-weight: 500;
    color: var(--ink-2);
  }
  .pills button + button {
    border-left: 1px solid var(--hairline);
  }
  .pills button.active {
    background: var(--accent-soft);
    color: var(--accent-ink);
    font-weight: 600;
  }
  .fresh {
    font-size: 11.5px;
    color: var(--ink-3);
    white-space: nowrap;
  }
</style>
