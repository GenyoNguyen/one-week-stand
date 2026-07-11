<script>
  export let error = null;
  export let empty = false;
  export let onRetry = null;

  $: title = error?.code === 'forecast_pending'
    ? 'Forecast still processing'
    : error?.code === 'dashboard_unavailable'
      ? 'Dashboard data unavailable'
      : empty
        ? 'No data for this view'
        : 'Could not load dashboard data';
  $: detail = error?.message ||
    'The completed forecast does not contain records for this scope. Try another property or upload a complete hotel performance bundle.';
</script>

<div class="panel state" role={error ? 'alert' : 'status'}>
  <p class="title">{title}</p>
  <p>{detail}</p>
  {#if onRetry}
    <button on:click={onRetry}>Try again</button>
  {/if}
</div>

<style>
  .state {
    max-width: 620px;
    padding: 24px;
  }
  p {
    margin: 0 0 6px;
    color: var(--ink-2);
    font-size: 13px;
    line-height: 1.5;
  }
  .title {
    color: var(--ink);
    font-weight: 650;
    font-size: 14px;
  }
  button {
    margin-top: 8px;
    border: 1px solid var(--hairline-strong);
    border-radius: var(--radius);
    background: var(--panel);
    color: var(--gold-ink);
    padding: 6px 12px;
    font: inherit;
    font-size: 12.5px;
    font-weight: 600;
  }
</style>
