<script>
  // Booking pace comparison. Date-based feeds are a current arrival-week
  // snapshot; only explicitly week-indexed feeds are described as a curve.
  import { scaleLinear } from 'd3-scale';
  import { line as d3line, curveMonotoneX } from 'd3-shape';
  import { GRAY_CONTEXT } from '../lib/constants.js';
  import { fmtInt } from '../lib/formatters.js';

  export let points = []; // [{weeksOut, ty|null, ly}]
  export let currentWeeksOut = 4;
  export let monthLabel = '';
  export let snapshot = false;
  export let height = 240;

  let width = 600;
  let hover = null;

  const m = { top: 14, right: 104, bottom: 26, left: 44 };
  $: iw = width - m.left - m.right;
  $: ih = height - m.top - m.bottom;

  $: x = scaleLinear().domain([20, 0]).range([0, iw]);
  $: maxY = Math.max(...points.map((p) => Math.max(p.ty ?? 0, p.ly)));
  $: y = scaleLinear().domain([0, maxY * 1.08]).range([ih, 0]);

  $: tyPts = points.filter((p) => p.ty != null);
  $: lyLine = d3line().x((p) => x(p.weeksOut)).y((p) => y(p.ly)).curve(curveMonotoneX)(points);
  $: tyLine = d3line().x((p) => x(p.weeksOut)).y((p) => y(p.ty)).curve(curveMonotoneX)(tyPts);

  $: tyEnd = tyPts[tyPts.length - 1];
  $: lyEnd = points[points.length - 1];
  $: yTicks = y.ticks(4);

  function onMove(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left - m.left;
    if (px < 0 || px > iw) return (hover = null);
    const w = Math.round(x.invert(px));
    const p = points.find((q) => q.weeksOut === w);
    hover = p ? { x: x(p.weeksOut), p } : null;
  }
</script>

<div class="wrap" bind:clientWidth={width} style="height:{height}px">
  <svg
    {width}
    {height}
    on:mousemove={onMove}
    on:mouseleave={() => (hover = null)}
    role="img"
    aria-label={snapshot
      ? `Current booking pace snapshot for ${monthLabel}: room nights on the books versus same-time-last-year by arrival lead`
      : `Booking pace for ${monthLabel}: cumulative room nights on the books, this year versus same time last year`}
  >
    <g transform="translate({m.left},{m.top})">
      {#each yTicks as v}
        <line x1="0" x2={iw} y1={y(v)} y2={y(v)} class="grid" />
        <text x="-8" y={y(v)} dy="3" class="tick r">{fmtInt(v)}</text>
      {/each}

      {#if !snapshot}
        <line x1={x(currentWeeksOut)} x2={x(currentWeeksOut)} y1="0" y2={ih} class="today" />
        <text x={x(currentWeeksOut)} y="-4" class="tick c today-label">today</text>
      {/if}

      <path d={lyLine} class="ly" style="stroke:{GRAY_CONTEXT}" />
      <path d={tyLine} class="ty" />

      <!-- direct labels at line ends -->
      {#if tyEnd}
        <circle cx={x(tyEnd.weeksOut)} cy={y(tyEnd.ty)} r="3" class="ty-dot" />
        <text x={x(tyEnd.weeksOut) + 8} y={y(tyEnd.ty)} dy="3" class="lbl ty-lbl">
          {snapshot ? 'OTB' : 'This year'} · {fmtInt(tyEnd.ty)}
        </text>
      {/if}
      <text x={x(0) + 8} y={y(lyEnd.ly)} dy="3" class="lbl ly-lbl">
        {snapshot ? 'STLY OTB' : 'Last year'} · {fmtInt(lyEnd.ly)}
      </text>

      {#each [20, 16, 12, 8, 4, 0] as w}
        <text x={x(w)} y={ih + 16} class="tick c">{w === 0 ? 'arrival' : `${w}w`}</text>
      {/each}

      {#if hover}
        <line x1={hover.x} x2={hover.x} y1="0" y2={ih} class="crosshair" />
      {/if}
    </g>
  </svg>

  {#if hover}
    <div class="tooltip" style="left:{Math.min(hover.x + m.left + 10, width - 175)}px; top:{m.top}px">
      <div class="t-date">{hover.p.weeksOut} weeks before arrival</div>
      {#if hover.p.ty != null}
        <div class="t-row"><span class="sw ty-sw"></span>{snapshot ? 'OTB' : 'This year'} <b class="num">{fmtInt(hover.p.ty)} rn</b></div>
      {/if}
      <div class="t-row"><span class="sw ly-sw"></span>{snapshot ? 'STLY OTB' : 'Last year'} <b class="num">{fmtInt(hover.p.ly)} rn</b></div>
    </div>
  {/if}
</div>
<div class="caption">
  {snapshot
    ? `Current OTB snapshot aggregated by arrival lead for ${monthLabel}; this is not a historical cumulative curve.`
    : `Cumulative room nights on the books for ${monthLabel} arrivals`}
</div>

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
  .today {
    stroke: var(--hairline-strong);
    stroke-dasharray: 3 3;
  }
  .today-label {
    fill: var(--ink-3);
    font-size: 10px;
  }
  .ly {
    fill: none;
    stroke: #b9b3a7;
    stroke-width: 2;
  }
  .ty {
    fill: none;
    stroke: var(--accent);
    stroke-width: 2.5;
    stroke-linecap: round;
  }
  .ty-dot {
    fill: var(--accent);
  }
  .lbl {
    font-size: 11px;
    font-weight: 600;
  }
  .ty-lbl {
    fill: var(--accent-ink);
  }
  .ly-lbl {
    fill: var(--ink-3);
  }
  .crosshair {
    stroke: var(--ink-3);
    stroke-width: 1;
    stroke-dasharray: 2 3;
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
    min-width: 160px;
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
  .sw {
    width: 10px;
    height: 3px;
    display: inline-block;
    border-radius: 1px;
  }
  .ty-sw {
    background: var(--accent);
  }
  .ly-sw {
    background: #b9b3a7;
  }
  .caption {
    font-size: 11.5px;
    color: var(--ink-3);
    margin-top: 6px;
  }
</style>
