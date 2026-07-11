<script>
  import { createEventDispatcher } from 'svelte';
  import { fmtPct, fmtMoneyFull, fmtInt, fmtDelta, deltaClass, deltaArrow } from '../lib/formatters.js';

  export let rows = []; // [{property, occ, adr, revpar, pu7, delta}]
  export let total = null; // portfolio rollup {occ, adr, revpar, pu7, delta} — same numbers the hero quotes
  export let compareLabel = 'vs budget';

  const dispatch = createEventDispatcher();
</script>

<table class="data">
  <thead>
    <tr>
      <th>Property</th>
      <th class="r">Occ tonight</th>
      <th class="r">ADR</th>
      <th class="r">RevPAR</th>
      <th class="r">Pickup 7d</th>
      <th class="r">RevPAR {compareLabel}</th>
    </tr>
  </thead>
  <tbody>
    {#each rows as r}
      <tr
        class="row"
        tabindex="0"
        role="link"
        aria-label="Open {r.property.name}"
        on:click={() => dispatch('select', r.property.id)}
        on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && dispatch('select', r.property.id)}
      >
        <td>
          <span class="dot" style="background:{r.property.color}"></span>
          {r.property.name}
        </td>
        <td class="r">{fmtPct(r.occ)}</td>
        <td class="r">{fmtMoneyFull(r.adr)}</td>
        <td class="r">{fmtMoneyFull(r.revpar)}</td>
        <td class="r">{fmtInt(r.pu7)} rm</td>
        <td class="r">
          <span class="delta {deltaClass(r.delta)}">{deltaArrow(r.delta)} {fmtDelta(r.delta)}</span>
        </td>
      </tr>
    {/each}
  </tbody>
  {#if total}
    <tfoot>
      <tr class="total">
        <td>Portfolio</td>
        <td class="r">{fmtPct(total.occ)}</td>
        <td class="r">{fmtMoneyFull(total.adr)}</td>
        <td class="r">{fmtMoneyFull(total.revpar)}</td>
        <td class="r">{fmtInt(total.pu7)} rm</td>
        <td class="r">
          <span class="delta {deltaClass(total.delta)}">{deltaArrow(total.delta)} {fmtDelta(total.delta)}</span>
        </td>
      </tr>
    </tfoot>
  {/if}
</table>

<style>
  .row {
    cursor: pointer;
  }
  .row:focus-visible {
    outline: 2px solid var(--gold);
    outline-offset: -2px;
  }
  .total td {
    font-weight: 700;
    border-top: 2px solid var(--hairline-strong);
    border-bottom: none;
    background: var(--panel-tint);
  }
  .dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 7px;
    vertical-align: baseline;
  }
</style>
