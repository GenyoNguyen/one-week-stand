import { afterEach, beforeEach, describe, expect, test } from 'vitest';
import { get } from 'svelte/store';

import fixture from './__fixtures__/hotel-dashboard.v1.json';
import {
  ACTIVE_DASHBOARD_STORAGE_KEY,
  activeDashboard,
  loadActiveDashboard,
  resetDashboardState,
  setActiveForecast
} from './dashboard-store.js';
import { getDisplayCurrency } from './formatters.js';
import { alertStatus, focusAlert } from './stores.js';

const originalFetch = globalThis.fetch;
const originalLocalStorage = globalThis.localStorage;

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
    clear: () => values.clear()
  };
}

beforeEach(() => {
  globalThis.localStorage = memoryStorage();
  resetDashboardState();
});

afterEach(() => {
  globalThis.fetch = originalFetch;
  globalThis.localStorage = originalLocalStorage;
});

describe('active dashboard result store', () => {
  test('persists an explicitly selected completed job and loads its dashboard', async () => {
    globalThis.fetch = async (url) => {
      expect(url).toBe('/api/forecast/forecast_fixture1234/result');
      return Response.json({ success: true, data: fixture }, { status: 200 });
    };

    await setActiveForecast('forecast_fixture1234');
    const dashboard = await loadActiveDashboard();

    expect(localStorage.getItem(ACTIVE_DASHBOARD_STORAGE_KEY)).toBe('forecast_fixture1234');
    expect(get(activeDashboard).status).toBe('ready');
    expect(dashboard.metadata.currency).toBe('VND');
    expect(getDisplayCurrency()).toBe('VND');
  });

  test('keeps malformed live data as an explicit store error', async () => {
    globalThis.fetch = async () => Response.json({
      success: true,
      data: { job: fixture.job, dashboard_output: { schema_version: 'hotel-dashboard.v2' } }
    });
    await setActiveForecast('forecast_fixture1234');

    await expect(loadActiveDashboard()).rejects.toThrow('Unsupported dashboard schema');
    expect(get(activeDashboard).status).toBe('error');
    expect(get(activeDashboard).dashboard).toBeNull();
  });

  test('clears alert decisions when a different forecast job is selected', async () => {
    await setActiveForecast('forecast_fixture1234');
    alertStatus.set({ 'pace-gap:ACR:2026-07-13': 'accepted' });
    focusAlert.set('pace-gap:ACR:2026-07-13');

    await setActiveForecast('forecast_second1234');

    expect(get(alertStatus)).toEqual({});
    expect(get(focusAlert)).toBeNull();
  });
});
