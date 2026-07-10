<script>
  import KpiCard from '../components/KpiCard.svelte';
  import ForecastChart from '../components/ForecastChart.svelte';
  import PropertyTable from '../components/PropertyTable.svelte';
  import RecommendationPanel from '../components/RecommendationPanel.svelte';
  import { getSeries, getAlerts } from '../lib/api.js';
  import { propertyFilter, compareMode, navigate, selectedProperty } from '../lib/stores.js';
  import { PROPERTIES, TODAY } from '../lib/constants.js';
  import {
    fmtPct,
    fmtMoneyFull,
    fmtMoney,
    fmtInt,
    fmtDelta,
    fmtDateFull,
    deltaClass,
    deltaArrow
  } from '../lib/formatters.js';

  let loading = true;
  let today = null;
  let hist = [];
  let outlook = [];
  let alerts = [];
  let propRows = [];

  const SEV_ORDER = { risk: 0, watch: 1, opportunity: 2 };

  let seq = 0; // drop stale responses if filters change mid-flight
  async function load(pid, cmp) {
    const my = ++seq;
    loading = true;
    const [t, h, o, al, ...perProp] = await Promise.all([
      getSeries(pid, 0, 0),
      getSeries(pid, -13, 0),
      getSeries(pid, 1, 30),
      getAlerts(),
      ...PROPERTIES.map((p) => Promise.all([getSeries(p.id, 0, 0), getSeries(p.id, 1, 30)]))
    ]);
    if (my !== seq) return;
    today = t[0];
    hist = h;
    outlook = o;
    alerts = al;
    propRows = perProp.map(([tp, next], i) => {
      const d = tp[0];
      const cmpRevpar = cmp === 'budget' ? d.budgetOcc * d.budgetAdr : d.lyOcc * d.lyAdr;
      return {
        property: PROPERTIES[i],
        occ: d.occ,
        adr: d.adr,
        revpar: d.revpar,
        pu7: next.reduce((s, r) => s + r.pu7, 0),
        delta: (d.revpar - cmpRevpar) / cmpRevpar
      };
    });
    loading = false;
  }
  $: load($propertyFilter, $compareMode);

  $: scopeName =
    $propertyFilter === 'ALL'
      ? 'Portfolio'
      : PROPERTIES.find((p) => p.id === $propertyFilter)?.name;

  $: heroBudget = today ? (today.revpar - today.budgetOcc * today.budgetAdr) / (today.budgetOcc * today.budgetAdr) : 0;
  $: heroLy = today ? (today.revpar - today.lyOcc * today.lyAdr) / (today.lyOcc * today.lyAdr) : 0;

  $: cmpOcc = today ? ($compareMode === 'budget' ? today.budgetOcc : today.lyOcc) : 0;
  $: cmpAdr = today ? ($compareMode === 'budget' ? today.budgetAdr : today.lyAdr) : 0;
  $: cmpLabel = $compareMode === 'budget' ? 'vs budget' : 'vs last year';

  $: pickup24 = outlook.reduce((s, r) => s + r.pu1, 0);
  $: pickupDayAvg7 = outlook.reduce((s, r) => s + r.pu7, 0) / 7;
  $: rev30 = outlook.reduce((s, r) => s + r.revenue, 0);
  $: budgetRev30 = outlook.reduce((s, r) => s + r.budgetOcc * r.capacity * r.budgetAdr, 0);

  $: needsAttention = alerts
    .filter((a) => $propertyFilter === 'ALL' || a.property === $propertyFilter || a.property === 'ALL')
    .sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity])
    .slice(0, 3);

  function openProperty(id) {
    selectedProperty.set(id);
    navigate('property');
  }
</script>

<div class="view reveal">
  <header class="head">
    <div>
      <h1 class="view-title">Daily overview</h1>
      <p class="view-sub">{scopeName} position · {fmtDateFull(TODAY)}</p>
    </div>
  </header>

  {#if loading}
    <div class="skeleton" style="height:132px"></div>
    <div class="skeleton" style="height:320px"></div>
  {:else}
    <section class="hero-band">
      <div class="hero panel">
        <div class="kicker">RevPAR tonight</div>
        <div class="hero-num num">{fmtMoneyFull(today.revpar)}</div>
        <div class="hero-deltas">
          <span class="delta {deltaClass(heroBudget)}">{deltaArrow(heroBudget)} {fmtDelta(heroBudget)} vs budget</span>
          <span class="delta {deltaClass(heroLy)}">{deltaArrow(heroLy)} {fmtDelta(heroLy)} vs last year</span>
        </div>
      </div>

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
        label="Pickup last 24h"
        value={`${fmtInt(pickup24)} rm`}
        delta={(pickup24 - pickupDayAvg7) / pickupDayAvg7}
        deltaLabel="vs 7-day avg"
        spark={outlook.slice(0, 14).map((d) => d.pu1)}
        sparkCaption="next 14 stay dates"
      />
      <KpiCard
        label="Revenue OTB, next 30 days"
        value={fmtMoney(rev30)}
        delta={(rev30 - budgetRev30) / budgetRev30}
        deltaLabel="vs budget"
        spark={outlook.map((d) => d.revenue)}
        sparkCaption="by stay date"
      />
    </section>

    <section class="grid">
      <div class="panel main">
        <div class="panel-head">
          <h2 class="kicker">Occupancy outlook — next 30 days</h2>
        </div>
        <div class="panel-body">
          <ForecastChart
            data={outlook}
            compare={$compareMode}
            height={252}
            label="{scopeName} occupancy outlook for the next 30 days"
          />
        </div>
      </div>

      <aside class="side">
        <div class="side-head">
          <h2 class="kicker">Needs attention</h2>
          <button class="linkish" on:click={() => navigate('alerts')}>Review &amp; act →</button>
        </div>
        {#each needsAttention as a (a.id)}
          <RecommendationPanel alert={a} compact />
        {/each}
      </aside>
    </section>

    <section class="panel props">
      <div class="panel-head">
        <h2 class="kicker">By property — tonight</h2>
      </div>
      <PropertyTable rows={propRows} compareLabel={cmpLabel} on:select={(e) => openProperty(e.detail)} />
    </section>
  {/if}
</div>

<style>
  .view {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .hero-band {
    display: grid;
    grid-template-columns: minmax(0, 1.35fr) repeat(4, minmax(0, 1fr));
    gap: 12px;
  }
  .hero {
    padding: 14px 18px;
    background: var(--sidebar);
    border-color: var(--sidebar);
    color: var(--sidebar-ink);
  }
  .hero .kicker {
    color: var(--sidebar-muted);
  }
  .hero-num {
    font-family: var(--font-display);
    font-size: 46px;
    font-weight: 500;
    line-height: 1.1;
    letter-spacing: -0.01em;
    margin: 4px 0 6px;
  }
  .hero-deltas {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 12.5px;
  }
  .hero .delta.pos {
    color: #79c9a2;
  }
  .hero .delta.neg {
    color: #e88f84;
  }
  .grid {
    display: grid;
    grid-template-columns: minmax(0, 2.1fr) minmax(300px, 1fr);
    gap: 12px;
    align-items: start;
  }
  .panel-head {
    padding: 12px 16px 0;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .panel-body {
    padding: 8px 16px 14px;
  }
  .side {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .side-head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 0 2px;
  }
  .linkish {
    background: none;
    border: none;
    color: var(--accent-ink);
    font-size: 12px;
    font-weight: 600;
    padding: 0;
  }
  .props {
    padding-bottom: 4px;
  }
  .props .panel-head {
    padding-bottom: 8px;
  }
</style>
