<script>
  import DOMPurify from 'dompurify';
  import { marked } from 'marked';
  import { onDestroy, onMount } from 'svelte';

  import { getForecast, getForecastResult, resumeForecast } from '../lib/api.js';

  export let jobId = '';

  const POLL_INTERVAL_MS = 2500;
  const PROJECTS_STORAGE_KEY = 'anam-forecast-projects';
  let job = null;
  let project = null;
  let result = null;
  let error = '';
  let pollTimer;
  let loading = true;
  let requestSequence = 0;

  $: report = result?.report || null;
  $: structured = report?.structured_output || null;
  $: reportHtml = report?.markdown_content
    ? DOMPurify.sanitize(marked.parse(report.markdown_content, { gfm: true, breaks: false }))
    : '';

  onMount(() => {
    try {
      const projects = JSON.parse(localStorage.getItem(PROJECTS_STORAGE_KEY) || '[]');
      project = projects.find((item) => item.job_id === jobId) || null;
    } catch {
      project = null;
    }
    const sequence = ++requestSequence;
    void refresh(sequence);
    return () => {
      if (pollTimer) clearTimeout(pollTimer);
      requestSequence += 1;
    };
  });

  function schedule(sequence) {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = setTimeout(() => void refresh(sequence), POLL_INTERVAL_MS);
  }

  async function refresh(sequence = requestSequence) {
    if (!jobId) {
      error = 'No forecast project was selected.';
      loading = false;
      return;
    }
    try {
      const nextJob = await getForecast(jobId);
      if (sequence !== requestSequence) return;
      job = nextJob;
      loading = false;

      if (nextJob.status === 'completed') {
        const response = await getForecastResult(jobId);
        if (sequence !== requestSequence) return;
        if (response.status === 202) {
          schedule(sequence);
          return;
        }
        result = response.data;
        return;
      }

      if (nextJob.status === 'failed') {
        error = nextJob.error || nextJob.message || 'The forecast project failed.';
        return;
      }

      schedule(sequence);
    } catch (requestError) {
      if (sequence !== requestSequence) return;
      loading = false;
      error = requestError?.message || 'The forecast project could not be loaded.';
    }
  }

  async function finishReport() {
    if (!job?.resumable) return;
    error = '';
    loading = true;
    try {
      job = await resumeForecast(jobId);
      const sequence = ++requestSequence;
      await refresh(sequence);
    } catch (requestError) {
      loading = false;
      error = requestError?.message || 'The report could not be resumed.';
    }
  }

  function openProjects() {
    location.hash = 'data';
  }

  function formatCell(value) {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function downloadReport() {
    if (!report?.markdown_content) return;
    const url = URL.createObjectURL(
      new Blob([report.markdown_content], { type: 'text/markdown;charset=utf-8' })
    );
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${report.report_id || jobId}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
</script>

<svelte:head>
  <title>Forecast report · The Anam</title>
</svelte:head>

<div class="view reveal">
  <header class="report-header">
    <div>
      <button class="back-button" type="button" on:click={openProjects}>← Forecast projects</button>
      <h1 class="view-title">{project?.name || 'Forecast report'}</h1>
      <p class="view-sub">Forecast report · {jobId}</p>
    </div>
    {#if report?.markdown_content}
      <button class="ghost" type="button" on:click={downloadReport}>Download Markdown</button>
    {/if}
  </header>

  {#if loading && !job}
    <section class="panel loading-panel">
      <span class="status-dot active"></span>
      <b>Loading forecast project…</b>
    </section>
  {:else if error && !report}
    <section class="panel error-panel" role="alert">
      <span class="tag risk">Needs attention</span>
      <b>{error}</b>
      {#if job?.resumable}
        <button class="primary" type="button" on:click={finishReport}>Finish report</button>
      {/if}
    </section>
  {:else}
    <section class="project-summary panel">
      <div>
        <span class="kicker">Project status</span>
        <h2>{job?.status === 'completed' ? 'Complete' : job?.message || 'Processing'}</h2>
      </div>
      <div class="summary-meta">
        <span>{job?.progress || 0}%</span>
        <span>{job?.stage || 'queued'}</span>
        {#if job?.project_id}<span>{job.project_id}</span>{/if}
      </div>
    </section>

    {#if structured?.rows?.length}
      <section class="panel structured-panel">
        <div class="panel-head">
          <div>
            <h2 class="kicker">Structured result</h2>
            <p class="panel-sub">Validated output from the forecast report</p>
          </div>
          <span class="tag watch">{structured.rows.length} rows · needs verification</span>
        </div>
        <div class="table-scroll">
          <table class="result-table">
            <thead>
              <tr>
                {#each structured.columns || [] as column (column.key)}
                  <th>{column.label || column.key}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each structured.rows as row, rowIndex (row.claim + rowIndex)}
                <tr>
                  {#each structured.columns || [] as column (column.key)}
                    <td>{formatCell(row[column.key])}</td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}

    {#if reportHtml}
      <section class="panel report-panel">
        <div class="panel-head">
          <div>
            <h2 class="kicker">Report</h2>
            <p class="panel-sub">Generated commercial read and recommended actions</p>
          </div>
          <button class="ghost" type="button" on:click={downloadReport}>Download Markdown</button>
        </div>
        <div class="markdown-body">{@html reportHtml}</div>
      </section>
    {/if}
  {/if}
</div>

<style>
  .report-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }
  .back-button {
    display: block;
    margin-bottom: 10px;
    padding: 0;
    border: 0;
    background: none;
    color: var(--gold-ink);
    font-size: 12px;
    font-weight: 600;
  }
  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 18px 10px;
  }
  .panel-sub {
    margin: 3px 0 0;
    color: var(--ink-3);
    font-size: 11.5px;
  }
  .loading-panel,
  .error-panel,
  .project-summary {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 18px;
  }
  .error-panel {
    flex-wrap: wrap;
    color: var(--ink-2);
  }
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    flex: 0 0 auto;
    border-radius: 50%;
    background: var(--watch);
  }
  .project-summary {
    justify-content: space-between;
  }
  .project-summary h2 {
    margin-top: 4px;
    font-family: var(--font-display);
    font-size: 22px;
  }
  .summary-meta {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 6px;
    color: var(--ink-3);
    font-size: 11px;
    text-align: right;
  }
  .summary-meta span {
    padding: 3px 7px;
    border: 1px solid var(--hairline);
    border-radius: var(--radius);
  }
  .table-scroll {
    overflow-x: auto;
    padding: 0 18px 18px;
  }
  .result-table {
    width: max-content;
    min-width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  .result-table th,
  .result-table td {
    max-width: 440px;
    padding: 8px 10px;
    border: 1px solid var(--hairline);
    text-align: left;
    vertical-align: top;
  }
  .result-table th {
    background: var(--panel-tint);
    color: var(--ink-2);
    font-size: 10.5px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    white-space: nowrap;
  }
  .result-table td {
    color: var(--ink-2);
    overflow-wrap: anywhere;
  }
  .markdown-body {
    padding: 4px 20px 24px;
    color: var(--ink-2);
    font-size: 13px;
    line-height: 1.65;
    overflow-x: auto;
  }
  .markdown-body :global(h1) {
    margin: 8px 0 6px;
    color: var(--ink);
    font-family: var(--font-display);
    font-size: 24px;
    letter-spacing: 0;
  }
  .markdown-body :global(h2) {
    margin: 24px 0 8px;
    color: var(--ink);
    font-family: var(--font-display);
    font-size: 18px;
    letter-spacing: 0;
  }
  .markdown-body :global(p),
  .markdown-body :global(ul),
  .markdown-body :global(ol) {
    max-width: 1000px;
  }
  .markdown-body :global(blockquote) {
    margin: 12px 0;
    padding: 8px 14px;
    border-left: 3px solid var(--gold);
    background: var(--panel-tint);
  }
  .markdown-body :global(table) {
    width: max-content;
    min-width: 100%;
    margin: 14px 0;
    border-collapse: collapse;
    font-size: 12px;
  }
  .markdown-body :global(th),
  .markdown-body :global(td) {
    max-width: 520px;
    padding: 8px 10px;
    border: 1px solid var(--hairline);
    text-align: left;
    vertical-align: top;
  }
  .markdown-body :global(th) {
    background: var(--panel-tint);
    color: var(--ink);
  }
  button.primary,
  button.ghost {
    border-radius: var(--radius);
    padding: 6px 12px;
    font-size: 12.5px;
  }
  button.primary {
    border: none;
    background: var(--primary);
    color: #fff;
    font-weight: 600;
  }
  button.ghost {
    border: 1px solid var(--hairline-strong);
    background: none;
    color: var(--ink-2);
  }
  @media (max-width: 700px) {
    .report-header,
    .project-summary {
      align-items: stretch;
      flex-direction: column;
    }
    .summary-meta {
      justify-content: flex-start;
      text-align: left;
    }
  }
</style>
