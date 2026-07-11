<script>
  import { onDestroy, onMount } from 'svelte';

  import { fmtInt } from '../lib/formatters.js';
  import { activeDashboard, loadActiveDashboard, setActiveForecast } from '../lib/dashboard-store.js';
  import {
    getForecast,
    getLatestForecast,
    resumeForecast,
    submitForecast
  } from '../lib/api.js';
  import { convertTabularFiles, HOTEL_SCHEMAS } from '../lib/tabular.js';

  const REQUIRED_COLUMNS = HOTEL_SCHEMAS.find((schema) => schema.id === 'pms-daily-export').columns;
  const FORECAST_STORAGE_KEY = 'anam-active-forecast-job';
  const PROJECTS_STORAGE_KEY = 'anam-forecast-projects';
  const MAX_PROJECTS = 12;
  const POLL_INTERVAL_MS = 2500;
  const MAX_POLL_FAILURES = 4;

  let stage = 'idle';
  let dragOver = false;
  let report = null;
  let forecastJob = null;
  let forecastError = '';
  let fileInput;
  let pollTimer;
  let projects = [];
  let selectedProjectId = '';
  let requestSequence = 0;
  let pollFailures = 0;
  let statusPollFailed = false;

  $: selectedProject = projects.find((project) => project.job_id === selectedProjectId) ?? null;
  $: canResumeForecast = Boolean(forecastJob?.resumable);
  $: resumeStage = forecastJob?.resume_stage
    || (forecastJob?.failed_stage === 'report' ? 'report' : 'graph');
  $: ingestDashboard = $activeDashboard.dashboard;
  $: ingestStatus = ingestDashboard?.raw?.data_status || null;
  $: ingestRows = (ingestDashboard?.metadata?.properties || []).map((property) => {
    const freshness = (ingestStatus?.freshness || []).find((item) => item.property === property.id);
    const stayDates = new Set(
      ingestDashboard.daily
        .filter((row) => row.property === property.id)
        .map((row) => row.date.getTime())
    ).size;
    return {
      property,
      source: ingestDashboard.metadata.sourceFiles.join(', ') || ingestDashboard.metadata.sourceLabel,
      received: freshness?.received_at || ingestDashboard.metadata.asOf,
      stayDates,
      freshness
    };
  });
  $: ingestWarnings = Array.isArray(ingestStatus?.warnings) ? ingestStatus.warnings : [];

  onMount(() => {
    loadProjects();
    // Populate the status table from the selected/latest completed hotel result.
    // A missing result is normal before the first upload.
    void loadActiveDashboard().catch(() => {});
    const jobId = sessionStorage.getItem(FORECAST_STORAGE_KEY);
    if (jobId?.startsWith('forecast_')) {
      const sequence = ++requestSequence;
      stage = 'processing';
      forecastJob = {
        job_id: jobId,
        status: 'queued',
        progress: 0,
        message: 'Restoring forecast status'
      };
      void refreshForecast(jobId, sequence);
    } else {
      if (projects.some((project) => project.status === 'queued' || project.status === 'running')) {
        void pollProjects();
      } else if (!projects.length) {
        void restoreLatestForecast();
      }
    }
  });

  onDestroy(() => {
    stopPolling();
    requestSequence += 1;
  });

  function onDrop(e) {
    e.preventDefault();
    dragOver = false;
    const files = e.dataTransfer?.files;
    if (files?.length) void validateFiles(files);
  }

  function onPick(e) {
    const files = e.target.files;
    if (files?.length) void validateFiles(files);
    e.target.value = '';
  }

  function stopPolling() {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null;
  }

  function loadProjects() {
    try {
      const stored = JSON.parse(localStorage.getItem(PROJECTS_STORAGE_KEY) || '[]');
      projects = Array.isArray(stored) ? stored.slice(0, MAX_PROJECTS) : [];
    } catch {
      projects = [];
    }
  }

  function persistProjects() {
    try {
      localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify(projects.slice(0, MAX_PROJECTS)));
    } catch {
      // The backend remains authoritative if browser storage is unavailable.
    }
  }

  function upsertProject(job, metadata = {}) {
    if (!job?.job_id) return;
    const existing = projects.find((project) => project.job_id === job.job_id);
    const next = {
      ...(existing || {}),
      job_id: job.job_id,
      project_id: job.project_id || existing?.project_id || '',
      report_id: job.report_id || existing?.report_id || '',
      status: job.status || existing?.status || 'queued',
      stage: job.stage || existing?.stage || 'queued',
      progress: Number.isFinite(job.progress) ? job.progress : existing?.progress || 0,
      message: job.message || existing?.message || 'Forecast queued',
      error: job.error || existing?.error || '',
      created_at: job.created_at || existing?.created_at || new Date().toISOString(),
      updated_at: job.updated_at || existing?.updated_at || new Date().toISOString(),
      sourceNames: metadata.sourceNames || existing?.sourceNames || [],
      name: metadata.name || existing?.name || 'Hotel forecast project'
    };
    projects = [next, ...projects.filter((project) => project.job_id !== job.job_id)].slice(0, MAX_PROJECTS);
    persistProjects();
  }

  function statusLabel(project) {
    if (project.status === 'completed') return 'Ready';
    if (project.status === 'failed') return 'Needs attention';
    if (project.status === 'running') return `${project.progress || 0}% · ${stageLabel(project.stage)}`;
    return 'Queued';
  }

  function stageLabel(stage) {
    return String(stage || 'queued').replaceAll('_', ' ');
  }

  function statusClass(status) {
    if (status === 'completed') return 'complete';
    if (status === 'failed') return 'failed';
    return 'active';
  }

  function openProject(project) {
    if (!project?.job_id) return;
    selectedProjectId = project.job_id;
    location.hash = `report/${encodeURIComponent(project.job_id)}`;
  }

  function useInDashboard(project = selectedProject || forecastJob) {
    if (!project?.job_id) return;
    void setActiveForecast(project.job_id);
    location.hash = 'daily';
  }

  function formatReceived(value) {
    if (!value) return 'Timestamp unavailable';
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return 'Timestamp unavailable';
    return new Intl.DateTimeFormat('en-GB', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: ingestDashboard?.metadata?.timezone || 'Asia/Ho_Chi_Minh'
    }).format(date);
  }

  async function restoreLatestForecast() {
    const sequence = ++requestSequence;
    try {
      const job = await getLatestForecast();
      if (sequence !== requestSequence || !job?.job_id) return;
      upsertProject(job, {
        name: 'Latest completed forecast',
        sourceNames: ['Latest completed forecast']
      });
      selectedProjectId = job.job_id;
      stage = 'idle';
      forecastJob = job;
    } catch {
      // No completed forecast is a normal first-run state.
    }
  }

  async function validateFiles(fileList) {
    const files = Array.from(fileList);
    const sequence = ++requestSequence;
    stopPolling();
    sessionStorage.removeItem(FORECAST_STORAGE_KEY);
    stage = 'validating';
    report = null;
    forecastJob = null;
    forecastError = '';
    pollFailures = 0;
    statusPollFailed = false;

    try {
      const converted = await convertTabularFiles(files);
      if (sequence !== requestSequence) return;
      report = {
        ...converted,
        sizeKb: Math.max(1, Math.round(converted.sourceSize / 1024)),
        markdownKb: Math.max(1, Math.round(converted.markdownSize / 1024))
      };
      stage = 'report';
      void runForecast();
    } catch (error) {
      if (sequence !== requestSequence) return;
      report = {
        name: files.length === 1 ? files[0].name : `${files.length} hotel data files`,
        sizeKb: Math.max(1, Math.round(files.reduce((sum, file) => sum + file.size, 0) / 1024)),
        rows: 0,
        missing: [],
        extra: [],
        ok: false,
        error: error.message || 'The file could not be read.'
      };
      stage = 'report';
    }
  }

  function friendlyForecastError(error) {
    if (error?.status === 503) {
      return 'The forecast service is temporarily unavailable.';
    }
    return error?.message || 'The forecast service could not be reached.';
  }

  async function runForecast() {
    if (!report?.ok || !report.markdownFiles?.length) return;
    const sequence = ++requestSequence;
    stopPolling();
    stage = 'submitting';
    forecastJob = null;
    forecastError = '';
    pollFailures = 0;
    statusPollFailed = false;

    try {
      const job = await submitForecast(report.markdownFiles, {
        sourceNames: report.sourceNames,
        projectName: `The Anam · ${report.sourceNames.length} data source${report.sourceNames.length === 1 ? '' : 's'}`
      });
      if (sequence !== requestSequence) return;
      forecastJob = job;
      selectedProjectId = job.job_id;
      upsertProject(job, {
        name: `The Anam · ${report.sourceNames.length} data source${report.sourceNames.length === 1 ? '' : 's'}`,
        sourceNames: report.sourceNames
      });
      stage = 'processing';
      sessionStorage.setItem(FORECAST_STORAGE_KEY, job.job_id);
      await refreshForecast(job.job_id, sequence);
    } catch (error) {
      if (sequence !== requestSequence) return;
      forecastError = friendlyForecastError(error);
      stage = 'failed';
    }
  }

  async function retryForecast() {
    if (statusPollFailed && forecastJob?.job_id) {
      const sequence = ++requestSequence;
      stopPolling();
      pollFailures = 0;
      statusPollFailed = false;
      forecastError = '';
      stage = 'processing';
      forecastJob = { ...forecastJob, message: 'Reconnecting to forecast status' };
      sessionStorage.setItem(FORECAST_STORAGE_KEY, forecastJob.job_id);
      await refreshForecast(forecastJob.job_id, sequence);
      return;
    }

    if (!canResumeForecast) {
      await runForecast();
      return;
    }

    const sequence = ++requestSequence;
    stopPolling();
    pollFailures = 0;
    forecastError = '';
    stage = 'processing';
    forecastJob = {
      ...forecastJob,
      status: 'queued',
      message: resumeStage === 'report'
        ? 'Requesting saved-report finalization'
        : 'Requesting graph-processing resume'
    };

    try {
      const job = await resumeForecast(forecastJob.job_id);
      if (sequence !== requestSequence) return;
      forecastJob = job;
      sessionStorage.setItem(FORECAST_STORAGE_KEY, job.job_id);
      await refreshForecast(job.job_id, sequence);
    } catch (error) {
      if (sequence !== requestSequence) return;
      forecastError = friendlyForecastError(error);
      stage = 'failed';
    }
  }

  async function refreshForecast(jobId, sequence = requestSequence) {
    try {
      const job = await getForecast(jobId);
      if (sequence !== requestSequence) return;
      pollFailures = 0;
      statusPollFailed = false;
      forecastJob = job;
      upsertProject(job);

      if (job.status === 'completed') {
        sessionStorage.removeItem(FORECAST_STORAGE_KEY);
        stage = 'completed';
        scheduleProjectPoll();
        return;
      }

      if (job.status === 'failed') {
        if (!job.resumable) {
          sessionStorage.removeItem(FORECAST_STORAGE_KEY);
        }
        forecastError = job.error || job.message || 'The forecast pipeline failed.';
        stage = 'failed';
        scheduleProjectPoll();
        return;
      }

      stage = 'processing';
      scheduleProjectPoll();
    } catch (error) {
      if (sequence !== requestSequence) return;
      const retryable = !error?.status || error.status === 429 || error.status >= 500;
      if (!retryable) {
        forecastError = friendlyForecastError(error);
        stage = 'failed';
        return;
      }
      pollFailures += 1;
      if (pollFailures <= MAX_POLL_FAILURES) {
        stage = 'processing';
        forecastJob = {
          ...forecastJob,
          message: `Status connection interrupted; retrying (${pollFailures}/${MAX_POLL_FAILURES})`
        };
        scheduleProjectPoll(POLL_INTERVAL_MS * pollFailures);
        return;
      }
      forecastError = friendlyForecastError(error);
      statusPollFailed = true;
      stage = 'failed';
    }
  }

  function scheduleProjectPoll(delay = POLL_INTERVAL_MS) {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = setTimeout(() => void pollProjects(), delay);
  }

  async function pollProjects() {
    const pending = projects.filter((project) =>
      project.status === 'queued' || project.status === 'running'
    );
    if (!pending.length) return;

    const results = await Promise.all(
      pending.map(async (project) => {
        try {
          return await getForecast(project.job_id);
        } catch {
          return null;
        }
      })
    );
    results.filter(Boolean).forEach((job) => {
      upsertProject(job);
      if (job.job_id === selectedProjectId) forecastJob = job;
    });

    if (selectedProjectId) {
      const selected = projects.find((project) => project.job_id === selectedProjectId);
      if (selected?.status === 'completed') stage = 'completed';
      if (selected?.status === 'failed') {
        forecastError = selected.error || selected.message || 'The forecast pipeline failed.';
        stage = 'failed';
      }
    }

    if (projects.some((project) => project.status === 'queued' || project.status === 'running')) {
      scheduleProjectPoll();
    }
  }

  function reset() {
    requestSequence += 1;
    stopPolling();
    sessionStorage.removeItem(FORECAST_STORAGE_KEY);
    stage = 'idle';
    report = null;
    forecastJob = null;
    forecastError = '';
    pollFailures = 0;
    statusPollFailed = false;
  }

  function downloadMarkdown() {
    if (!report?.files?.length) return;
    const markdown = report.files
      .map((file) => `# Source: ${file.sourceName}\n\n${file.markdown}`)
      .join('\n\n---\n\n');
    const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = report.files.length === 1 ? report.files[0].filename : 'the_anam_hotel_data_bundle.md';
    a.click();
    URL.revokeObjectURL(url);
  }

  function downloadTemplate() {
    const sample = [
      REQUIRED_COLUMNS.join(','),
      '2026-07-09,ACR,213,196,41160,210.00,0.92,OTA,Booking.com,KR,21,3,0.89,205.00,0.87,198.00,180',
      '2026-07-09,AMN,127,101,15453,153.00,0.80,Direct,Brand.com,VN,14,1,0.82,155.00,0.75,149.00,95'
    ].join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([sample], { type: 'text/csv' }));
    a.download = 'anam_daily_template.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }

