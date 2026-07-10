<script>
  import { PROPERTIES, DATA_ASOF, DATA_SOURCE } from '../lib/constants.js';
  import { fmtInt } from '../lib/formatters.js';

  // Columns the ingest service (part 1) expects — mirrored in
  // docs/data_upload_plan.md. Validation here is client-side only; the real
  // /api/upload endpoint re-validates server-side once the backend lands.
  const REQUIRED_COLUMNS = [
    'date',
    'property',
    'rooms_available',
    'rooms_sold',
    'room_revenue',
    'adr',
    'occupancy',
    'market_segment',
    'channel',
    'guest_nationality',
    'lead_time_days',
    'cancellations',
    'budget_occupancy',
    'budget_adr',
    'ly_occupancy',
    'ly_adr',
    'otb_rooms'
  ];

  // idle -> validating -> report -> imported
  let stage = 'idle';
  let dragOver = false;
  let report = null;

  function onDrop(e) {
    e.preventDefault();
    dragOver = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) validateFile(file);
  }

  function onPick(e) {
    const file = e.target.files?.[0];
    if (file) validateFile(file);
    e.target.value = '';
  }

  function validateFile(file) {
    stage = 'validating';
    report = null;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || '');
      const lines = text.split(/\r?\n/).filter((l) => l.trim().length);
      const header = (lines[0] || '')
        .split(',')
        .map((h) => h.trim().toLowerCase().replace(/^"|"$/g, ''));
      const missing = REQUIRED_COLUMNS.filter((c) => !header.includes(c));
      const extra = header.filter((c) => c && !REQUIRED_COLUMNS.includes(c));

      // light content probing for the summary — not a full parse
      const dateIdx = header.indexOf('date');
      const propIdx = header.indexOf('property');
      const dates = [];
      const props = new Set();
      for (const line of lines.slice(1)) {
        const cells = line.split(',');
        if (dateIdx >= 0 && cells[dateIdx]) dates.push(cells[dateIdx].trim());
        if (propIdx >= 0 && cells[propIdx]) props.add(cells[propIdx].trim());
      }
      dates.sort();

      report = {
        name: file.name,
        sizeKb: Math.max(1, Math.round(file.size / 1024)),
        rows: Math.max(0, lines.length - 1),
        missing,
        extra,
        dateFrom: dates[0] ?? null,
        dateTo: dates[dates.length - 1] ?? null,
        properties: [...props],
        ok: missing.length === 0 && lines.length > 1 && file.name.toLowerCase().endsWith('.csv')
      };
      stage = 'report';
    };
    reader.onerror = () => {
      report = { name: file.name, ok: false, missing: [], extra: [], rows: 0, readError: true };
      stage = 'report';
    };
    reader.readAsText(file);
  }

  function importFile() {
    // backend pending — this will POST to /api/upload once part 1 is live
    stage = 'imported';
  }

  function reset() {
    stage = 'idle';
    report = null;
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

  // mock ingest status — becomes /api/ingest/status with the real backend
  const STATUS = PROPERTIES.map((p, i) => ({
    property: p,
    lastImport: DATA_ASOF,
    rows: [214, 213, 215][i] * 1, // one row per stay date in the daily export window
    status: 'ok'
  }));
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
          <th class="r">Rows</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {#each STATUS as s (s.property.id)}
          <tr>
            <td><span class="dot" style="background:{s.property.color}"></span>{s.property.name}</td>
            <td>{DATA_SOURCE}</td>
            <td>{s.lastImport}</td>
            <td class="r">{fmtInt(s.rows)}</td>
            <td><span class="tag opportunity">OK</span></td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>

  <section class="grid">
    <div class="panel">
      <div class="panel-head">
        <h2 class="kicker">Manual upload</h2>
        <button class="linkish" on:click={downloadTemplate}>Download CSV template</button>
      </div>
      <div class="panel-body">
        {#if stage === 'idle' || stage === 'validating'}
          <label
            class="dropzone"
            class:over={dragOver}
            on:dragover|preventDefault={() => (dragOver = true)}
            on:dragleave={() => (dragOver = false)}
            on:drop={onDrop}
          >
            <input type="file" accept=".csv" on:change={onPick} />
            {#if stage === 'validating'}
              <span>Checking file…</span>
            {:else}
              <span><b>Drop a daily CSV export here</b> or click to browse</span>
              <span class="hint">Same columns as the PMS/CRS daily export — see template</span>
            {/if}
          </label>
        {:else if stage === 'report' && report}
          <div class="report">
            <div class="report-head">
              <b class="num">{report.name}</b>
              <span class="hint">{report.sizeKb} KB · {fmtInt(report.rows)} data rows</span>
            </div>
            {#if report.ok}
              <p class="ok-line">
                <span class="tag opportunity">Ready</span>
                All {REQUIRED_COLUMNS.length} required columns present
                {#if report.dateFrom}· stay dates {report.dateFrom} → {report.dateTo}{/if}
                {#if report.properties.length}· properties: {report.properties.join(', ')}{/if}
              </p>
              <div class="actions">
                <button class="primary" on:click={importFile}>Import</button>
                <button class="ghost" on:click={reset}>Choose another file</button>
              </div>
            {:else}
              <p class="err-line">
                <span class="tag risk">Not importable</span>
                {#if report.readError}
                  The file could not be read.
                {:else if !report.name.toLowerCase().endsWith('.csv')}
                  Expected a .csv file.
                {:else if report.rows === 0}
                  No data rows found under the header.
                {:else}
                  Missing columns: <b>{report.missing.join(', ')}</b>
                {/if}
              </p>
              {#if report.extra?.length}
                <p class="hint">Ignored extra columns: {report.extra.join(', ')}</p>
              {/if}
              <div class="actions">
                <button class="ghost" on:click={reset}>Try another file</button>
              </div>
            {/if}
          </div>
        {:else if stage === 'imported'}
          <div class="report">
            <p class="ok-line">
              <span class="tag opportunity">Queued</span>
              <b>{report.name}</b> validated and queued for ingest. Dashboards refresh after the
              nightly run — or immediately once the ingest service (part 1) is connected.
            </p>
            <div class="actions">
              <button class="ghost" on:click={reset}>Upload another file</button>
            </div>
          </div>
        {/if}
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2 class="kicker">Connect a source</h2></div>
      <div class="panel-body sources">
        <div class="source">
          <div class="source-head">
            <b>Scheduled file export</b>
            <span class="tag opportunity">Recommended</span>
          </div>
          <p>
            PMS/CRS drops the daily CSV to a shared folder or SFTP by 05:30; the ingest job loads
            it and dashboards are ready by 06:00. No manual step in daily operations.
          </p>
        </div>
        <div class="source">
          <div class="source-head"><b>Direct PMS / CRS connector</b></div>
          <p>
            API pull straight from Opera Cloud / SynXis once credentials are provisioned. Planned
            after the pilot — the export schema stays identical, so no dashboard changes.
          </p>
        </div>
        <p class="hint">
          Both routes land in the same validation pipeline as manual upload. To set one up,
          contact the project team — see docs/data_upload_plan.md.
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
  .linkish {
    background: none;
    border: none;
    color: var(--accent-ink);
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
    min-height: 150px;
    border: 1.5px dashed var(--hairline-strong);
    border-radius: var(--radius-panel);
    background: var(--panel-tint);
    cursor: pointer;
    text-align: center;
    padding: 20px;
    font-size: 13px;
    color: var(--ink-2);
  }
  .dropzone.over {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .dropzone input {
    display: none;
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
  }
  button.primary {
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: var(--radius);
    padding: 6px 16px;
    font-size: 12.5px;
    font-weight: 600;
  }
  button.primary:hover {
    background: var(--accent-ink);
  }
  button.ghost {
    background: none;
    border: 1px solid var(--hairline-strong);
    border-radius: var(--radius);
    padding: 6px 12px;
    font-size: 12.5px;
    color: var(--ink-2);
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
</style>
