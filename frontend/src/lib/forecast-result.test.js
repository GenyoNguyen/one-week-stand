import { describe, expect, test } from 'vitest';

import fixture from './__fixtures__/hotel-dashboard.v1.json';
import {
  DashboardContractError,
  normalizeForecastResult,
  selectAlerts,
  selectChannels,
  selectNationalities,
  selectPaceCurve,
  selectPickupCalendar,
  selectSegmentMix,
  selectSegments,
  selectSeries
} from './forecast-result.js';

const clone = (value) => structuredClone(value);

describe('hotel-dashboard.v1 result contract', () => {
  test('validates and normalizes metadata and nullable capabilities', () => {
    const dashboard = normalizeForecastResult(fixture);

    expect(dashboard.schemaVersion).toBe('hotel-dashboard.v1');
    expect(dashboard.jobId).toBe('forecast_fixture1234');
    expect(dashboard.metadata.currency).toBe('VND');
    expect(dashboard.metadata.asOfBasis).toBe('forecast_job_submission_time');
    expect(dashboard.metadata.properties.map((property) => property.id)).toEqual(['ACR', 'AMN', 'ANT']);
    expect(dashboard.capabilities.forecast_intervals).toBe(false);
    expect(dashboard.daily[0].fcLo80).toBeNull();
  });

  test('builds the existing daily-series shape and rolls up properties', () => {
    const dashboard = normalizeForecastResult(fixture);
    const [portfolio] = selectSeries(dashboard, 'ALL', 1, 1);
    const [camRanh] = selectSeries(dashboard, 'ACR', 1, 1);

    expect(portfolio.capacity).toBe(496);
    expect(portfolio.roomsSold).toBe(280);
    expect(portfolio.occ).toBeCloseTo(280 / 496);
    expect(portfolio.fcOcc).toBeCloseTo(410 / 496);
    expect(portfolio.fcLo80).toBeNull();
    expect(portfolio.pu1).toBe(7);
    expect(camRanh.roomsSold).toBe(120);
    expect(camRanh.fcOcc).toBeCloseTo(180 / 213);
  });

  test('treats the as-of calendar date as current even when the run timestamp is earlier in the day', () => {
    const sameDay = clone(fixture);
    sameDay.dashboard_output.run_metadata.as_of = '2026-07-10T06:00:00+07:00';
    sameDay.dashboard_output.daily_forecast[0].room_nights = 160;
    sameDay.dashboard_output.daily_forecast[0].on_the_books_rooms = 99;

    const [camRanh] = selectSeries(normalizeForecastResult(sameDay), 'ACR', 0, 0);

    expect(camRanh.roomsSold).toBe(160);
  });

  test('normalizes all existing breakdown selector shapes', () => {
    const dashboard = normalizeForecastResult(fixture);
    const segments = selectSegments(dashboard, 'ALL');
    const mix = selectSegmentMix(dashboard);
    const channels = selectChannels(dashboard);
    const nationalities = selectNationalities(dashboard);
    const pace = selectPaceCurve(dashboard, 'ACR');
    const pickup = selectPickupCalendar(dashboard, 'ACR');

    expect(segments.find((row) => row.segment === 'Direct').roomNights).toBe(90);
    expect(mix.find((row) => row.property.id === 'ACR').mix).toEqual([
      expect.objectContaining({ segment: 'Direct', share: 0.6 }),
      expect.objectContaining({ segment: 'OTA', share: 0.4 })
    ]);
    expect(channels[0]).toEqual(expect.objectContaining({ channel: 'Brand.com', roomNights: 90 }));
    expect(nationalities.find((row) => row.name === 'Vietnam')).toEqual(
      expect.objectContaining({ roomNights: 80, share: 2 / 3 })
    );
    expect(pace.points).toEqual([
      { weeksOut: 1, ty: 100, ly: 105 },
      { weeksOut: 0, ty: 120, ly: 110 }
    ]);
    expect(pace).toEqual(expect.objectContaining({ isSnapshot: true, monthLabel: 'next 90 days' }));
    expect(pickup.map((row) => row.pu7)).toEqual([14, 11]);
  });

  test('treats backend *_pct fields as percentage points even below one percent', () => {
    const lowPercentages = clone(fixture);
    lowPercentages.dashboard_output.breakdowns.segments = [{
      property: 'ACR',
      segment: 'Direct',
      on_the_books_room_nights: 10,
      revenue: 1000,
      cancellation_rate_pct: 0.69,
      delta_last_year_pct: 0.61
    }];

    const [segment] = selectSegments(normalizeForecastResult(lowPercentages), 'ACR');

    expect(segment.cxlRate).toBeCloseTo(0.0069);
    expect(segment.deltaLy).toBeCloseTo(0.0061);
  });

  test('preserves unavailable capability metrics as null instead of invented zeros', () => {
    const limited = clone(fixture);
    Object.assign(limited.dashboard_output.capabilities, {
      point_forecast: false,
      pace_vs_stly: false,
      pickup: false
    });
    for (const row of limited.dashboard_output.daily_forecast) {
      delete row.expected_final_room_nights;
      delete row.expected_final_occupancy_pct;
      delete row.forecast_adr;
      delete row.forecast_revenue;
      delete row.pickup_room_nights;
      delete row.pickup_24h_room_nights;
      delete row.stly_otb_rooms;
    }

    const dashboard = normalizeForecastResult(limited);
    const [row] = selectSeries(dashboard, 'ACR', 1, 1);

    expect(row).toEqual(expect.objectContaining({ fcOcc: null, pu7: null, pu1: null, stlyOtbRooms: null }));
    expect(selectPaceCurve(dashboard, 'ACR').points).toEqual([]);
    expect(selectPickupCalendar(dashboard, 'ACR')).toEqual([]);
  });

  test('uses on-the-books room nights before generic room_nights in forward breakdowns', () => {
    const withBoth = clone(fixture);
    withBoth.dashboard_output.breakdowns.segments[0].on_the_books_room_nights = 6;

    const direct = selectSegments(normalizeForecastResult(withBoth), 'ACR')
      .find((row) => row.segment === 'Direct');

    expect(direct.roomNights).toBe(6);
  });

  test('joins risks to actions without stringifying structured impact', () => {
    const [alert] = selectAlerts(normalizeForecastResult(fixture));

    expect(alert.severity).toBe('risk');
    expect(alert.body).toContain('7.4% below budget');
    expect(alert.action).toContain('Review rate');
    expect(alert.impact).toBe('Up to VND 69,000,000');
    expect(alert.impact).not.toContain('[object Object]');
    expect(alert.impactValue).toBe(69000000);
  });

  test('rejects unsupported versions and malformed live numbers', () => {
    const wrongVersion = clone(fixture);
    wrongVersion.dashboard_output.schema_version = 'hotel-dashboard.v2';
    expect(() => normalizeForecastResult(wrongVersion)).toThrow(DashboardContractError);
    expect(() => normalizeForecastResult(wrongVersion)).toThrow('Unsupported dashboard schema');

    const malformed = clone(fixture);
    malformed.dashboard_output.daily_forecast[0].rooms_available = 'not-a-number';
    expect(() => normalizeForecastResult(malformed)).toThrow('rooms_available must be a finite number');
  });

  test('does not treat an unavailable completed result as zero-valued live data', () => {
    const unavailable = clone(fixture);
    unavailable.dashboard_output.available = false;
    unavailable.dashboard_output.daily_forecast = [];
    unavailable.dashboard_output.unavailable_reason = 'No recognized performance feed.';

    expect(() => normalizeForecastResult(unavailable)).toThrow('No recognized performance feed.');
  });
});
