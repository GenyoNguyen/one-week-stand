<script>
  import RecommendationPanel from '../components/RecommendationPanel.svelte';
  import { getAlerts } from '../lib/api.js';
  import { propertyFilter, alertStatus, focusAlert } from '../lib/stores.js';

  let loading = true;
  let alerts = [];
  let filter = 'all';
  let openId = null; // accordion: one alert expanded at a time
  let autoOpened = false;

  const SEV_ORDER = { risk: 0, watch: 1, opportunity: 2 };

  async function load() {
    loading = true;
    alerts = await getAlerts();
    loading = false;
  }
  load();

  $: scoped = alerts.filter(
    (a) => $propertyFilter === 'ALL' || a.property === $propertyFilter || a.property === 'ALL'
  );
  $: counts = {
    all: scoped.length,
    risk: scoped.filter((a) => a.severity === 'risk').length,
    watch: scoped.filter((a) => a.severity === 'watch').length,
    opportunity: scoped.filter((a) => a.severity === 'opportunity').length
  };
  $: visible = scoped
    .filter((a) => filter === 'all' || a.severity === filter)
    .sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);
  $: open = visible.filter((a) => !$alertStatus[a.id]);
  $: resolved = visible.filter((a) => $alertStatus[a.id]);
  $: acceptedCount = scoped.filter((a) => $alertStatus[a.id] === 'accepted').length;

  // deep link from "Needs attention" wins; otherwise open the top of the
  // queue once on first load, then let the user drive
  $: if ($focusAlert) {
    openId = $focusAlert;
    filter = 'all';
    autoOpened = true;
    focusAlert.set(null);
  }
  $: if (!autoOpened && open.length) {
    openId = open[0].id;
    autoOpened = true;
  }

  const toggle = (id) => (openId = openId === id ? null : id);
</script>

<div class="view reveal">
  <header class="head">
    <div>
      <h1 class="view-title">Alerts &amp; recommendations</h1>
      <p class="view-sub">
        Each alert carries one recommended action — accept to assign it, dismiss with reason in
        stand-up. {acceptedCount ? `${acceptedCount} accepted today.` : ''}
      </p>
    </div>
    <div class="chips" role="group" aria-label="Severity filter">
      {#each [['all', 'All'], ['risk', 'Risks'], ['watch', 'Watch'], ['opportunity', 'Opportunities']] as [id, label]}
        <button class:active={filter === id} on:click={() => (filter = id)}>
          {label} <span class="count num">{counts[id]}</span>
        </button>
      {/each}
    </div>
  </header>

  {#if loading}
    <div class="skeleton" style="height:420px"></div>
  {:else if !open.length && !resolved.length}
    <div class="panel empty">
      <p><b>No alerts for this scope.</b></p>
      <p>
        Nothing needs attention for the selected property. Widen the filter to all properties, or
        check back after tomorrow's 06:00 data refresh.
      </p>
    </div>
  {:else}
    <section class="cards">
      {#each open as a (a.id)}
        <RecommendationPanel alert={a} expanded={openId === a.id} on:toggle={() => toggle(a.id)} />
      {/each}
    </section>

    {#if resolved.length}
      <h2 class="kicker resolved-head">Resolved today</h2>
      <section class="cards">
        {#each resolved as a (a.id)}
          <RecommendationPanel alert={a} expanded={openId === a.id} on:toggle={() => toggle(a.id)} />
        {/each}
      </section>
    {/if}
  {/if}
</div>

<style>
  .view {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    flex-wrap: wrap;
  }
  .chips {
    display: inline-flex;
    border: 1px solid var(--hairline-strong);
    border-radius: var(--radius);
    overflow: hidden;
    background: var(--panel);
  }
  .chips button {
    border: none;
    background: none;
    padding: 6px 12px;
    font-size: 12.5px;
    font-weight: 500;
    color: var(--ink-2);
  }
  .chips button + button {
    border-left: 1px solid var(--hairline);
  }
  .chips button.active {
    background: var(--accent-soft);
    color: var(--accent-ink);
    font-weight: 600;
  }
  .count {
    color: var(--ink-3);
    font-size: 11px;
  }
  /* a decision queue reads top-to-bottom — one column, one card expanded */
  .cards {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-width: 780px;
  }
  .resolved-head {
    margin-top: 6px;
  }
  .empty {
    padding: 28px;
    max-width: 460px;
  }
  .empty p {
    margin: 0 0 6px;
    color: var(--ink-2);
  }
</style>
