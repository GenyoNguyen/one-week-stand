import * as mock from './mock.js';
import {
  getForecast,
  getForecastResult,
  getLatestForecast,
  resumeForecast,
  submitForecast
} from './forecast-client.js';
import { loadActiveDashboard } from './dashboard-store.js';
import {
  selectAlerts,
  selectChannels,
  selectNationalities,
  selectPaceCurve,
  selectPickupCalendar,
  selectSegmentMix,
  selectSegments,
  selectSeries
} from './forecast-result.js';

export { getForecast, getForecastResult, getLatestForecast, resumeForecast, submitForecast };

const env = import.meta.env || {};
export const DASHBOARD_DEMO_MODE =
  env.VITE_DASHBOARD_DEMO === 'true' || env.VITE_DEMO_MODE === 'true';

const simulate = (data, ms = 180) => new Promise((resolve) => setTimeout(() => resolve(data), ms));
const live = async (selector) => selector(await loadActiveDashboard());

// Mock data is available only when explicitly enabled. A missing or malformed
// live result is surfaced to the view and is never replaced with demo figures.
export const getSeries = (propertyId, fromLead, toLead) =>
  DASHBOARD_DEMO_MODE
    ? simulate(mock.series(propertyId, fromLead, toLead))
    : live((dashboard) => selectSeries(dashboard, propertyId, fromLead, toLead));

export const getSegments = (propertyId) =>
  DASHBOARD_DEMO_MODE
    ? simulate(mock.segments(propertyId))
    : live((dashboard) => selectSegments(dashboard, propertyId));

export const getSegmentMix = () =>
  DASHBOARD_DEMO_MODE
    ? simulate(mock.segmentMixByProperty())
    : live(selectSegmentMix);

export const getChannels = () =>
  DASHBOARD_DEMO_MODE
    ? simulate(mock.channels())
    : live(selectChannels);

export const getNationalities = () =>
  DASHBOARD_DEMO_MODE
    ? simulate(mock.nationalities())
    : live(selectNationalities);

export const getPaceCurve = (propertyId) =>
  DASHBOARD_DEMO_MODE
    ? simulate(mock.paceCurve(propertyId))
    : live((dashboard) => selectPaceCurve(dashboard, propertyId));

export const getPickupCalendar = (propertyId) =>
  DASHBOARD_DEMO_MODE
    ? simulate(mock.pickupCalendar(propertyId))
    : live((dashboard) => selectPickupCalendar(dashboard, propertyId));

export const getAlerts = () =>
  DASHBOARD_DEMO_MODE
    ? simulate(mock.ALERTS)
    : live(selectAlerts);
