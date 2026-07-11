async function forecastRequest(path, options = {}) {
  const response = await fetch(path, options);
  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

  if (!response.ok || payload?.success === false) {
    const error = new Error(payload?.error || `Forecast service returned HTTP ${response.status}.`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  if (!payload || payload.success !== true || !Object.prototype.hasOwnProperty.call(payload, 'data')) {
    const error = new Error('Forecast service returned a malformed response envelope.');
    error.status = response.status;
    error.payload = payload;
    error.code = 'invalid_response';
    throw error;
  }

  return { status: response.status, data: payload.data };
}

export async function submitForecast(markdownFiles, metadata = {}) {
  const files = Array.isArray(markdownFiles) ? markdownFiles : [markdownFiles];
  if (!files.length || files.some((file) => !(file instanceof Blob))) {
    throw new Error('At least one converted hotel data file is required.');
  }

  const form = new FormData();
  for (const file of files) form.append('files', file, file.name);
  form.append('data_profile', 'hotel');
  form.append('output_locale', metadata.outputLocale || 'en');

  const sourceNames = metadata.sourceNames?.length
    ? metadata.sourceNames
    : files.map((file) => file.name);
  form.append(
    'project_name',
    metadata.projectName ||
      (sourceNames.length === 1
        ? `Hotel forecast · ${sourceNames[0]}`
        : `Hotel forecast · ${sourceNames.length} data sources`)
  );
  form.append(
    'simulation_requirement',
    metadata.simulationRequirement ||
      'Forecast hotel demand by stay date and market segment. Identify booking pace, cancellation, staffing, rate, inventory, and channel risks and recommend concrete commercial actions.'
  );
  form.append(
    'additional_context',
    metadata.additionalContext ||
      `The frontend converted these hotel data sources into separate Markdown files while retaining every worksheet and column: ${sourceNames.join(', ')}.`
  );
  form.append(
    'report_prompt',
    metadata.reportPrompt ||
      'Write an English, evidence-backed hotel commercial outlook. Clearly separate source facts, deterministic calculations, and interpretation. Cover demand, booking pace, cancellations, budget and last-year comparisons, material risks and opportunities, then recommend scoped actions with rationale, owner, assumptions, and timing. Do not invent forecast intervals, confidence, financial impact, or exact rate and inventory changes when the uploaded data cannot support them.'
  );

  return (await forecastRequest('/api/forecast', { method: 'POST', body: form })).data;
}

export async function getForecast(jobId) {
  return (await forecastRequest(`/api/forecast/${encodeURIComponent(jobId)}`)).data;
}

export async function getLatestForecast() {
  return (await forecastRequest('/api/forecast/latest?data_profile=hotel')).data;
}

export async function resumeForecast(jobId) {
  return (
    await forecastRequest(`/api/forecast/${encodeURIComponent(jobId)}/resume`, {
      method: 'POST'
    })
  ).data;
}

export async function getForecastResult(jobId) {
  return forecastRequest(`/api/forecast/${encodeURIComponent(jobId)}/result`);
}
