<script>
  // Part-to-whole as a segmented donut: padded gaps + rounded corners,
  // fixed series colours. Hovering a segment takes over the centre readout.
  import { pie as d3pie, arc as d3arc } from 'd3-shape';
  import { fmtPct } from '../lib/formatters.js';

  export let items = []; // [{label, share, color}]
  export let size = 176;
  export let thickness = 26;
  export let centerValue = '';
  export let centerLabel = '';
  export let ariaLabel = 'Share breakdown';

  let hover = null;

  $: r = size / 2;
  $: segs = d3pie()
    .value((d) => d.share)
    .sort(null) // fixed order — never re-sort by size
    .padAngle(0.04)(items);
  $: arcGen = d3arc()
    .innerRadius(r - thickness)
    .outerRadius(r)
    .cornerRadius(4);
  $: hovered = hover ? items.find((i) => i.label === hover) : null;
</script>

<svg width={size} height={size} viewBox="0 0 {size} {size}" role="group" aria-label={ariaLabel}>
  <g transform="translate({r},{r})" role="listbox" aria-label={ariaLabel} aria-orientation="horizontal">
    {#each segs as s (s.data.label)}
      <path
        d={arcGen(s)}
        fill={s.data.color}
        class="seg"
        class:dim={hover && hover !== s.data.label}
        tabindex="0"
        role="option"
        aria-selected={hover === s.data.label}
        on:mouseenter={() => (hover = s.data.label)}
        on:mouseleave={() => (hover = null)}
        on:focus={() => (hover = s.data.label)}
        on:blur={() => (hover = null)}
        aria-label="{s.data.label}: {fmtPct(s.data.share)}"
      />
    {/each}
    <text class="c-value num" y={centerLabel || hovered ? -1 : 5}>
      {hovered ? fmtPct(hovered.share) : centerValue}
    </text>
    {#if hovered || centerLabel}
      <text class="c-label" y="16">{hovered ? hovered.label : centerLabel}</text>
    {/if}
  </g>
</svg>

<style>
  .seg {
    transition: opacity 0.12s;
    cursor: default;
  }
  .seg.dim {
    opacity: 0.3;
  }
  .seg:focus-visible {
    outline: none;
    stroke: var(--ink);
    stroke-width: 1.5;
  }
  .c-value {
    text-anchor: middle;
    font-size: 17px;
    font-weight: 700;
    fill: var(--ink);
  }
  .c-label {
    text-anchor: middle;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    fill: var(--ink-3);
  }
</style>
