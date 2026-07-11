<script>
  // 7-day pickup by stay date, calendar layout. Sequential single hue —
  // magnitude only, so one teal ramp, light to dark.
  import { fmtDate, fmtInt } from '../lib/formatters.js';

  export let cells = []; // [{date, pu7}] — consecutive days starting tomorrow

  $: max = Math.max(1, ...cells.map((c) => c.pu7));

  // teal ramp between two endpoints, discrete enough to stay readable
  function shade(v) {
    const t = Math.pow(v / max, 0.75);
    const from = [232, 242, 239];
    const to = [7, 84, 72];
    const c = from.map((f, i) => Math.round(f + (to[i] - f) * t));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }
  const ink = (v) => (v / max > 0.55 ? '#f2efe9' : 'var(--ink-2)');

  // align first cell to its weekday column (Mon-first)
  $: lead = cells.length ? (cells[0].date.getDay() + 6) % 7 : 0;
  const DOW = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  let hover = null;
</script>

<div class="cal">
  {#each DOW as d}
    <div class="dow">{d}</div>
  {/each}
  {#each Array(lead) as _}
    <div></div>
  {/each}
  {#each cells as c (c.date)}
    <div
      class="cell num"
      style="background:{shade(c.pu7)}; color:{ink(c.pu7)}"
      on:mouseenter={() => (hover = c)}
      on:mouseleave={() => (hover = null)}
      role="figure"
      aria-label="{fmtDate(c.date)}: {c.pu7} rooms picked up in last 7 days"
    >
      {c.date.getDate()}
    </div>
  {/each}
</div>

<div class="foot">
  <span class="hint num">
    {#if hover}{fmtDate(hover.date)} — {fmtInt(hover.pu7)} rooms picked up in the last 7 days{:else}Hover a
    date for detail{/if}
  </span>
  <span class="scale">
    0
    {#each [0.2, 0.4, 0.6, 0.8, 1] as s}
      <i style="background:{shade(s * max)}"></i>
    {/each}
    {fmtInt(max)} rm
  </span>
</div>

<style>
  .cal {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 3px;
  }
  .dow {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--ink-3);
    text-align: center;
    padding-bottom: 2px;
  }
  .cell {
    aspect-ratio: 1.5;
    border-radius: 3px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11.5px;
    cursor: default;
  }
  .cell:hover {
    outline: 2px solid var(--ink);
    outline-offset: -1px;
  }
  .foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    font-size: 11px;
    color: var(--ink-3);
  }
  .scale {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-variant-numeric: tabular-nums;
  }
  .scale i {
    width: 14px;
    height: 10px;
    border-radius: 2px;
    display: inline-block;
  }
</style>
