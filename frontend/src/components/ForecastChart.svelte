<script>
  import { scaleTime, scaleLinear } from 'd3-scale';
  import { line as d3line, area as d3area, curveMonotoneX } from 'd3-shape';
  import { GRAY_CONTEXT } from '../lib/constants.js';
  import { fmtDate, fmtDateFull, fmtPct } from '../lib/formatters.js';

  export let data = []; // [{date, occ(OTB), fcOcc, fcLo80, fcHi80, fcLo50, fcHi50, budgetOcc, lyOcc}]
  export let compare = 'budget';
  export let height = 300;
  export let compact = false;

  let width = 600;
  let hover = null; // {x, point}

  $: m = compact
    ? { top: 8, right: 20, bottom: 20, left: 34 }
    : { top: 12, right: 18, bottom: 26, left: 40 };
  $: iw = width - m.left - m.right;
  $: ih = height - m.top - m.bottom;

  $: x = scaleTime()
    .domain([data[0]?.date ?? new Date(), data[data.length - 1]?.date ?? new Date()])
    .range([0, iw]);
  $: y = scaleLinear().domain([0, 1]).range([ih, 0]);

  $: compareKey = compare === 'budget' ? 'budgetOcc' : 'lyOcc';

  $: band80 = d3area()
    .x((d) => x(d.date))
    .y0((d) => y(d.fcLo80))
    .y1((d) => y(d.fcHi80))
    .curve(curveMonotoneX)(data);
  $: band50 = d3area()
    .x((d) => x(d.date))
    .y0((d) => y(d.fcLo50))
    .y1((d) => y(d.fcHi50))
    .curve(curveMonotoneX)(data);
  $: fcLine = d3line()
    .x((d) => x(d.date))
    .y((d) => y(d.fcOcc))
    .curve(curveMonotoneX)(data);
  $: otbLine = d3line()
    .x((d) => x(d.date))
    .y((d) => y(d.occ))
    .curve(curveMonotoneX)(data);
  $: cmpLine = d3line()
    .x((d) => x(d.date))
    .y((d) => y(d[compareKey]))
    .curve(curveMonotoneX)(data);

  $: ticks = x.ticks(compact ? 3 : Math.min(8, Math.ceil(data.length / 7)));

  function onMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left - m.left;
    if (px < 0 || px > iw || !data.length) return (hover = null);
    const t = x.invert(px).getTime();
    let best = data[0];
    for (const d of data) if (Math.abs(d.date - t) < Math.abs(best.date - t)) best = d;
    hover = { x: x(best.date), point: best };
  }
</script>

