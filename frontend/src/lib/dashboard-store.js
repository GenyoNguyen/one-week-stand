import { derived, get, writable } from 'svelte/store';

import { getForecastResult, getLatestForecast } from './forecast-client.js';
import { normalizeForecastResult } from './forecast-result.js';
import { setDisplayCurrency } from './formatters.js';
import { alertStatus, focusAlert } from './stores.js';

export const ACTIVE_DASHBOARD_STORAGE_KEY = 'anam-active-dashboard-job';

const initialState = {
  status: 'idle',
  jobId: null,
  dashboard: null,
  error: null,
  loadedAt: null
};

export const activeDashboard = writable(initialState);
export const dashboardMetadataStore = derived(activeDashboard, ($state) => $state.dashboard?.metadata ?? null);
export const activeDashboardGeneration = writable(0);

let pendingLoad = null;
let loadGeneration = 0;

function storage() {
  return typeof localStorage === 'undefined' ? null : localStorage;
}

function persistedJobId() {
  const jobId = storage()?.getItem(ACTIVE_DASHBOARD_STORAGE_KEY);
  return jobId?.startsWith('forecast_') ? jobId : null;
}

export function setActiveForecast(jobId, { load = false } = {}) {
  const normalized = String(jobId || '').trim();
  if (normalized && !normalized.startsWith('forecast_')) {
    throw new Error('Forecast job IDs must start with forecast_.');
  }
  const previousJobId = get(activeDashboard).jobId || persistedJobId();
  if ((normalized || null) !== (previousJobId || null)) {
    // Alert IDs are deterministic property/date keys, so decisions from one
    // result must never hide changed evidence in another result.
    alertStatus.set({});
    focusAlert.set(null);
  }
  loadGeneration += 1;
  pendingLoad = null;
  if (normalized) storage()?.setItem(ACTIVE_DASHBOARD_STORAGE_KEY, normalized);
  else storage()?.removeItem(ACTIVE_DASHBOARD_STORAGE_KEY);
  activeDashboard.set({ ...initialState, jobId: normalized || null });
  activeDashboardGeneration.update((value) => value + 1);
  return load ? loadActiveDashboard({ jobId: normalized || null, force: true }) : Promise.resolve(null);
}

async function resolveJobId(explicitJobId) {
  if (explicitJobId) return explicitJobId;
  const persisted = persistedJobId();
  if (persisted) return persisted;
  const current = get(activeDashboard).jobId;
  if (current) return current;
  const latest = await getLatestForecast();
  if (!latest?.job_id) throw new Error('The forecast service did not return a completed job ID.');
  return latest.job_id;
}

export function loadActiveDashboard({ jobId = null, force = false } = {}) {
  const state = get(activeDashboard);
  const desiredJobId = jobId || persistedJobId();
  if (!force && state.status === 'ready' && (!desiredJobId || state.jobId === desiredJobId)) {
    return Promise.resolve(state.dashboard);
  }
  if (!force && pendingLoad && (!desiredJobId || state.jobId === desiredJobId)) return pendingLoad;

  const generation = ++loadGeneration;
  const task = (async () => {
    activeDashboard.update((value) => ({ ...value, status: 'loading', error: null }));
    try {
      const resolvedJobId = await resolveJobId(jobId);
      if (generation !== loadGeneration) throw Object.assign(new Error('Dashboard load was superseded.'), { code: 'load_superseded' });
      activeDashboard.update((value) => ({ ...value, jobId: resolvedJobId }));
      const response = await getForecastResult(resolvedJobId);
      if (generation !== loadGeneration) throw Object.assign(new Error('Dashboard load was superseded.'), { code: 'load_superseded' });
      if (response.status === 202) {
        const error = new Error(response.data?.message || 'This forecast is still processing.');
        error.code = 'forecast_pending';
        error.status = 202;
        throw error;
      }
      const dashboard = normalizeForecastResult(response.data);
      dashboard.jobId = dashboard.jobId || resolvedJobId;
      setDisplayCurrency(dashboard.metadata.currency);
      activeDashboard.set({
        status: 'ready',
        jobId: resolvedJobId,
        dashboard,
        error: null,
        loadedAt: new Date()
      });
      return dashboard;
    } catch (error) {
      if (generation === loadGeneration) {
        activeDashboard.update((value) => ({ ...value, status: 'error', dashboard: null, error }));
      }
      throw error;
    } finally {
      if (pendingLoad === task) pendingLoad = null;
    }
  })();
  pendingLoad = task;
  return task;
}

export async function loadLatestDashboard({ force = true } = {}) {
  const latest = await getLatestForecast();
  if (!latest?.job_id) throw new Error('No completed forecast is available.');
  return setActiveForecast(latest.job_id).then(() => loadActiveDashboard({ jobId: latest.job_id, force }));
}

export function invalidateDashboard() {
  loadGeneration += 1;
  pendingLoad = null;
  activeDashboard.update((value) => ({ ...value, status: 'idle', dashboard: null, error: null }));
  activeDashboardGeneration.update((value) => value + 1);
}

export function resetDashboardState() {
  loadGeneration += 1;
  pendingLoad = null;
  storage()?.removeItem(ACTIVE_DASHBOARD_STORAGE_KEY);
  activeDashboard.set(initialState);
  activeDashboardGeneration.set(0);
  setDisplayCurrency('USD');
}
