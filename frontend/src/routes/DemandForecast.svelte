<script>
  import ForecastChart from '../components/ForecastChart.svelte';
  import { getSeries } from '../lib/api.js';
  import { propertyFilter, horizon, compareMode } from '../lib/stores.js';
  import { PROPERTIES } from '../lib/constants.js';
  import {
    fmtPct,
    fmtInt,
    fmtDate,
    fmtDow,
    isWeekend,
    fmtDelta,
    deltaClass,
    deltaArrow
  } from '../lib/formatters.js';

  let loading = true;
  let big = [];
  let perProp = [];
  let showAllRows = false;

  async function load(pid, h) {
    loading = true;
    const jobs = [getSeries(pid, 1, h)];
    if (pid === 'ALL') for (const p of PROPERTIES) jobs.push(getSeries(p.id, 1, h));
    const [b, ...rest] = await Promise.all(jobs);
    big = b;
    perProp = pid === 'ALL' ? rest : [];
    loading = false;
  }
  $: load($propertyFilter, $horizon);

  $: scopeName =
    $propertyFilter === 'ALL'
      ? 'All properties'
      : PROPERTIES.find((p) => p.id === $propertyFilter)?.name;

  $: cmpKey = $compareMode === 'budget' ? 'budgetOcc' : 'lyOcc';
  $: cmpLabel = $compareMode === 'budget' ? 'Budget' : 'Last year';

  $: rows = showAllRows ? big : big.slice(0, 14);
</script>

<div class="view reveal">
  <header>
    <h1 class="view-title">Demand forecast</h1>
    <p class="view-sub">
      {scopeName} · next {$horizon} days by stay date · bands show 50% and 80% forecast intervals
    </p>
  </header>

  {#if loading}
    <div class="skeleton" style="height:360px"></div>
  {:else}
    <section class="panel">
      <div class="panel-body">
        <ForecastChart data={big} compare={$compareMode} height={320} />
      </div>
    </section>

    {#if perProp.length}
      <section class="multiples">
        {#each PROPERTIES as p, i}
          <div class="panel small">
            <div class="small-head">
              <span class="dot" style="background:{p.color}"></span>
              {p.name}
            </div>
            <ForecastChart data={perProp[i]} compare={$compareMode} height={140} compact />
          </div>
        {/each}
      </section>
    {/if}

    <section class="panel">
      <div class="panel-head">
        <h2 class="kicker">Forecast detail by stay date</h2>
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
            <th class="r">Forecast</th>
            <th class="r">80% band</th>
            <th class="r">{cmpLabel}</th>
            <th class="r">Gap to forecast</th>
            <th class="r">Pickup 7d</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as r (r.date)}
            <tr class:wknd={isWeekend(r.date)}>
              <td>{fmtDow(r.date)} {fmtDate(r.date)}</td>
              <td class="r">{fmtInt(r.roomsSold)}</td>
              <td class="r">{fmtPct(r.occ)}</td>
              <td class="r"><b>{fmtPct(r.fcOcc)}</b></td>
              <td class="r muted">{fmtPct(r.fcLo80)}–{fmtPct(r.fcHi80)}</td>
              <td class="r muted">{fmtPct(r[cmpKey])}</td>
              <td class="r">
                <span class="delta {deltaClass(r.fcOcc - r[cmpKey])}">
                  {deltaArrow(r.fcOcc - r[cmpKey])}
                  {fmtDelta(r.fcOcc - r[cmpKey], { digits: 1 })} pts
                </span>
              </td>
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
    color: var(--accent-ink);
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