<div class="wrap" bind:clientWidth={width} style="height:{height}px">
  <svg {width} {height} on:mousemove={onMove} on:mouseleave={() => (hover = null)} role="img">
    <g transform="translate({m.left},{m.top})">
      <!-- y grid -->
      {#each [0.25, 0.5, 0.75, 1] as v}
        <line x1="0" x2={iw} y1={y(v)} y2={y(v)} class="grid" />
        <text x="-8" y={y(v)} dy="3" class="tick r">{v * 100}%</text>
      {/each}
      <line x1="0" x2={iw} y1={y(0)} y2={y(0)} class="axis" />

      <!-- confidence bands: two discrete opacity steps, no gradient -->
      <path d={band80} class="band b80" />
      <path d={band50} class="band b50" />

      <!-- reference, forecast, on-the-books -->
      <path d={cmpLine} class="cmp" />
      <path d={fcLine} class="fc" />
      <path d={otbLine} class="otb" />

      <!-- x ticks -->
      {#each ticks as t}
        <text x={x(t)} y={ih + 16} class="tick c">{fmtDate(t)}</text>
      {/each}

      {#if hover}
        <line x1={hover.x} x2={hover.x} y1="0" y2={ih} class="crosshair" />
        <circle cx={hover.x} cy={y(hover.point.occ)} r="3.5" class="dot otb-dot" />
        <circle cx={hover.x} cy={y(hover.point.fcOcc)} r="3.5" class="dot fc-dot" />
      {/if}
    </g>
  </svg>

  {#if hover}
    <div
      class="tooltip"
      style="left:{Math.min(hover.x + m.left + 12, width - 190)}px; top:{m.top + 6}px"
    >
      <div class="t-date">{fmtDateFull(hover.point.date)}</div>
      <div class="t-row"><span class="sw otb-sw"></span>On the books <b class="num">{fmtPct(hover.point.occ)}</b></div>
      <div class="t-row"><span class="sw fc-sw"></span>Forecast <b class="num">{fmtPct(hover.point.fcOcc)}</b>
        <span class="t-band num">({fmtPct(hover.point.fcLo80)}–{fmtPct(hover.point.fcHi80)})</span>
      </div>
      <div class="t-row"><span class="sw cmp-sw"></span>{compare === 'budget' ? 'Budget' : 'Last year'}
        <b class="num">{fmtPct(hover.point[compareKey])}</b>
      </div>
    </div>
  {/if}
</div>

{#if !compact}
  <div class="legend">
    <span><i class="line ink"></i>On the books</span>
    <span><i class="line dash"></i>Forecast</span>
    <span><i class="block b50s"></i>50% band</span>
    <span><i class="block b80s"></i>80% band</span>
    <span><i class="line gray"></i>{compare === 'budget' ? 'Budget' : 'Last year'}</span>
  </div>
{/if}

<style>
  .wrap {
    position: relative;
    width: 100%;
    min-width: 0;
  }
  .wrap svg {
    display: block;
    max-width: 100%;
  }
  .grid {
    stroke: var(--hairline);
    stroke-width: 1;
  }
  .axis {
    stroke: var(--hairline-strong);
  }
  .tick {
    font-size: 10.5px;
    fill: var(--ink-3);
    font-variant-numeric: tabular-nums;
  }
  .tick.r {
    text-anchor: end;
  }
  .tick.c {
    text-anchor: middle;
  }
  .band {
    stroke: none;
  }
  .b80 {
    fill: var(--accent);
    opacity: 0.1;
  }
  .b50 {
    fill: var(--accent);
    opacity: 0.2;
  }
  .fc {
    fill: none;
    stroke: var(--accent);
    stroke-width: 2;
    stroke-dasharray: 5 4;
    stroke-linecap: round;
  }
  .otb {
    fill: none;
    stroke: var(--ink);
    stroke-width: 2;
    stroke-linecap: round;
  }
  .cmp {
    fill: none;
    stroke: #b9b3a7;
    stroke-width: 1.5;
  }
  .crosshair {
    stroke: var(--ink-3);
    stroke-width: 1;
    stroke-dasharray: 2 3;
  }
  .dot {
    stroke: var(--panel);
    stroke-width: 1.5;
  }
  .otb-dot {
    fill: var(--ink);
  }
  .fc-dot {
    fill: var(--accent);
  }
  .tooltip {
    position: absolute;
    pointer-events: none;
    background: var(--panel);
    border: 1px solid var(--hairline-strong);
    border-radius: var(--radius);
    box-shadow: var(--shadow-pop);
    padding: 8px 10px;
    font-size: 12px;
    min-width: 170px;
  }
  .t-date {
    font-weight: 600;
    margin-bottom: 4px;
  }
  .t-row {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--ink-2);
    line-height: 1.7;
  }
  .t-row b {
    color: var(--ink);
    margin-left: auto;
  }
  .t-band {
    color: var(--ink-3);
    font-size: 11px;
  }
  .sw {
    width: 10px;
    height: 3px;
    border-radius: 1px;
    display: inline-block;
  }
  .otb-sw {
    background: var(--ink);
  }
  .fc-sw {
    background: var(--accent);
  }
  .cmp-sw {
    background: #b9b3a7;
  }
  .legend {
    display: flex;
    gap: 18px;
    margin-top: 8px;
    font-size: 11.5px;
    color: var(--ink-2);
  }
  .legend span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .legend i {
    display: inline-block;
  }
  .legend .line {
    width: 16px;
    height: 0;
    border-top: 2px solid var(--ink);
  }
  .legend .line.dash {
    border-top-style: dashed;
    border-top-color: var(--accent);
  }
  .legend .line.gray {
    border-top-color: #b9b3a7;
  }
  .legend .block {
    width: 14px;
    height: 10px;
    border-radius: 2px;
  }
  .legend .b50s {
    background: var(--accent);
    opacity: 0.25;
  }
  .legend .b80s {
    background: var(--accent);
    opacity: 0.12;
  }
</style>
