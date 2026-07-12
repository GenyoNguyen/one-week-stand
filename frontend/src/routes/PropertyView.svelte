<script>
  import KpiCard from '../components/KpiCard.svelte';
  import PaceChart from '../components/PaceChart.svelte';
  import Heatmap from '../components/Heatmap.svelte';
  import DonutChart from '../components/DonutChart.svelte';
  import DashboardDataState from '../components/DashboardDataState.svelte';
  import { getSeries, getPaceCurve, getPickupCalendar, getSegmentMix } from '../lib/api.js';
  import { dashboardMetadataStore, invalidateDashboard } from '../lib/dashboard-store.js';
  import { selectedProperty, propertyFilter, compareMode } from '../lib/stores.js';
  import { PROPERTIES, SERIES } from '../lib/constants.js';
  import { fmtPct, fmtMoneyFull, fmtInt, fmtDate } from '../lib/formatters.js';

  let loading = true;
  let today = null;
  let hist = [];
  let next30 = [];
  let pace = null;
  let calendar = [];
  let mix = [];
  let loadError = null;

  function sumAvailable(rows, key) {
    const values = rows.map((row) => row[key]).filter(Number.isFinite);
    return values.length ? values.reduce((sum, value) => sum + value, 0) : null;
  }

  // property is ONE state across the app: the tabs write both stores, so the
  // global select can never disagree with the heading (review round 2)
  function pick(id) {
    selectedProperty.set(id);
    propertyFilter.set(id);
  }

  let seq = 0; // drop stale responses if the property changes mid-flight
  async function load(pid) {
    const my = ++seq;
    loading = true;
    loadError = null;
    try {
      const [t, h, n, pc, cal, mixAll] = await Promise.all([
        getSeries(pid, 0, 0),
        getSeries(pid, -13, 0),
        getSeries(pid, 1, 30),
        getPaceCurve(pid),
        getPickupCalendar(pid),
        getSegmentMix()
      ]);
      if (my !== seq) return;
      if (!t.length) throw new Error('This property has no performance row for the forecast as-of date.');
      today = t[0];
      hist = h;
      next30 = n;
      pace = pc;
      calendar = cal;
      mix = mixAll.find((m) => m.property.id === pid)?.mix ?? [];
    } catch (error) {
      if (my !== seq) return;
      loadError = error;
      today = null;
      hist = [];
      next30 = [];
      pace = null;
      calendar = [];
      mix = [];
    } finally {
      if (my === seq) loading = false;
    }
  }
  $: load($selectedProperty);

  $: propertyDefinitions = $dashboardMetadataStore?.properties?.length
    ? $dashboardMetadataStore.properties
    : PROPERTIES;
  $: prop = propertyDefinitions.find((p) => p.id === $selectedProperty) || propertyDefinitions[0];
  $: if (
    $dashboardMetadataStore?.properties?.length
    && !propertyDefinitions.some((property) => property.id === $selectedProperty)
  ) {
    selectedProperty.set(propertyDefinitions[0].id);
    propertyFilter.set(propertyDefinitions[0].id);
  }
  $: cmpOcc = today ? ($compareMode === 'budget' ? today.budgetOcc : today.lyOcc) : 0;
  $: cmpAdr = today ? ($compareMode === 'budget' ? today.budgetAdr : today.lyAdr) : 0;
  $: cmpLabel = $compareMode === 'budget' ? 'vs budget' : 'vs last year';
  $: otbRn30 = next30.reduce((s, r) => s + r.roomsSold, 0);
  $: pickupSnapshotNext30 = sumAvailable(next30, 'pu7');
  $: cancellationsNext30 = sumAvailable(next30, 'cxl7');

  function retry() {
    invalidateDashboard();
    void load($selectedProperty);
  }
</script>

