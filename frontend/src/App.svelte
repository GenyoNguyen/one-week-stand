<script>
  import { onMount } from 'svelte';
  import FilterBar from './components/FilterBar.svelte';
  import AnamLogo from './components/AnamLogo.svelte';
  import DailyOverview from './routes/DailyOverview.svelte';
  import DemandForecast from './routes/DemandForecast.svelte';
  import PropertyView from './routes/PropertyView.svelte';
  import SegmentChannelView from './routes/SegmentChannelView.svelte';
  import AlertsRecommendations from './routes/AlertsRecommendations.svelte';
  import DataUpload from './routes/DataUpload.svelte';
  import { currentView, navigate } from './lib/stores.js';

  const VIEWS = [
    {
      id: 'daily',
      label: 'Daily overview',
      component: DailyOverview,
      icon: 'M2 12.5h12M4.5 12.5a3.5 3.5 0 0 1 7 0M8 6.5V4.5m-4.6 3 1.1 1.1m8.1-1.1-1.1 1.1'
    },
    {
      id: 'forecast',
      label: 'Demand forecast',
      component: DemandForecast,
      icon: 'M2 12l3.5-4.5 2.8 2.6L13 4m0 0h-3m3 0v3'
    },
    {
      id: 'property',
      label: 'Properties',
      component: PropertyView,
      icon: 'M3 13.5V4l5-2 5 2v9.5M6 6h1m2 0h1M6 8.5h1m2 0h1M2 13.5h12'
    },
    {
      id: 'segments',
      label: 'Segments & channels',
      component: SegmentChannelView,
      icon: 'M8 2 14 5 8 8 2 5l6-3Zm-6 6 6 3 6-3M2 11l6 3 6-3'
    },
    {
      id: 'alerts',
      label: 'Alerts & actions',
      component: AlertsRecommendations,
      icon: 'M8 2a4 4 0 0 1 4 4c0 3 1 4 1.5 4.5h-11C3 10 4 9 4 6a4 4 0 0 1 4-4Zm-1.5 11a1.5 1.5 0 0 0 3 0'
    },
    {
      id: 'data',
      label: 'Data',
      component: DataUpload,
      icon: 'M8 10V2.5m0 0L5 5.5m3-3 3 3M3 9.5v2A1.5 1.5 0 0 0 4.5 13h7a1.5 1.5 0 0 0 1.5-1.5v-2'
    }
  ];

  $: active = VIEWS.find((v) => v.id === $currentView) ?? VIEWS[0];

  const go = navigate;

  onMount(() => {
    const fromHash = () => {
      const id = location.hash.replace('#', '');
      if (VIEWS.some((v) => v.id === id)) currentView.set(id);
    };
    fromHash();
    window.addEventListener('hashchange', fromHash);
    return () => window.removeEventListener('hashchange', fromHash);
  });
</script>

<div class="app">
  <aside class="sidebar">
    <div class="brand">
      <AnamLogo size={48} color="var(--gold)" />
      <div class="brand-name">The Anam</div>
      <div class="brand-sub">Commercial Intelligence</div>
    </div>

    <nav>
      {#each VIEWS as v (v.id)}
        <button class="nav-item" class:active={v.id === active.id} on:click={() => go(v.id)}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d={v.icon} stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          {v.label}
        </button>
      {/each}
    </nav>

    <div class="side-foot">
      <div class="foot-line">Mock data preview</div>
      <div class="foot-line dim">Forecast &amp; intelligence services pending — shapes match the API contract</div>
    </div>
  </aside>

  <div class="main">
    <FilterBar />
    <main class="content">
      <svelte:component this={active.component} />
    </main>
  </div>
</div>

<style>
  .app {
    display: grid;
    grid-template-columns: 232px 1fr;
    min-height: 100vh;
  }
  .sidebar {
    background: var(--sidebar);
    color: var(--sidebar-ink);
    display: flex;
    flex-direction: column;
    padding: 20px 12px 16px;
    position: sticky;
    top: 0;
    height: 100vh;
  }
  /* brand lockup: emblem above a Trajan-style wordmark, as on the real logo */
  .brand {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 6px;
    padding: 10px 10px 18px;
    border-bottom: 1px solid rgba(236, 231, 220, 0.12);
    margin-bottom: 14px;
  }
  .brand-name {
    font-family: 'Cinzel', var(--font-display);
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    color: #c9a25e;
  }
  .brand-sub {
    font-size: 9.5px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--sidebar-muted);
  }
  nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    border-radius: var(--radius);
    color: var(--sidebar-muted);
    font-size: 13px;
    font-weight: 500;
    padding: 8px 10px;
  }
  .nav-item:hover {
    color: var(--sidebar-ink);
    background: rgba(236, 231, 220, 0.06);
  }
  .nav-item.active {
    color: #ecd9a8;
    background: rgba(201, 154, 60, 0.14);
  }
  .side-foot {
    margin-top: auto;
    padding: 12px 10px 0;
    border-top: 1px solid rgba(236, 231, 220, 0.12);
    font-size: 10.5px;
    line-height: 1.5;
  }
  .foot-line {
    color: var(--sidebar-ink);
    font-weight: 600;
  }
  .foot-line.dim {
    color: var(--sidebar-muted);
    font-weight: 400;
    margin-top: 3px;
  }
  .main {
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
  .content {
    padding: 22px 32px 40px;
    max-width: 1560px;
    width: 100%;
    margin: 0 auto;
  }
</style>
