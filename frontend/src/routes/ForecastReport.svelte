<script>
  import DOMPurify from 'dompurify';
  import { marked } from 'marked';
  import { onDestroy, onMount } from 'svelte';

  import { getForecast, getForecastResult, resumeForecast } from '../lib/api.js';
  import { setActiveForecast } from '../lib/dashboard-store.js';

  export let jobId = '';

  const POLL_INTERVAL_MS = 2500;
  const MAX_POLL_FAILURES = 4;
  const PROJECTS_STORAGE_KEY = 'anam-forecast-projects';

  let activeJobId = '';
  let error = '';
  let job = null;
  let loading = true;
  let mounted = false;
  let pollFailures = 0;
  let pollNotice = '';
  let pollTimer;
  let project = null;
  let requestSequence = 0;
  let result = null;
  let statusPollFailed = false;

  $: report = result?.report || null;
  $: outline = report?.outline || null;
  $: structured = report?.structured_output || null;
  $: structuredRows = Array.isArray(structured?.rows) ? structured.rows : [];
  $: structuredColumns = getStructuredColumns(structured, structuredRows);
  $: reportSections = getReportSections(outline, structured);
  $: fallbackReportHtml = reportSections.length || !report?.markdown_content
    ? ''
    : renderMarkdown(stripStructuredTable(report.markdown_content, structured));
  $: reportTitle = outline?.title?.trim() || project?.name || 'Forecast report';
  $: reportSummary = outline?.summary?.trim() || '';
  $: dashboardJobId = result?.job?.job_id || job?.job_id || activeJobId;

  onMount(() => {
    mounted = true;
    beginJob(jobId);
  });

  onDestroy(() => {
    mounted = false;
    stopPolling();
    requestSequence += 1;
  });

  // App keeps this component mounted while moving from one report hash to another.
  // Treat an updated prop as a completely new request and invalidate in-flight work.
  $: if (mounted && jobId !== activeJobId) beginJob(jobId);

  function beginJob(nextJobId) {
    stopPolling();
    activeJobId = nextJobId || '';
    const sequence = ++requestSequence;
    error = '';
    job = null;
    loading = true;
    pollFailures = 0;
    pollNotice = '';
    project = findStoredProject(activeJobId);
    result = null;
    statusPollFailed = false;

    if (!activeJobId) {
      error = 'No forecast project was selected.';
      loading = false;
      return;
    }
    void refresh(activeJobId, sequence);
  }

  function findStoredProject(id) {
    try {
      const projects = JSON.parse(localStorage.getItem(PROJECTS_STORAGE_KEY) || '[]');
      return Array.isArray(projects)
        ? projects.find((item) => item?.job_id === id) || null
        : null;
    } catch {
      return null;
    }
  }

  function stopPolling() {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null;
  }

  function isCurrent(id, sequence) {
    return mounted && id === activeJobId && sequence === requestSequence;
  }

  function schedule(id, sequence, delay = POLL_INTERVAL_MS) {
    stopPolling();
    pollTimer = setTimeout(() => void refresh(id, sequence), delay);
  }

  async function refresh(id = activeJobId, sequence = requestSequence) {
    if (!id || !isCurrent(id, sequence)) return;

    try {
      const nextJob = await getForecast(id);
      if (!isCurrent(id, sequence)) return;
      job = nextJob;
      loading = false;
      error = '';
      pollFailures = 0;
      pollNotice = '';
      statusPollFailed = false;

      if (nextJob.status === 'completed') {
        const response = await getForecastResult(id);
        if (!isCurrent(id, sequence)) return;
        if (response.status === 202) {
          pollNotice = 'The report is complete and its result is being finalized.';
          schedule(id, sequence);
          return;
        }
        if (!response.data?.report) {
          error = 'The forecast completed, but its report result is unavailable.';
          statusPollFailed = true;
          return;
        }
        result = response.data;
        job = response.data.job || nextJob;
        return;
      }

      if (nextJob.status === 'failed') {
        error = nextJob.error || nextJob.message || 'The forecast project failed.';
        return;
      }

      schedule(id, sequence);
    } catch (requestError) {
      if (!isCurrent(id, sequence)) return;
      handleRequestError(requestError, id, sequence);
    }
  }

  function handleRequestError(requestError, id, sequence) {
    loading = false;
    const retryable = !requestError?.status
      || requestError.status === 429
      || requestError.status >= 500;

    if (retryable && pollFailures < MAX_POLL_FAILURES) {
      pollFailures += 1;
      pollNotice = `Status connection interrupted; retrying (${pollFailures}/${MAX_POLL_FAILURES}).`;
      schedule(id, sequence, POLL_INTERVAL_MS * pollFailures);
      return;
    }

    statusPollFailed = retryable;
    error = friendlyError(requestError);
  }

  function friendlyError(requestError) {
    if (requestError?.status === 404) return 'This forecast project could not be found.';
    if (requestError?.status === 429) return 'The forecast service is busy. Try reconnecting shortly.';
    if (requestError?.status === 503) return 'The forecast service is temporarily unavailable.';
    return requestError?.message || 'The forecast project could not be loaded.';
  }

  async function finishReport() {
    if (!job?.resumable || !activeJobId) return;
    stopPolling();
    const id = activeJobId;
    const sequence = ++requestSequence;
    error = '';
    loading = true;
    pollFailures = 0;
    pollNotice = '';
    statusPollFailed = false;

    try {
      const resumedJob = await resumeForecast(id);
      if (!isCurrent(id, sequence)) return;
      job = resumedJob;
      loading = false;
      await refresh(id, sequence);
    } catch (requestError) {
      if (!isCurrent(id, sequence)) return;
      loading = false;
      error = requestError?.message || 'The report could not be resumed.';
    }
  }

  function retryLoad() {
    if (!activeJobId) return;
    stopPolling();
    const sequence = ++requestSequence;
    error = '';
    loading = !job;
    pollFailures = 0;
    pollNotice = '';
    statusPollFailed = false;
    void refresh(activeJobId, sequence);
  }

  function openProjects() {
    location.hash = 'data';
  }

  function useInDashboard() {
    if (!dashboardJobId) return;
    void setActiveForecast(dashboardJobId);
    location.hash = 'daily';
  }

  function stripStructuredTable(markdown, table) {
    let content = String(markdown || '').replaceAll('\r\n', '\n');
    const tableMarkdown = table?.markdown?.trim();
    if (tableMarkdown) {
      content = content.replaceAll(String(tableMarkdown).replaceAll('\r\n', '\n'), '');
    }
    return content.trim();
  }

  function renderMarkdown(markdown) {
    if (!markdown?.trim()) return '';
    return DOMPurify.sanitize(marked.parse(markdown, { gfm: true, breaks: false }));
  }

  function getReportSections(reportOutline, table) {
    if (!Array.isArray(reportOutline?.sections)) return [];
    return reportOutline.sections
      .map((section, index) => {
        const markdown = stripStructuredTable(section?.content, table);
        return {
          key: `${index}:${section?.title || 'section'}`,
          title: section?.title?.trim() || `Section ${index + 1}`,
          html: renderMarkdown(markdown),
          markdown
        };
      })
      .filter((section) => section.markdown);
  }

  function getStructuredColumns(table, rows) {
    const described = Array.isArray(table?.columns)
      ? table.columns.filter((column) => column?.key)
      : [];
    if (described.length) return described;
    const keys = rows.flatMap((row) => row && typeof row === 'object' ? Object.keys(row) : []);
    return [...new Set(keys)].map((key) => ({ key, label: humanize(key) }));
  }

  function humanize(value) {
    return String(value || '')
      .replaceAll('_', ' ')
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function isAssessmentColumn(column) {
    return column?.key === 'assessment';
  }

  function isConfidenceColumn(column) {
    return column?.key === 'confidence';
  }

  function assessmentClass(value) {
    if (value === 'consistent') return 'opportunity';
    if (value === 'inconsistent') return 'risk';
    return 'watch';
  }

  function formatCell(value, column) {
    if (value === null || value === undefined || value === '') return '—';
    if (isConfidenceColumn(column) && Number.isFinite(Number(value))) {
      const confidence = Number(value);
      return new Intl.NumberFormat('en', {
        style: 'percent',
        maximumFractionDigits: confidence > 0 && confidence < 0.01 ? 1 : 0
      }).format(confidence);
    }
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (Array.isArray(value)) return value.map((item) => formatCell(item, {})).join(', ');
    if (typeof value === 'number') {
      return new Intl.NumberFormat('en', { maximumFractionDigits: 2 }).format(value);
    }
    if (typeof value === 'object') return JSON.stringify(value);
    if (isAssessmentColumn(column)) return humanize(value);
    return String(value);
  }

  function rowKey(row, index) {
    try {
      return `${index}:${JSON.stringify(structuredColumns.map((column) => row?.[column.key]))}`;
    } catch {
      return index;
    }
  }

  function stageLabel(value) {
    return humanize(value || 'queued');
  }

  function downloadReport() {
    if (!report?.markdown_content) return;
    const url = URL.createObjectURL(
      new Blob([report.markdown_content], { type: 'text/markdown;charset=utf-8' })
    );
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${report.report_id || activeJobId}.md`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
</script>

<svelte:head>
  <title>{reportTitle} · The Anam</title>
</svelte:head>

<div class="view reveal">
  <header class="report-header">
    <div class="title-copy">
      <button class="back-button" type="button" on:click={openProjects}>← Forecast projects</button>
      <h1 class="view-title">{reportTitle}</h1>
      {#if reportSummary}
        <p class="report-summary">{reportSummary}</p>
      {:else}
        <p class="view-sub">Forecast report · {activeJobId || 'No project selected'}</p>
      {/if}
    </div>
    {#if report}
      <div class="header-actions">
        <button class="ghost" type="button" on:click={downloadReport}>Download Markdown</button>
        <button class="primary" type="button" on:click={useInDashboard}>Use in dashboard</button>
      </div>
    {/if}
  </header>

  {#if loading && !job}
    <section class="panel loading-panel" aria-live="polite">
      <span class="status-dot active"></span>
      <b>Loading forecast project…</b>
    </section>
  {:else if error && !report}
    <section class="panel error-panel" role="alert">
      <span class="tag risk">Needs attention</span>
      <b>{error}</b>
      <div class="error-actions">
        {#if job?.resumable}
          <button class="primary" type="button" disabled={loading} on:click={finishReport}>
            {job?.resume_stage === 'report' ? 'Finish report' : 'Resume forecast'}
          </button>
        {:else if statusPollFailed || job?.status === 'completed'}
          <button class="primary" type="button" on:click={retryLoad}>Reconnect</button>
        {/if}
        <button class="ghost" type="button" on:click={openProjects}>Back to projects</button>
      </div>
    </section>
  {:else}
    <section class="project-summary panel" aria-live="polite">
      <div>
        <span class="kicker">Project status</span>
        <h2>{job?.status === 'completed' ? 'Report ready' : job?.message || 'Processing forecast'}</h2>
        {#if pollNotice}<p class="poll-notice">{pollNotice}</p>{/if}
      </div>
      <div class="status-progress">
        <progress max="100" value={job?.progress || 0}></progress>
        <div class="summary-meta">
          <span>{job?.progress || 0}%</span>
          <span>{stageLabel(job?.stage)}</span>
          {#if job?.project_id}<span>{job.project_id}</span>{/if}
        </div>
      </div>
    </section>

    {#each reportSections as section (section.key)}
      <section class="panel report-panel">
        <div class="section-head">
          <span class="kicker">Forecast analysis</span>
          <h2>{section.title}</h2>
        </div>
        <div class="markdown-body">{@html section.html}</div>
      </section>
    {/each}

    {#if fallbackReportHtml}
      <section class="panel report-panel">
        <div class="section-head">
          <span class="kicker">Forecast analysis</span>
          <h2>Generated report</h2>
        </div>
        <div class="markdown-body">{@html fallbackReportHtml}</div>
      </section>
    {/if}

    {#if structuredRows.length}
      <section class="panel structured-panel">
        <div class="panel-head">
          <div>
            <h2 class="kicker">{structured?.title || 'Evidence assessment'}</h2>
            <p class="panel-sub">
              Automated checks against the uploaded source files. These assessments remain provisional.
            </p>
          </div>
          <span class="tag watch">{structuredRows.length} claim{structuredRows.length === 1 ? '' : 's'}</span>
        </div>
        <p class="confidence-note">
          Confidence describes source-evidence matching for each claim; it is not forecast probability or a prediction interval.
        </p>
        <div class="table-scroll">
          <table class="result-table">
            <thead>
              <tr>
                {#each structuredColumns as column (column.key)}
                  <th>{column.label || humanize(column.key)}</th>
                {/each}
              </tr>
            </thead>
            <tbody>
              {#each structuredRows as row, rowIndex (rowKey(row, rowIndex))}
                <tr>
                  {#each structuredColumns as column (column.key)}
                    <td>
                      {#if isAssessmentColumn(column)}
                        <span class="tag {assessmentClass(row[column.key])}">
                          {formatCell(row[column.key], column)}
                        </span>
                      {:else if isConfidenceColumn(column)}
                        <span class="confidence-value">{formatCell(row[column.key], column)}</span>
                      {:else}
                        {formatCell(row[column.key], column)}
                      {/if}
                    </td>
                  {/each}
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </section>
    {/if}

    {#if report}
      <section class="panel dashboard-cta">
        <div>
          <span class="kicker">Next step</span>
          <h2>Use this forecast in the commercial dashboard</h2>
          <p>The dashboard will use this completed job as its active forecast while the narrative report remains available here.</p>
        </div>
        <button class="primary" type="button" on:click={useInDashboard}>Use in dashboard →</button>
      </section>
    {/if}
  {/if}
</div>

<style>
  .view {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .report-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
  }
  .title-copy {
    max-width: 940px;
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
  .report-summary {
    max-width: 900px;
    margin: 8px 0 0;
    color: var(--ink-2);
    font-size: 13.5px;
    line-height: 1.55;
  }
  .header-actions,
  .error-actions {
    display: flex;
    flex: 0 0 auto;
    gap: 8px;
  }
  .panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 18px 8px;
  }
  .panel-sub {
    max-width: 760px;
    margin: 4px 0 0;
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
  .error-actions {
    margin-left: auto;
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
  .project-summary h2,
  .dashboard-cta h2 {
    margin-top: 4px;
    font-family: var(--font-display);
    font-size: 22px;
  }
  .poll-notice {
    margin: 5px 0 0;
    color: var(--watch);
    font-size: 11.5px;
  }
  .status-progress {
    width: min(360px, 40%);
  }
  .status-progress progress {
    display: block;
    width: 100%;
    height: 6px;
    margin-bottom: 8px;
    accent-color: var(--accent);
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
  .section-head {
    padding: 18px 20px 0;
  }
  .section-head h2 {
    margin-top: 4px;
    color: var(--ink);
    font-family: var(--font-display);
    font-size: 21px;
  }
  .confidence-note {
    margin: 2px 18px 12px;
    padding: 8px 10px;
    border-left: 3px solid var(--watch);
    background: var(--watch-soft);
    color: var(--ink-2);
    font-size: 11.5px;
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
    padding: 9px 10px;
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
  .confidence-value {
    color: var(--ink);
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    white-space: nowrap;
  }
  .markdown-body {
    padding: 5px 20px 24px;
    color: var(--ink-2);
    font-size: 13px;
    line-height: 1.65;
    overflow-x: auto;
  }
  .markdown-body :global(h1),
  .markdown-body :global(h2) {
    margin: 22px 0 8px;
    color: var(--ink);
    font-family: var(--font-display);
    font-size: 18px;
    letter-spacing: 0;
  }
  .markdown-body :global(h3),
  .markdown-body :global(h4) {
    margin: 18px 0 6px;
    color: var(--ink);
    font-size: 14px;
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
  .dashboard-cta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 20px;
    border-color: rgba(11, 138, 118, 0.3);
    background: var(--accent-soft);
  }
  .dashboard-cta p {
    max-width: 760px;
    margin: 6px 0 0;
    color: var(--ink-2);
    font-size: 12.5px;
  }
  button.primary,
  button.ghost {
    border-radius: var(--radius);
    padding: 7px 12px;
    font-size: 12.5px;
    white-space: nowrap;
  }
  button.primary {
    border: none;
    background: var(--primary);
    color: #fff;
    font-weight: 600;
  }
  button.primary:hover {
    background: var(--primary-hover);
  }
  button.primary:disabled {
    cursor: wait;
    opacity: 0.6;
  }
  button.ghost {
    border: 1px solid var(--hairline-strong);
    background: var(--panel);
    color: var(--ink-2);
  }
  @media (max-width: 760px) {
    .report-header,
    .project-summary,
    .dashboard-cta {
      align-items: stretch;
      flex-direction: column;
    }
    .header-actions,
    .error-actions {
      margin-left: 0;
      flex-wrap: wrap;
    }
    .status-progress {
      width: 100%;
    }
    .summary-meta {
      justify-content: flex-start;
      text-align: left;
    }
    .dashboard-cta button {
      align-self: flex-start;
    }
  }
</style>
