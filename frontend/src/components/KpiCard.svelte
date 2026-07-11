<script>
  import Sparkline from './Sparkline.svelte';
  import { fmtDelta, deltaClass, deltaArrow } from '../lib/formatters.js';

  export let label = '';
  export let value = '';
  export let delta = null; // fraction, e.g. 0.042
  export let deltaLabel = '';
  export let goodWhenUp = true;
  export let spark = null; // number[]
  export let sparkCaption = 'last 14 days';
</script>

<div class="kpi panel">
  <div class="kicker">{label}</div>
  <div class="value num">{value}</div>
  {#if delta !== null}
    <div class="delta-row">
      <span class="delta {deltaClass(delta, goodWhenUp)}">{deltaArrow(delta)} {fmtDelta(delta)}</span>
      <span class="ref">{deltaLabel}</span>
    </div>
  {/if}
  {#if spark}
    <div class="spark">
      <Sparkline data={spark} width={132} height={26} color="var(--ink-3)" />
      <span class="cap">{sparkCaption}</span>
    </div>
  {/if}
</div>

<style>
  .kpi {
    padding: 14px 16px 12px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .value {
    font-size: 26px;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin-top: 3px;
  }
  .delta-row {
    display: flex;
    align-items: baseline;
    gap: 6px;
    font-size: 12.5px;
  }
  .ref {
    color: var(--ink-3);
  }
  .spark {
    margin-top: 8px;
    display: flex;
    align-items: flex-end;
    gap: 8px;
  }
  .cap {
    font-size: 10.5px;
    color: var(--ink-3);
  }
</style>
