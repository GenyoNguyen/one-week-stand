<script>
  import RecommendationPanel from '../components/RecommendationPanel.svelte';
  import DashboardDataState from '../components/DashboardDataState.svelte';
  import { getAlerts } from '../lib/api.js';
  import { invalidateDashboard } from '../lib/dashboard-store.js';
  import { propertyFilter, alertStatus, focusAlert } from '../lib/stores.js';
  import { fmtMoney } from '../lib/formatters.js';

  let loading = true;
  let alerts = [];
  let filter = 'all';
  let openId = null; // accordion: one alert expanded at a time
  let autoOpened = false;
  let loadError = null;

  const SEV_ORDER = { risk: 0, watch: 1, opportunity: 2 };

  async function load() {
    loading = true;
    loadError = null;
    try {
      alerts = await getAlerts();
    } catch (error) {
      loadError = error;
      alerts = [];
    } finally {
      loading = false;
    }
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
  $: acceptedAlerts = scoped.filter((a) => $alertStatus[a.id] === 'accepted');
  $: acceptedCount = acceptedAlerts.length;
  $: dismissedCount = scoped.filter((a) => $alertStatus[a.id] === 'dismissed').length;
  // Sum structured live impact values. Demo strings retain their legacy $NNK parsing.
  $: impactSum = acceptedAlerts.reduce((s, a) => {
    const m = a.impact?.match(/\$(\d+)K/);
    return s + (Number.isFinite(a.impactValue) ? a.impactValue : m ? Number(m[1]) * 1000 : 0);
  }, 0);
  $: ownerCounts = Object.entries(
    acceptedAlerts.reduce((o, a) => ((o[a.owner] = (o[a.owner] || 0) + 1), o), {})
  );

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

  function retry() {
    invalidateDashboard();
    void load();
  }
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
  {:else if loadError}
    <DashboardDataState error={loadError} onRetry={retry} />
  {:else if !open.length && !resolved.length}
    <div class="panel empty">
      <p><b>No alerts for this scope.</b></p>
      <p>
        Nothing needs attention for the selected property. Widen the filter to all properties, or
        check back after tomorrow's 06:00 data refresh.
      </p>
    </div>
  {:else}
    <div class="layout">
      <section class="cards">
        {#each open as a (a.id)}
          <RecommendationPanel alert={a} expanded={openId === a.id} on:toggle={() => toggle(a.id)} />
        {/each}
        {#if !open.length}
          <div class="panel queue-clear">
            <p><b>Queue is clear.</b></p>
            <p>Every alert has been decided — see the summary on the right, or Undo to revisit one.</p>
          </div>
        {/if}
      </section>

      <aside class="side">
        <div class="panel summary">
          <h2 class="kicker">Today so far</h2>
          <div class="sum-nums">
            <div class="sum">
              <span class="big num">{acceptedCount}</span>
              <span class="sum-label">accepted</span>
            </div>
            <div class="sum">
              <span class="big num">{dismissedCount}</span>
              <span class="sum-label">dismissed</span>
            </div>
            <div class="sum">
              <span class="big num">{open.length}</span>
              <span class="sum-label">in queue</span>
            </div>
          </div>
          {#if impactSum > 0}
            <div class="impact num">Up to {fmtMoney(impactSum)} source-derived impact on accepted actions</div>
          {/if}
          {#if ownerCounts.length}
            <div class="owners">
              <span class="owners-label">Assigned to</span>
              {#each ownerCounts as [owner, n] (owner)}
                <span class="owner-chip">{owner}{n > 1 ? ` ×${n}` : ''}</span>
              {/each}
            </div>
          {/if}
          {#if !acceptedCount && !dismissedCount}
            <p class="hint">No decisions yet — work the queue from the top.</p>
          {/if}
        </div>

        {#if resolved.length}
          <h2 class="kicker resolved-head">Resolved today</h2>
          {#each resolved as a (a.id)}
            <RecommendationPanel alert={a} expanded={openId === a.id} on:toggle={() => toggle(a.id)} />
          {/each}
        {/if}
      </aside>
    </div>
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
    gap: 2px;
    border: 1px solid var(--hairline);
    border-radius: var(--radius);
    padding: 2px;
    background: var(--panel-tint);
  }
  .chips button {
    border: none;
    background: none;
    border-radius: calc(var(--radius) - 2px);
    padding: 5px 12px;
    font-size: 12.5px;
    font-weight: 500;
    color: var(--ink-2);
  }
  .chips button.active {
    background: var(--panel);
    color: var(--gold-ink);
    font-weight: 600;
    box-shadow: var(--shadow-card);
  }
  .count {
    color: var(--ink-3);
    font-size: 11px;
  }
  /* decision queue on the left, running tally + resolved on the right */
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 330px;
    gap: 14px;
    align-items: start;
  }
  .cards {
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-width: 0;
  }
  .side {
    display: flex;
    flex-direction: column;
    gap: 10px;
    position: sticky;
    top: 66px;
  }
  .summary {
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .sum-nums {
    display: flex;
    gap: 22px;
  }
  .sum {
    display: flex;
    flex-direction: column;
  }
  .big {
    font-size: 26px;
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.15;
  }
  .sum-label {
    font-size: 11.5px;
    color: var(--ink-3);
  }
  .impact {
    font-size: 12.5px;
    font-weight: 600;
    color: var(--gold-ink);
    border-left: 3px solid var(--gold);
    padding-left: 10px;
  }
  .owners {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }
  .owners-label {
    font-size: 11.5px;
    color: var(--ink-3);
  }
  .owner-chip {
    font-size: 11.5px;
    font-weight: 600;
    color: var(--ink-2);
    border: 1px solid var(--hairline-strong);
    border-radius: 3px;
    padding: 1px 7px;
  }
  .hint {
    margin: 0;
    font-size: 12px;
    color: var(--ink-3);
  }
  .queue-clear {
    padding: 22px;
  }
  .queue-clear p {
    margin: 0 0 4px;
    color: var(--ink-2);
    font-size: 13px;
  }
  .resolved-head {
    margin-top: 8px;
  }
  @media (max-width: 1080px) {
    .layout {
      grid-template-columns: 1fr;
    }
    .side {
      position: static;
    }
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