</script>

<div class="view reveal">
  <header>
    <h1 class="view-title">Data</h1>
    <p class="view-sub">Daily exports feeding the dashboard, and how to load new data</p>
  </header>

  <section class="panel">
    <div class="panel-head"><h2 class="kicker">Ingest status — last daily export</h2></div>
    <table class="data">
      <thead>
        <tr>
          <th>Property</th>
          <th>Source</th>
          <th>Received</th>
          <th class="r">Stay dates</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {#each ingestRows as s (s.property.id)}
          <tr>
            <td><span class="dot" style="background:{s.property.color}"></span>{s.property.name}</td>
            <td>{s.source}</td>
            <td title={s.freshness?.reason || ''}>{formatReceived(s.received)}</td>
            <td class="r">{fmtInt(s.stayDates)}</td>
            <td>
              {#if ingestStatus?.status === 'ready'}
                <span class="tag opportunity">Accepted</span>
              {:else}
                <span class="tag watch">Partial</span>
              {/if}
            </td>
          </tr>
        {:else}
          <tr>
            <td colspan="5" class="empty-status">
              {#if $activeDashboard.status === 'loading'}
                Loading the latest completed hotel result…
              {:else}
                No completed hotel result is selected yet. Upload data to create one.
              {/if}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
    {#if ingestStatus}
      <div class="ingest-summary">
        <span><b>{fmtInt(ingestStatus.accepted_rows)}</b> source rows accepted</span>
        <span><b>{fmtInt(ingestStatus.rejected_rows)}</b> rejected</span>
        {#if ingestStatus.missing_feeds?.length}
          <span>Missing feeds: {ingestStatus.missing_feeds.join(', ')}</span>
        {/if}
        {#if ingestStatus.optional_missing_feeds?.length}
          <span>Optional feeds not uploaded: {ingestStatus.optional_missing_feeds.join(', ')}</span>
        {/if}
        {#if ingestWarnings.length}
          <details>
            <summary>{ingestWarnings.length} data note{ingestWarnings.length === 1 ? '' : 's'}</summary>
            <ul>
              {#each ingestWarnings as warning}<li>{warning}</li>{/each}
            </ul>
          </details>
        {/if}
      </div>
    {/if}
  </section>

  <section class="grid">
    <div class="panel">
      <div class="panel-head">
        <h2 class="kicker">Manual upload</h2>
        <button class="linkish" on:click={downloadTemplate}>Download CSV template</button>
      </div>
      <div class="panel-body" aria-live="polite">
        {#if stage === 'idle' || stage === 'validating'}
          <!-- semantic button = native keyboard support, single tab stop;
               the real file input is out of the tab order entirely -->
          <input
            bind:this={fileInput}
            class="file-input"
            type="file"
            multiple
            accept=".csv,.xlsx,.md,.markdown,text/csv,text/markdown,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            tabindex="-1"
            aria-hidden="true"
            on:change={onPick}
          />
          <button
            type="button"
            class="dropzone"
            class:over={dragOver}
            aria-label="Upload CSV, XLSX, or Markdown hotel data files"
            on:click={() => fileInput?.click()}
            on:dragover|preventDefault={() => (dragOver = true)}
            on:dragleave={() => (dragOver = false)}
            on:drop|preventDefault={onDrop}
          >
            {#if stage === 'validating'}
              <span>Checking file…</span>
            {:else}
              <span><b>Drop CSV, Excel, or Markdown files here</b> or click to browse</span>
              <span class="hint">Include performance data; a project starts automatically after validation</span>
            {/if}
          </button>
        {:else if stage === 'report' && report}
          <div class="report">
            <div class="report-head">
              <b class="num">{report.name}</b>
              <span class="hint">
                {report.sizeKb} KB
                {#if report.rowCount !== null && report.rowCount !== undefined}
                  · {fmtInt(report.rowCount || report.rows)} data rows
                {/if}
                {#if report.sheetCount}· {report.sheetCount} {report.sheetCount === 1 ? 'sheet' : 'sheets'}{/if}
              </span>
            </div>
            {#if report.ok}
              <p class="ok-line">
                <span class="tag opportunity">Ready</span>
                {report.matchedSchemas.length} recognized dataset{report.matchedSchemas.length === 1 ? '' : 's'}
                {#if report.dateFrom}· stay dates {report.dateFrom} → {report.dateTo}{/if}
                {#if report.properties.length}· properties: {report.properties.join(', ')}{/if}
              </p>
              <p class="hint">
                Converted to {report.markdownFiles.length} Markdown file{report.markdownFiles.length === 1 ? '' : 's'} · {report.markdownKb} KB
              </p>
              <div class="file-list">
                {#each report.files as file (file.markdownFile)}
                  <span><b>{file.sourceName}</b> · {file.matchedSchemas.map((schema) => schema.label).join(', ')}</span>
                {/each}
              </div>
              {#if report.extra?.length}
                <p class="hint">Additional columns retained: {report.extra.join(', ')}</p>
              {/if}
              <div class="actions">
                <button class="primary" on:click={runForecast}>Create project &amp; run forecast</button>
                <button class="ghost" on:click={downloadMarkdown}>Download Markdown</button>
                <button class="ghost" on:click={reset}>Choose another file</button>
              </div>
            {:else}
              <p class="err-line" role="alert">
                <span class="tag risk">Not importable</span>
                {#if report.error}
                  {report.error}
                {:else}
                  Missing columns: <b>{report.missing.join(', ')}</b>
                {/if}
              </p>
              {#if report.extra?.length}
                <p class="hint">Detected additional columns: {report.extra.join(', ')}</p>
              {/if}
              <div class="actions">
                <button class="ghost" on:click={reset}>Try another file</button>
              </div>
            {/if}
          </div>
        {:else if stage === 'submitting'}
          <div class="report">
            <p class="ok-line">
              <span class="tag watch">Submitting</span>
              Sending <b>{report.markdownFiles.length} hotel data file{report.markdownFiles.length === 1 ? '' : 's'}</b> to the forecast service…
            </p>
            <progress class="progress" max="100"></progress>
          </div>
        {:else if stage === 'processing' && forecastJob}
          <div class="report">
            <p class="ok-line">
              <span class="tag watch">{forecastJob.status || 'queued'}</span>
              <b>{forecastJob.message || 'Forecast processing'}</b>
            </p>
            <progress class="progress" max="100" value={forecastJob.progress || 0}></progress>
            <p class="hint job-meta">
              {forecastJob.progress || 0}% · {forecastJob.stage || 'queued'} · {forecastJob.job_id}
            </p>
          </div>
        {:else if stage === 'completed'}
          <div class="report">
            <p class="ok-line">
              <span class="tag opportunity">Complete</span>
              <b>Forecast project is ready</b>
            </p>
            <p class="hint job-meta">
              Review the generated narrative and evidence assessment, or use this completed job in the dashboard.
            </p>
            <div class="actions">
              {#if selectedProject}
                <button class="primary" on:click={() => openProject(selectedProject)}>Open report</button>
                <button class="ghost dashboard-action" on:click={() => useInDashboard(selectedProject)}>Use in dashboard</button>
              {/if}
              <button class="ghost" on:click={reset}>Upload another file</button>
            </div>
          </div>
        {:else if stage === 'failed'}
          <div class="report">
            <p class="err-line" role="alert">
              <span class="tag risk">Forecast failed</span>
              {forecastError}
            </p>
            {#if forecastJob?.job_id}<p class="hint job-meta">{forecastJob.job_id}</p>{/if}
            <div class="actions">
              {#if canResumeForecast || report?.ok}
                <button class="primary" on:click={retryForecast}>
                  {canResumeForecast
                    ? resumeStage === 'report' ? 'Finish report' : 'Resume graph'
                    : 'Try again'}
                </button>
              {/if}
              <button class="ghost" on:click={reset}>Choose another file</button>
            </div>
          </div>
        {/if}
      </div>
    </div>

    <div class="panel project-panel">
      <div class="panel-head">
        <div>
          <h2 class="kicker">Forecast projects</h2>
          <p class="panel-sub">Live job status · click a project to open its report</p>
        </div>
        <span class="project-count">{projects.length}</span>
      </div>
      <div class="project-list" aria-live="polite">
        {#if projects.length}
          {#each projects as project (project.job_id)}
            <button
              type="button"
              class="project-tab"
              class:selected={project.job_id === selectedProjectId}
              on:click={() => openProject(project)}
              aria-label={`Open ${project.name}, ${statusLabel(project)}`}
            >
              <span class="project-status-dot {statusClass(project.status)}" aria-hidden="true"></span>
              <span class="project-copy">
                <b>{project.name}</b>
                <span>{project.sourceNames?.join(', ') || 'Uploaded hotel data'}</span>
              </span>
              <span class="project-state {statusClass(project.status)}">{statusLabel(project)}</span>
              <span class="project-arrow" aria-hidden="true">›</span>
            </button>
          {/each}
        {:else}
          <div class="empty-projects">
            <b>No forecast projects yet</b>
            <span>Upload hotel data to create the first project.</span>
          </div>
        {/if}
      </div>
    </div>
  </section>

  <section class="panel source-panel">
    <div class="panel-head"><h2 class="kicker">Connect a source</h2></div>
    <div class="source-grid">
      <div class="source">
        <div class="source-head">
          <b>Scheduled file export</b>
          <span class="tag opportunity">Recommended</span>
        </div>
        <p>
          PMS/CRS drops the daily CSV or XLSX workbook to a shared folder or SFTP by 05:30; the
          ingest job loads it and dashboards are ready by 06:00.
        </p>
      </div>
      <div class="source">
        <div class="source-head"><b>Direct PMS / CRS connector</b></div>
        <p>
          API pull straight from Opera Cloud / SynXis once credentials are provisioned. The export
          schema stays identical, so no dashboard changes are required.
        </p>
      </div>
    </div>
  </section>

</div>

<style>
  .view {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .panel-head {
    padding: 12px 16px 8px;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }
  .panel-body {
    padding: 4px 16px 16px;
  }
  .grid {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr);
    gap: 12px;
    align-items: start;
  }
  .dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 7px;
  }
  .empty-status {
    padding: 18px 16px;
    color: var(--ink-3);
    text-align: center;
  }
  .ingest-summary {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    padding: 9px 16px 13px;
    border-top: 1px solid var(--hairline);
    color: var(--ink-3);
    font-size: 11.5px;
  }
  .ingest-summary details {
    flex-basis: 100%;
  }
  .ingest-summary summary {
    cursor: pointer;
  }
  .ingest-summary ul {
    margin: 6px 0 0;
    padding-left: 18px;
  }
  .linkish {
    background: none;
    border: none;
    color: var(--gold-ink);
    font-size: 12px;
    font-weight: 600;
    padding: 0;
    cursor: pointer;
  }
  .dropzone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: 100%;
    min-height: 150px;
    border: 1.5px dashed var(--hairline-strong);
    border-radius: var(--radius-panel);
    background: var(--panel-tint);
    cursor: pointer;
    text-align: center;
    padding: 20px;
    font-size: 13px;
    font-family: inherit;
    color: var(--ink-2);
  }
  .dropzone.over {
    border-color: var(--gold);
    background: var(--gold-soft);
  }
  .dropzone:focus-visible {
    outline: 2px solid var(--gold);
    outline-offset: 2px;
  }
  .file-input {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    overflow: hidden;
    clip: rect(0 0 0 0);
  }
  .hint {
    font-size: 11.5px;
    color: var(--ink-3);
  }
  .report {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .report-head {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
  }
  .ok-line,
  .err-line {
    margin: 0;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .file-list {
    display: flex;
    flex-direction: column;
    gap: 3px;
    font-size: 11.5px;
    color: var(--ink-2);
    overflow-wrap: anywhere;
  }
  .progress {
    width: 100%;
    height: 8px;
    accent-color: var(--accent);
  }
  .job-meta {
    margin: 0;
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }
  .panel-sub {
    margin: 3px 0 0;
    color: var(--ink-3);
    font-size: 11.5px;
  }
  .project-count {
    min-width: 24px;
    padding: 2px 7px;
    border: 1px solid var(--hairline);
    border-radius: 999px;
    color: var(--ink-3);
    font-size: 11px;
    text-align: center;
  }
  .project-list {
    display: flex;
    flex-direction: column;
    padding: 0 10px 10px;
    gap: 4px;
  }
  .project-tab {
    display: grid;
    grid-template-columns: 8px minmax(0, 1fr) auto 12px;
    align-items: center;
    gap: 9px;
    width: 100%;
    padding: 10px 8px;
    border: 1px solid transparent;
    border-radius: var(--radius);
    background: transparent;
    color: var(--ink-2);
    text-align: left;
  }
  .project-tab:hover,
  .project-tab.selected {
    border-color: var(--hairline);
    background: var(--panel-tint);
  }
  .project-status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--watch);
  }
  .project-status-dot.complete {
    background: var(--good);
  }
  .project-status-dot.failed {
    background: var(--risk);
  }
  .project-copy {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 2px;
  }
  .project-copy b,
  .project-copy span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .project-copy b {
    color: var(--ink);
    font-size: 12.5px;
  }
  .project-copy span {
    color: var(--ink-3);
    font-size: 10.5px;
  }
  .project-state {
    color: var(--watch);
    font-size: 10.5px;
    white-space: nowrap;
  }
  .project-state.complete {
    color: var(--good);
  }
  .project-state.failed {
    color: var(--risk);
  }
  .project-arrow {
    color: var(--ink-3);
    font-size: 18px;
    line-height: 1;
  }
  .empty-projects {
    display: flex;
    flex-direction: column;
    gap: 3px;
    padding: 20px 10px 24px;
    color: var(--ink-3);
    font-size: 11.5px;
  }
  .empty-projects b {
    color: var(--ink-2);
    font-size: 12.5px;
  }
  button.primary {
    background: var(--primary);
    color: #fff;
    border: none;
    border-radius: var(--radius);
    padding: 6px 16px;
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
  .source-panel {
    margin-top: 0;
  }
  .source-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    padding: 4px 16px 16px;
  }
  .sources {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .source {
    border: 1px solid var(--hairline);
    border-radius: var(--radius);
    padding: 10px 12px;
  }
  .source-head {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }
  .source p {
    margin: 0;
    font-size: 12.5px;
    color: var(--ink-2);
  }
  @media (max-width: 900px) {
    .grid {
      grid-template-columns: 1fr;
    }
    .source-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
