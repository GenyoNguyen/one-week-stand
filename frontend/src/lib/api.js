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