<div class="view reveal">
  <header class="head">
    <div>
      <h1 class="view-title">{prop.name}</h1>
      <p class="view-sub">{prop.rooms} keys · property deep-dive</p>
    </div>
    <div class="tabs" role="tablist">
      {#each propertyDefinitions as p}
        <button
          role="tab"
          aria-selected={p.id === $selectedProperty}
          class:active={p.id === $selectedProperty}
          on:click={() => pick(p.id)}
        >
          <span class="dot" style="background:{p.color}"></span>{p.short}
        </button>
      {/each}
    </div>
  </header>

  {#if loading}
    <div class="skeleton" style="height:120px"></div>
    <div class="skeleton" style="height:300px"></div>
  {:else if loadError}
    <DashboardDataState error={loadError} onRetry={retry} />
  {:else}
    <section class="kpis">
      <KpiCard
        label="Occupancy tonight"
        value={fmtPct(today.occ)}
        delta={(today.occ - cmpOcc) / cmpOcc}
        deltaLabel={cmpLabel}
        spark={hist.map((d) => d.occ)}
      />
      <KpiCard
        label="ADR tonight"
        value={fmtMoneyFull(today.adr)}
        delta={(today.adr - cmpAdr) / cmpAdr}
        deltaLabel={cmpLabel}
        spark={hist.map((d) => d.adr)}
      />
      <KpiCard
        label="Source pickup, next 30 stay dates"
        value={`${fmtInt(pickupSnapshotNext30)} rm`}
        spark={pickupSnapshotNext30 === null ? null : next30.map((d) => d.pu7).filter(Number.isFinite)}
        sparkCaption="uploaded measure by stay date"
      />
      <KpiCard
        label="Source cancellations, next 30 stay dates"
        value={`${fmtInt(cancellationsNext30)} rm`}
        goodWhenUp={false}
        spark={cancellationsNext30 === null ? null : next30.map((d) => d.cxl7).filter(Number.isFinite)}
        sparkCaption="reporting-day counts by stay date"
      />
    </section>

    <section class="grid">
      <div class="col">
        {#if pace?.points?.length}
        <div class="panel">
          <div class="panel-head"><h2 class="kicker">Booking pace {pace.isSnapshot ? 'snapshot' : 'curve'} — {pace.monthLabel}</h2></div>
          <div class="panel-body">
            <PaceChart
              points={pace.points}
              currentWeeksOut={pace.currentWeeksOut}
              monthLabel={pace.monthLabel}
              snapshot={pace.isSnapshot}
            />
            <details class="fallback">
            <summary>View as table</summary>
            <table class="data">
              <thead>
                <tr>
                  <th>{pace.isSnapshot ? 'Arrival lead' : 'Weeks out'}</th>
                  <th class="r">{pace.isSnapshot ? 'OTB, RN' : 'This year, RN'}</th>
                  <th class="r">{pace.isSnapshot ? 'STLY OTB, RN' : 'Last year, RN'}</th>
                </tr>
              </thead>
              <tbody>
                {#each pace.points.filter((p) => p.weeksOut % 2 === 0) as p (p.weeksOut)}
                  <tr>
                    <td>{p.weeksOut === 0 ? 'Arrival' : `${p.weeksOut}w`}</td>
                    <td class="r">{p.ty == null ? '—' : fmtInt(p.ty)}</td>
                    <td class="r">{fmtInt(p.ly)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
            </details>
          </div>
        </div>
        {:else}
          <DashboardDataState empty />
        {/if}

        <div class="panel">
          <div class="panel-head"><h2 class="kicker">Segment mix — next 30 days on the books</h2></div>
          <div class="panel-body mix-body">
            <DonutChart
              items={mix.map((m, i) => ({ label: m.segment, share: m.share, color: SERIES[i] }))}
              size={164}
              thickness={25}
              centerValue="{fmtInt(otbRn30)} rn"
              centerLabel="on the books"
              ariaLabel="{prop.name} segment mix for the next 30 days on the books"
            />
            <div class="legend mix-legend">
              {#each mix as m, i}
                <span><i style="background:{SERIES[i]}"></i>{m.segment} <b class="num">{fmtPct(m.share)}</b></span>
              {/each}
            </div>
            <details class="fallback mix-fallback">
              <summary>View as table</summary>
              <table class="data">
                <thead>
                  <tr>
                    <th>Segment</th>
                    <th class="r">Share</th>
                    <th class="r">Room nights</th>
                  </tr>
                </thead>
                <tbody>
                  {#each mix as m (m.segment)}
                    <tr>
                      <td>{m.segment}</td>
                      <td class="r">{fmtPct(m.share)}</td>
                      <td class="r">{fmtInt(m.share * otbRn30)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </details>
          </div>
        </div>
      </div>

      <div class="panel heat">
        <div class="panel-head"><h2 class="kicker">Source pickup by stay date</h2></div>
        <div class="panel-body">
          {#if calendar.length}
            <Heatmap cells={calendar} />
            <details class="fallback">
            <summary>View as table</summary>
            <table class="data">
              <thead>
                <tr>
                  <th>Stay date</th>
                  <th class="r">Uploaded pickup</th>
                </tr>
              </thead>
              <tbody>
                {#each calendar as c (c.date)}
                  <tr>
                    <td>{fmtDate(c.date)}</td>
                    <td class="r">{fmtInt(c.pu7)} rm</td>
                  </tr>
                {/each}
              </tbody>
            </table>
            </details>
          {:else}
            <p class="unavailable">Pickup is not available in this result.</p>
          {/if}
        </div>
      </div>
    </section>
  {/if}
</div>

<style>
  .view {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .unavailable {
    margin: 0;
    color: var(--ink-3);
    font-size: 12.5px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    flex-wrap: wrap;
  }
  .tabs {
    display: inline-flex;
    gap: 2px;
    border: 1px solid var(--hairline);
    border-radius: var(--radius);
    padding: 2px;
    background: var(--panel-tint);
  }
  .tabs button {
    border: none;
    background: none;
    border-radius: calc(var(--radius) - 2px);
    padding: 5px 14px;
    font-size: 12.5px;
    font-weight: 500;
    color: var(--ink-2);
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .tabs button.active {
    background: var(--panel);
    color: var(--gold-ink);
    font-weight: 600;
    box-shadow: var(--shadow-card);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    display: inline-block;
  }
  .kpis {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }
  .grid {
    display: grid;
    grid-template-columns: minmax(0, 1.5fr) minmax(0, 1fr);
    gap: 12px;
    align-items: stretch; /* columns share one bottom edge */
  }
  .grid .panel {
    min-width: 0;
  }
  .heat {
    display: flex;
    flex-direction: column;
  }
  .heat .panel-body {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  .heat .fallback {
    margin-top: auto; /* pin the table link to the panel's bottom */
  }
  /* left column stacks pace + segment mix to balance the tall heatmap */
  .col {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 0;
  }
  .panel-head {
    padding: 12px 16px 0;
  }
  .panel-body {
    padding: 10px 16px 14px;
  }
  .mix-body {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 44px;
    flex-wrap: wrap;
    padding-top: 6px;
    padding-bottom: 12px;
  }
  .legend {
    display: flex;
    gap: 16px;
    margin-top: 10px;
    font-size: 11.5px;
    color: var(--ink-2);
    flex-wrap: wrap;
  }
  .mix-legend {
    margin-top: 0;
    flex-direction: column;
    gap: 8px;
    font-size: 12.5px;
  }
  /* full-width row beneath the donut + legend (mix-body wraps) */
  .mix-fallback {
    flex-basis: 100%;
    margin-top: 0;
  }
  .mix-fallback table {
    max-width: 340px;
    margin: 8px auto 0;
  }
  .legend span {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .legend i {
    width: 9px;
    height: 9px;
    border-radius: 2px;
    display: inline-block;
  }
  .fallback {
    margin-top: 10px;
  }
  .fallback summary {
    font-size: 11.5px;
    color: var(--gold-ink);
    font-weight: 600;
    cursor: pointer;
  }
  .fallback table {
    margin-top: 8px;
    max-width: 340px;
  }
</style>
