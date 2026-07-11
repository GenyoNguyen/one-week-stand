<script>
  import { PROPERTIES, COMPARE_MODES, HORIZONS, DATA_ASOF, DATA_SOURCE } from '../lib/constants.js';
  import { propertyFilter, selectedProperty, horizon, compareMode, currentView } from '../lib/stores.js';
  import { dashboardMetadataStore } from '../lib/dashboard-store.js';

  const env = import.meta.env || {};
  const demoMode = env.VITE_DASHBOARD_DEMO === 'true' || env.VITE_DEMO_MODE === 'true';

  // only show controls that actually apply to the current view — a visible
  // 30/60/90 switch on views that ignore it teaches users the wrong model
  $: showHorizon = $currentView === 'forecast';
  $: propertyOptions = $dashboardMetadataStore?.properties?.length
    ? $dashboardMetadataStore.properties
    : PROPERTIES;
  $: if (
    $dashboardMetadataStore?.properties?.length
    && $propertyFilter !== 'ALL'
    && !propertyOptions.some((property) => property.id === $propertyFilter)
  ) {
    propertyFilter.set('ALL');
  }
  $: freshnessPrefix = $dashboardMetadataStore?.asOfBasis === 'forecast_job_submission_time'
    ? 'Uploaded'
    : 'Data to';
  $: freshness = $dashboardMetadataStore
    ? `${freshnessPrefix} ${new Intl.DateTimeFormat('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        timeZone: $dashboardMetadataStore.timezone || 'Asia/Ho_Chi_Minh'
      }).format($dashboardMetadataStore.asOf)} · ${$dashboardMetadataStore.sourceLabel} · ${$dashboardMetadataStore.currency}`
    : demoMode
      ? `Data to ${DATA_ASOF} · ${DATA_SOURCE}`
      : 'No dashboard result selected';

  // property is ONE state: every control that picks a property writes both
  // stores, so the global select and the Property-view tabs never disagree
  function onPropChange(e) {
    if (e.target.value !== 'ALL') selectedProperty.set(e.target.value);
  }
</script>

<div class="bar">
  <div class="group">
    <select class="prop" bind:value={$propertyFilter} on:change={onPropChange} aria-label="Property">
      <option value="ALL">All properties</option>
      {#each propertyOptions as p}
        <option value={p.id}>{p.name}</option>
      {/each}
    </select>

    {#if showHorizon}
      <div class="pills" role="group" aria-label="Horizon">
        {#each HORIZONS as h}
          <button class:active={$horizon === h} on:click={() => horizon.set(h)}>{h}d</button>
        {/each}
      </div>
    {/if}

    <div class="pills" role="group" aria-label="Comparison">
      {#each COMPARE_MODES as m}
        <button class:active={$compareMode === m.id} on:click={() => compareMode.set(m.id)}>
          {m.label}
        </button>
      {/each}
    </div>
  </div>

  <div class="fresh num">{freshness}</div>
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
    background: color-mix(in srgb, var(--panel) 92%, transparent);
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
    box-shadow: var(--shadow-card);
  }
  /* shadcn-style segmented control: muted track, raised active thumb */
  .pills {
    display: inline-flex;
    gap: 2px;
    border: 1px solid var(--hairline);
    border-radius: var(--radius);
    padding: 2px;
    background: var(--panel-tint);
  }
  .pills button {
    border: none;
    background: none;
    border-radius: calc(var(--radius) - 2px);
    padding: 4px 11px;
    font-size: 12.5px;
    font-weight: 500;
    color: var(--ink-2);
  }
  .pills button.active {
    background: var(--panel);
    color: var(--gold-ink);
    font-weight: 600;
    box-shadow: var(--shadow-card);
  }
  .fresh {
    font-size: 11.5px;
    color: var(--ink-3);
    white-space: nowrap;
  }
</style>
