<script>
  import { createEventDispatcher } from 'svelte';
  import Sparkline from './Sparkline.svelte';
  import { PROPERTIES } from '../lib/constants.js';
  import { alertStatus, setAlertStatus } from '../lib/stores.js';

  export let alert;
  export let compact = false;
  // progressive disclosure: the queue shows collapsed summaries, one card
  // expands at a time (parent owns which)
  export let expanded = false;

  const dispatch = createEventDispatcher();

  $: status = $alertStatus[alert.id] || 'new';
  $: propName =
    alert.property === 'ALL'
      ? 'All properties'
      : PROPERTIES.find((p) => p.id === alert.property)?.short;

  const ICONS = {
    risk: 'M8 1.5 15 14H1L8 1.5Zm0 4.5v4m0 2.2v.3',
    watch: 'M8 3C4.5 3 2 8 2 8s2.5 5 6 5 6-5 6-5-2.5-5-6-5Zm0 7a2 2 0 1 1 0-4 2 2 0 0 1 0 4Z',
    opportunity: 'M4 12 12 4m0 0H6.5M12 4v5.5'
  };
  const LABELS = { risk: 'Risk', watch: 'Watch', opportunity: 'Opportunity' };
</script>

<article class="card panel" class:compact class:resolved={status !== 'new'}>
  <header>
    <span class="tag {alert.severity}">
      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d={ICONS[alert.severity]} stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      {LABELS[alert.severity]}
    </span>
    <span class="prop">{propName}</span>
    {#if status === 'accepted'}
      <span class="state accepted">Accepted · sent to {alert.owner}</span>
    {:else if status === 'dismissed'}
      <span class="state">Dismissed</span>
    {/if}
    {#if status !== 'new' && !compact}
      <button class="undo" on:click={() => setAlertStatus(alert.id, null)}>Undo</button>
    {/if}
  </header>

  {#if compact}
    <h3>{alert.title}</h3>
  {:else}
    <button class="title-row" aria-expanded={expanded} on:click={() => dispatch('toggle')}>
      <h3>{alert.title}</h3>
      <svg class="chev" class:open={expanded} width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="m4 6 4 4 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>
  {/if}

  {#if !compact && expanded}
    <p class="body">{alert.body}</p>

    <div class="evidence">
      <Sparkline data={alert.evidence} width={210} height={38} color="var(--ink-2)" />
      <span class="cap">{alert.evidenceLabel}</span>
    </div>

    <div class="action">
      <div class="kicker">Recommended action</div>
      <p>{alert.action}</p>
      <div class="impact num">{alert.impact}</div>
    </div>

    {#if status === 'new'}
      <footer>
        <button class="primary" on:click={() => setAlertStatus(alert.id, 'accepted')}>
          Accept — assign to {alert.owner}
        </button>
        <button class="ghost" on:click={() => setAlertStatus(alert.id, 'dismissed')}>Dismiss</button>
      </footer>
    {/if}
  {/if}
</article>

<style>
  .card {
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .card.resolved {
    opacity: 0.62;
  }
  header {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .prop {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--ink-2);
    border: 1px solid var(--hairline-strong);
    border-radius: 3px;
    padding: 1px 7px;
  }
  .state {
    margin-left: auto;
    font-size: 11.5px;
    color: var(--ink-3);
    font-weight: 500;
  }
  .state.accepted {
    color: var(--good);
  }
  .undo {
    background: none;
    border: none;
    color: var(--gold-ink);
    font-size: 11.5px;
    font-weight: 600;
    padding: 0;
  }
  .title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    background: none;
    border: none;
    padding: 0;
    text-align: left;
    color: inherit;
    font-family: inherit;
  }
  .chev {
    flex: none;
    color: var(--ink-3);
    transition: transform 0.15s;
  }
  .chev.open {
    transform: rotate(180deg);
  }
  h3 {
    font-size: 14.5px;
    font-weight: 600;
    line-height: 1.35;
    margin: 0;
  }
  .compact h3 {
    font-size: 13px;
  }
  .body {
    margin: 0;
    color: var(--ink-2);
    font-size: 13px;
  }
  .evidence {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    padding: 8px 10px;
    background: var(--panel-tint);
    border-radius: var(--radius);
  }
  .cap {
    font-size: 10.5px;
    color: var(--ink-3);
    padding-bottom: 2px;
  }
  .action {
    border-left: 3px solid var(--gold);
    padding: 4px 0 4px 12px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .action p {
    margin: 0;
    font-size: 13px;
  }
  .impact {
    font-size: 12px;
    color: var(--gold-ink);
    font-weight: 600;
  }
  footer {
    display: flex;
    gap: 8px;
    margin-top: 2px;
  }
  button.primary {
    background: var(--primary);
    color: #fff;
    border: none;
    border-radius: var(--radius);
    padding: 6px 14px;
    font-size: 12.5px;
    font-weight: 600;
    box-shadow: var(--shadow-card);
  }
  button.primary:hover {
    background: var(--primary-hover);
  }
  button.ghost {
    background: none;
    border: 1px solid var(--hairline-strong);
    border-radius: var(--radius);
    padding: 6px 12px;
    font-size: 12.5px;
    color: var(--ink-2);
  }
  button.ghost:hover {
    background: var(--panel-tint);
  }
</style>
