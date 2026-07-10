<script>
  import StackedBar from '../components/StackedBar.svelte';
  import { getSegments, getSegmentMix, getChannels, getNationalities } from '../lib/api.js';
  import { propertyFilter } from '../lib/stores.js';
  import { PROPERTIES, SEGMENTS, SERIES } from '../lib/constants.js';
  import {
    fmtPct,
    fmtInt,
    fmtMoneyFull,
    fmtMoney,
    fmtDelta,
    deltaClass,
    deltaArrow
  } from '../lib/formatters.js';

  let loading = true;
  let segs = [];
  let mixRows = [];
  let chans = [];
  let nats = [];

  let seq = 0; // drop stale responses if filters change mid-flight
  async function load(pid) {
    const my = ++seq;
    loading = true;
    const res = await Promise.all([getSegments(pid), getSegmentMix(), getChannels(), getNationalities()]);
    if (my !== seq) return;
    [segs, mixRows, chans, nats] = res;
    loading = false;
  }
  $: load($propertyFilter);

  $: scopeName =
    $propertyFilter === 'ALL'
      ? 'all properties'
      : PROPERTIES.find((p) => p.id === $propertyFilter)?.name;
  $: maxNat = Math.max(...nats.map((n) => n.share), 0.01);
</script>

<div class="view reveal">
  <header>
    <h1 class="view-title">Segments &amp; channels</h1>
    <p class="view-sub">Mix, value and cancellation behaviour · next 30 days on the books</p>
  </header>

  {#if loading}
    <div class="skeleton" style="height:160px"></div>
    <div class="skeleton" style="height:300px"></div>
  {:else}
    <section class="panel">
      <div class="panel-head"><h2 class="kicker">Segment mix by property</h2></div>
      <div class="panel-body mixes">
        {#each mixRows as row (row.property.id)}
          <div class="mix-row">
            <span class="mix-label">{row.property.short}</span>
            <div class="mix-bar">
              <StackedBar
                items={row.mix.map((m, i) => ({ label: m.segment, share: m.share, color: SERIES[i] }))}
                height={22}
              />
            </div>
          </div>
        {/each}
        <div class="legend">
          {#each SEGMENTS as s, i}
            <span><i style="background:{SERIES[i]}"></i>{s}</span>
          {/each}
        </div>
      </div>
    </section>

    <section class="two">
      <div class="panel">
        <div class="panel-head"><h2 class="kicker">By segment — {scopeName}</h2></div>
        <table class="data">
          <thead>
            <tr>
              <th>Segment</th>
              <th class="r">Room nights</th>
              <th class="r">ADR</th>
              <th class="r">Cxl rate</th>
              <th class="r">RN vs LY</th>
            </tr>
          </thead>
          <tbody>
            {#each segs as s, i (s.segment)}
              <tr>
                <td><span class="dot" style="background:{SERIES[i]}"></span>{s.segment}</td>
                <td class="r">{fmtInt(s.roomNights)}</td>
                <td class="r">{fmtMoneyFull(s.adr)}</td>
                <td class="r">{fmtPct(s.cxlRate)}</td>
                <td class="r">
                  <span class="delta {deltaClass(s.deltaLy)}">{deltaArrow(s.deltaLy)} {fmtDelta(s.deltaLy)}</span>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <div class="panel">
        <div class="panel-head">
          <h2 class="kicker">Top source markets — all properties</h2>
        </div>
        <div class="panel-body nats">
          {#each nats as n (n.name)}
            <div class="nat">
              <span class="nat-name">{n.name}</span>
              <div class="nat-track">
                <div class="nat-fill" style="width:{(n.share / maxNat) * 100}%"></div>
              </div>
              <span class="nat-share num">{fmtPct(n.share)}</span>
              <span class="delta {deltaClass(n.deltaLy)} nat-delta">
                {deltaArrow(n.deltaLy)}
                {fmtDelta(n.deltaLy)}
              </span>
            </div>
          {/each}
          <div class="foot">Share of forward room nights · Δ vs last year</div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head"><h2 class="kicker">By channel — all properties</h2></div>
      <table class="data">
        <thead>
          <tr>
            <th>Channel</th>
            <th class="r">Room nights</th>
            <th class="r">ADR</th>
            <th class="r">Revenue</th>
            <th class="r">Cxl rate (prev)</th>
            <th class="r">RN vs LY</th>
          </tr>
        </thead>
        <tbody>
          {#each chans as c (c.channel)}
            <tr>
              <td>{c.channel}</td>
              <td class="r">{fmtInt(c.roomNights)}</td>
              <td class="r">{fmtMoneyFull(c.adr)}</td>
              <td class="r">{fmtMoney(c.revenue)}</td>
              <td class="r">
                <span class:spike={c.cxlRate > c.cxlPrev * 1.5}>{fmtPct(c.cxlRate)}</span>
                <span class="muted">({fmtPct(c.cxlPrev)})</span>
              </td>
              <td class="r">
                <span class="delta {deltaClass(c.deltaLy)}">{deltaArrow(c.deltaLy)} {fmtDelta(c.deltaLy)}</span>
              </td>
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
  }
  .panel-body {
    padding: 4px 16px 14px;
  }
  .two {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
    gap: 12px;
    align-items: start;
  }
  .two .panel {
    min-width: 0;
  }
  .mixes {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .mix-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .mix-label {
    width: 76px;
    font-size: 12.5px;
    font-weight: 600;
    text-align: right;
    color: var(--ink-2);
  }
  .mix-bar {
    flex: 1;
  }
  .legend {
    display: flex;
    gap: 16px;
    margin-top: 4px;
    padding-left: 88px;
    font-size: 11.5px;
    color: var(--ink-2);
    flex-wrap: wrap;
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
  .dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 7px;
  }
  .muted {
    color: var(--ink-3);
    font-size: 11px;
  }
  .spike {
    color: var(--risk);
    font-weight: 700;
  }
  .nats {
    display: flex;
    flex-direction: column;
    gap: 7px;
  }
  .nat {
    display: grid;
    grid-template-columns: 110px 1fr 44px 62px;
    align-items: center;
    gap: 10px;
    font-size: 12.5px;
  }
  .nat-track {
    background: var(--panel-tint);
    border-radius: 2px;
    height: 12px;
  }
  .nat-fill {
    background: var(--accent);
    opacity: 0.85;
    height: 100%;
    border-radius: 2px;
  }
  .nat-share {
    text-align: right;
  }
  .nat-delta {
    font-size: 11.5px;
    text-align: right;
  }
  .foot {
    font-size: 11px;
    color: var(--ink-3);
    margin-top: 6px;
  }
</style>
