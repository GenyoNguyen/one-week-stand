<script>
  import { createEventDispatcher } from 'svelte';
  import { fmtPct, fmtMoneyFull, fmtInt, fmtDelta, deltaClass, deltaArrow } from '../lib/formatters.js';

  export let rows = []; // [{property, occ, adr, revpar, pu7, delta}]
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
      <tr class="row" on:click={() => dispatch('select', r.property.id)}>
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
</table>

<style>
  .row {
    cursor: pointer;
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
