// API layer. Once the FastAPI backend (parts 1–3) is live these functions
// switch to fetch('/api/...'); the mock module keeps identical shapes so no
// view code changes. A small artificial latency keeps loading states honest.
import * as mock from './mock.js';

const simulate = (data, ms = 180) => new Promise((res) => setTimeout(() => res(data), ms));

export const getSeries = (propertyId, fromLead, toLead) =>
  simulate(mock.series(propertyId, fromLead, toLead));

export const getSegments = (propertyId) => simulate(mock.segments(propertyId));
export const getSegmentMix = () => simulate(mock.segmentMixByProperty());
export const getChannels = () => simulate(mock.channels());
export const getNationalities = () => simulate(mock.nationalities());
export const getPaceCurve = (propertyId) => simulate(mock.paceCurve(propertyId));
export const getPickupCalendar = (propertyId) => simulate(mock.pickupCalendar(propertyId));
export const getAlerts = () => simulate(mock.ALERTS);

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

  return { status: response.status, data: payload?.data };
}

export async function submitForecast(markdownFiles, metadata = {}) {
  const files = Array.isArray(markdownFiles) ? markdownFiles : [markdownFiles];
  if (!files.length || files.some((file) => !(file instanceof Blob))) {
    throw new Error('At least one converted hotel data file is required.');
  }

  const form = new FormData();
  for (const file of files) form.append('files', file, file.name);
  form.append('data_profile', 'hotel');

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

  return (await forecastRequest('/api/forecast', { method: 'POST', body: form })).data;
}

export async function getForecast(jobId) {
  return (await forecastRequest(`/api/forecast/${encodeURIComponent(jobId)}`)).data;
}

export async function getLatestForecast() {
  return (await forecastRequest('/api/forecast/latest')).data;
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
