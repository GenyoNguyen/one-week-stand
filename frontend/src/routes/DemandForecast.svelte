<script>
  import { get } from 'svelte/store';
  import ForecastChart from '../components/ForecastChart.svelte';
  import DashboardDataState from '../components/DashboardDataState.svelte';
  import { getSeries } from '../lib/api.js';
  import { activeDashboard, invalidateDashboard } from '../lib/dashboard-store.js';
  import { propertyFilter, horizon, compareMode } from '../lib/stores.js';
  import { PROPERTIES } from '../lib/constants.js';
  import {
    fmtPct,
    fmtInt,
    fmtDate,
    fmtDow,
    isWeekend,
    fmtPts,
    deltaClass,
    deltaArrow
  } from '../lib/formatters.js';

  let loading = true;
  let big = [];
  let perProp = [];
  let showAllRows = false;
  let loadError = null;
  let propertyDefinitions = PROPERTIES;

  let seq = 0; // drop stale responses if filters change mid-flight
  async function load(pid, h) {
    const my = ++seq;
    loading = true;
    loadError = null;
    try {
      const b = await getSeries(pid, 1, h);
      const resultProperties = get(activeDashboard).dashboard?.metadata?.properties;
      propertyDefinitions = resultProperties?.length ? resultProperties : PROPERTIES;
      const rest = pid === 'ALL'
        ? await Promise.all(propertyDefinitions.map((property) => getSeries(property.id, 1, h)))
        : [];
      if (my !== seq) return;
      big = b;
      perProp = pid === 'ALL' ? rest : [];
    } catch (error) {
      if (my !== seq) return;
      loadError = error;
      big = [];
      perProp = [];
      propertyDefinitions = PROPERTIES;
    } finally {
      if (my === seq) loading = false;
    }
  }
  $: load($propertyFilter, $horizon);

  $: scopeName =
    $propertyFilter === 'ALL'
      ? 'All properties'
      : propertyDefinitions.find((p) => p.id === $propertyFilter)?.name || $propertyFilter;

  $: cmpKey = $compareMode === 'budget' ? 'budgetOcc' : 'lyOcc';
  $: cmpLabel = $compareMode === 'budget' ? 'Budget' : 'Last year';

  $: rows = showAllRows ? big : big.slice(0, 14);
  $: hasPointForecast = big.some((row) => Number.isFinite(row.fcOcc));
  $: hasIntervals = big.some(
    (row) =>
      Number.isFinite(row.fcLo80) &&
      Number.isFinite(row.fcHi80) &&
      Number.isFinite(row.fcLo50) &&
      Number.isFinite(row.fcHi50)
  );

  function retry() {
    invalidateDashboard();
    void load($propertyFilter, $horizon);
  }
</script>

<div class="view reveal">
  <header>
    <h1 class="view-title">Demand forecast</h1>
    <p class="view-sub">
      {scopeName} · next {$horizon} days by stay date
      {hasPointForecast ? hasIntervals ? ' · bands show 50% and 80% forecast intervals' : '' : ' · OTB snapshot; numeric point forecast unavailable'}
    </p>
  </header>

  {#if loading}
    <div class="skeleton" style="height:360px"></div>
  {:else if loadError}
    <DashboardDataState error={loadError} onRetry={retry} />
  {:else if !big.length}
    <DashboardDataState empty />
  {:else}
    {#if !hasPointForecast}
      <div class="availability-note" role="status">
        This MiroFish result does not contain a source-supported numeric point forecast. The charts show the uploaded OTB snapshot against {$compareMode === 'budget' ? 'budget' : 'last year'}; narrative predictions and evidence remain available in the generated report.
      </div>
    {/if}
    <section class="panel">
      <div class="panel-body">
        <ForecastChart
          data={big}
          compare={$compareMode}
          height={320}
          label="{scopeName} OTB occupancy outlook for the next {$horizon} days"
        />
      </div>
    </section>

    {#if perProp.length}
      <section class="multiples">
        {#each propertyDefinitions as p, i}
          <div class="panel small">
            <div class="small-head">
              <span class="dot" style="background:{p.color}"></span>
              {p.name}
            </div>
            <ForecastChart
              data={perProp[i]}
              compare={$compareMode}
              height={140}
              compact
              accent={p.color}
              label="{p.name} OTB occupancy outlook, next {$horizon} days"
            />
          </div>
        {/each}
      </section>
      <p class="encodings">
        Same encodings as the main chart: solid ink = on the books{hasPointForecast ? ' · dashed (property colour) = forecast' : ''}{hasIntervals ? ' · shaded = 50/80% bands' : ''} · gray = {$compareMode === 'budget' ? 'budget' : 'last year'}
      </p>
    {/if}

    <section class="panel">
      <div class="panel-head">
        <h2 class="kicker">{hasPointForecast ? 'Forecast' : 'OTB position'} detail by stay date</h2>
        <button class="linkish" on:click={() => (showAllRows = !showAllRows)}>
          {showAllRows ? 'Show first 14 days' : `Show all ${big.length} days`}
        </button>
      </div>
      <table class="data">
        <thead>
          <tr>
            <th>Stay date</th>
            <th class="r">OTB rooms</th>
            <th class="r">OTB occ</th>
            {#if hasPointForecast}<th class="r">Forecast</th>{/if}
            {#if hasIntervals}<th class="r">80% band</th>{/if}
            <th class="r">{cmpLabel}</th>
            {#if hasPointForecast}<th class="r">Forecast vs {cmpLabel.toLowerCase()}</th>{/if}
            <th class="r">Source pickup</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as r (r.date)}
            <tr class:wknd={isWeekend(r.date)}>
              <td>{fmtDow(r.date)} {fmtDate(r.date)}</td>
              <td class="r">{fmtInt(r.roomsSold)}</td>
              <td class="r">{fmtPct(r.occ)}</td>
              {#if hasPointForecast}<td class="r"><b>{fmtPct(r.fcOcc)}</b></td>{/if}
              {#if hasIntervals}<td class="r muted">{fmtPct(r.fcLo80)}–{fmtPct(r.fcHi80)}</td>{/if}
              <td class="r muted">{fmtPct(r[cmpKey])}</td>
              {#if hasPointForecast}
                <td class="r">
                  <span class="delta {deltaClass(r.fcOcc - r[cmpKey])}">
                    {deltaArrow(r.fcOcc - r[cmpKey])}
                    {fmtPts(r.fcOcc - r[cmpKey])}
                  </span>
                </td>
              {/if}
              <td class="r">{fmtInt(r.pu7)} rm</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}
</div>

<style>
  .view {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .panel-head {
    padding: 12px 16px 8px;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .availability-note {
    padding: 10px 14px;
    border: 1px solid var(--hairline-strong);
    border-radius: var(--radius);
    background: var(--gold-soft);
    color: var(--ink-2);
    font-size: 12.5px;
  }
  .panel-body {
    padding: 14px 16px;
  }
  .multiples {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }
  .small {
    padding: 12px 14px;
    min-width: 0;
  }
  .small-head {
    font-size: 12.5px;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .encodings {
    margin: -8px 0 0;
    font-size: 11.5px;
    color: var(--ink-3);
  }
  .dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
  }
  .linkish {
    background: none;
    border: none;
    color: var(--gold-ink);
    font-size: 12px;
    font-weight: 600;
    padding: 0;
  }
  td.muted {
    color: var(--ink-3);
  }
  tr.wknd td {
    background: color-mix(in srgb, var(--panel-tint) 55%, transparent);
  }
</style>
