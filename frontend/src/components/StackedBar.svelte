<script>
  // Horizontal part-to-whole bar with 2px surface gaps between segments.
  import { fmtPct } from '../lib/formatters.js';

  export let items = []; // [{label, share, color}]
  export let height = 22;

  let hover = null;
</script>

<div class="bar" style="height:{height}px">
  {#each items as it (it.label)}
    <div
      class="seg"
      style="flex-grow:{it.share}; background:{it.color}"
      on:mouseenter={() => (hover = it)}
      on:mouseleave={() => (hover = null)}
      role="figure"
      aria-label="{it.label}: {fmtPct(it.share)}"
    >
      {#if it.share > 0.12}
        <span class="num">{fmtPct(it.share)}</span>
      {/if}
    </div>
  {/each}
</div>
{#if hover}
  <div class="hint num">{hover.label} — {fmtPct(hover.share)}</div>
{/if}

<style>
  .bar {
    display: flex;
    gap: 2px;
    width: 100%;
  }
  .seg {
    border-radius: 2px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: rgba(255, 255, 255, 0.92);
    font-size: 10.5px;
    font-weight: 600;
    min-width: 4px;
    transition: opacity 0.12s;
  }
  .seg:hover {
    opacity: 0.85;
  }
  .hint {
    font-size: 11px;
    color: var(--ink-2);
    margin-top: 4px;
  }
</style>
