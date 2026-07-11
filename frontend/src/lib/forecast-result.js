import { CHANNELS, PROPERTIES, SEGMENTS } from './constants.js';

export const DASHBOARD_SCHEMA_VERSION = 'hotel-dashboard.v1';

const DAY_MS = 24 * 60 * 60 * 1000;
const PROPERTY_BY_ID = new Map(PROPERTIES.map((property) => [property.id, property]));

export class DashboardContractError extends Error {
  constructor(message, code = 'invalid_contract') {
    super(message);
    this.name = 'DashboardContractError';
    this.code = code;
  }
}

const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const first = (object, keys, fallback = null) => {
  for (const key of keys) if (object?.[key] !== undefined && object[key] !== null) return object[key];
  return fallback;
};

function requireObject(value, path) {
  if (!isObject(value)) throw new DashboardContractError(`${path} must be an object.`);
  return value;
}

function requireArray(value, path) {
  if (!Array.isArray(value)) throw new DashboardContractError(`${path} must be an array.`);
  return value;
}

function optionalNumber(value, path) {
  if (value === null || value === undefined || value === '') return null;
  const number = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(number)) throw new DashboardContractError(`${path} must be a finite number or null.`);
  return number;
}

function requiredNumber(value, path) {
  const number = optionalNumber(value, path);
  if (number === null) throw new DashboardContractError(`${path} is required.`);
  return number;
}

function percentagePoints(value, path) {
  const number = optionalNumber(value, path);
  return number === null ? null : number / 100;
}

function unitRatio(value, path) {
  return optionalNumber(value, path);
}

function ratioField(raw, percentageKeys, ratioKeys, path) {
  for (const key of percentageKeys) {
    if (raw?.[key] !== undefined && raw[key] !== null) {
      return percentagePoints(raw[key], `${path}.${key}`);
    }
  }
  for (const key of ratioKeys) {
    if (raw?.[key] !== undefined && raw[key] !== null) {
      return unitRatio(raw[key], `${path}.${key}`);
    }
  }
  return null;
}

function dateOnly(value, path) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate(), 12);
  }
  const match = String(value ?? '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) throw new DashboardContractError(`${path} must be an ISO date.`);
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12);
  if (
    date.getFullYear() !== Number(match[1]) ||
    date.getMonth() !== Number(match[2]) - 1 ||
    date.getDate() !== Number(match[3])
  ) {
    throw new DashboardContractError(`${path} is not a valid calendar date.`);
  }
  return date;
}

function instant(value, path) {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return value;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) throw new DashboardContractError(`${path} must be an ISO date or timestamp.`);
  return date;
}

function propertyId(value, path) {
  const id = String(value ?? '').trim().toUpperCase();
  if (!id) throw new DashboardContractError(`${path} is required.`);
  const aliases = {
    'THE ANAM CAM RANH': 'ACR',
    'CAM RANH': 'ACR',
    'THE ANAM MUI NE': 'AMN',
    'MUI NE': 'AMN',
    'THE ANAM NHA TRANG': 'ANT',
    'NHA TRANG': 'ANT'
  };
  return aliases[id] || id;
}

function normalizeProperty(raw, index, dailyRows) {
  if (typeof raw === 'string') raw = { id: raw };
  requireObject(raw, `dashboard_output.run_metadata.properties[${index}]`);
  const id = propertyId(first(raw, ['id', 'property', 'property_id', 'code']), `properties[${index}].id`);
  const known = PROPERTY_BY_ID.get(id);
  const capacity = optionalNumber(
    first(raw, ['rooms', 'room_count', 'rooms_available', 'capacity']),
    `properties[${index}].room_count`
  );
  const rowCapacity = dailyRows.find((row) => propertyId(row.property, 'daily_forecast.property') === id)?.rooms_available;
  return {
    id,
    name: String(first(raw, ['name', 'property_name'], known?.name || id)),
    short: String(first(raw, ['short', 'short_name', 'city'], known?.short || id)),
    rooms: capacity ?? optionalNumber(rowCapacity, `daily_forecast.${id}.rooms_available`) ?? known?.rooms ?? 0,
    color: known?.color
  };
}

function normalizeDailyRow(raw, index, asOfDay) {
  const path = `dashboard_output.daily_forecast[${index}]`;
  requireObject(raw, path);
  const date = dateOnly(first(raw, ['date', 'stay_date']), `${path}.date`);
  const property = propertyId(first(raw, ['property', 'property_id']), `${path}.property`);
  const capacity = requiredNumber(first(raw, ['rooms_available', 'capacity', 'available_rooms']), `${path}.rooms_available`);
  if (capacity <= 0) throw new DashboardContractError(`${path}.rooms_available must be greater than zero.`);

  const actualRooms = optionalNumber(first(raw, ['room_nights', 'rooms_sold', 'actual_room_nights']), `${path}.room_nights`);
  const onBooks = optionalNumber(
    first(raw, ['on_the_books_rooms', 'on_the_books_room_nights', 'otb_rooms']),
    `${path}.on_the_books_rooms`
  );
  if (actualRooms === null && onBooks === null) {
    throw new DashboardContractError(`${path} needs room_nights or on_the_books_rooms.`);
  }

  const isPastOrCurrent = date.getTime() <= asOfDay.getTime();
  const roomsSold = Math.max(0, isPastOrCurrent ? (actualRooms ?? onBooks) : (onBooks ?? actualRooms));
  const sourceOcc = ratioField(raw, ['occupancy_pct'], ['occupancy'], path);
  const occ = isPastOrCurrent && sourceOcc !== null ? sourceOcc : roomsSold / capacity;
  const adr = optionalNumber(first(raw, ['adr', 'adr_vnd', 'current_adr']), `${path}.adr`);
  const sourceRevenue = optionalNumber(first(raw, ['revenue', 'room_revenue', 'revenue_vnd']), `${path}.revenue`);

  const forecastRooms = optionalNumber(
    first(raw, ['expected_final_room_nights', 'expected_final_rooms', 'forecast_room_nights']),
    `${path}.expected_final_room_nights`
  );
  const forecastOcc = ratioField(
    raw,
    ['expected_final_occupancy_pct', 'forecast_occupancy_pct'],
    ['forecast_occupancy'],
    path
  ) ?? (forecastRooms === null ? null : forecastRooms / capacity);
  const forecastAdr = optionalNumber(first(raw, ['forecast_adr', 'expected_final_adr']), `${path}.forecast_adr`);
  const forecastRevenue = optionalNumber(first(raw, ['forecast_revenue', 'expected_final_revenue']), `${path}.forecast_revenue`);

  const budgetRooms = optionalNumber(first(raw, ['budget_room_nights', 'budget_rooms']), `${path}.budget_room_nights`);
  const budgetOcc = ratioField(raw, ['budget_occupancy_pct'], ['budget_occupancy'], path)
    ?? (budgetRooms === null ? null : budgetRooms / capacity);
  const budgetAdr = optionalNumber(first(raw, ['budget_adr', 'budget_adr_vnd']), `${path}.budget_adr`);
  const budgetRevenue = optionalNumber(first(raw, ['budget_revenue', 'budget_revenue_vnd']), `${path}.budget_revenue`)
    ?? (budgetRooms !== null && budgetAdr !== null ? budgetRooms * budgetAdr : null);

  const lyRooms = optionalNumber(first(raw, ['last_year_room_nights', 'ly_room_nights', 'last_year_rooms']), `${path}.last_year_room_nights`);
  const lyOcc = ratioField(raw, ['last_year_occupancy_pct', 'ly_occupancy_pct'], ['ly_occupancy'], path)
    ?? (lyRooms === null ? null : lyRooms / capacity);
  const lyAdr = optionalNumber(first(raw, ['last_year_adr', 'ly_adr', 'ly_adr_vnd']), `${path}.last_year_adr`);
  const lyRevenue = optionalNumber(first(raw, ['last_year_revenue', 'ly_revenue']), `${path}.last_year_revenue`)
    ?? (lyRooms !== null && lyAdr !== null ? lyRooms * lyAdr : null);

  const band = (names, suffix) => ratioField(raw, names, [], `${path}.${suffix}`);
  return {
    property,
    date,
    capacity,
    roomsSold,
    actualRooms,
    onBooks,
    occ,
    adr,
    revenue: isPastOrCurrent ? sourceRevenue ?? (adr === null ? null : roomsSold * adr) : adr === null ? sourceRevenue : roomsSold * adr,
    revpar: optionalNumber(first(raw, ['revpar', 'revpar_vnd']), `${path}.revpar`) ?? (adr === null ? null : occ * adr),
    budgetRooms,
    budgetOcc,
    budgetAdr,
    budgetRevenue,
    lyRooms,
    lyOcc,
    lyAdr,
    lyRevenue,
    fcRooms: forecastRooms,
    fcOcc: forecastOcc,
    fcAdr: forecastAdr,
    fcRevenue: forecastRevenue ?? (forecastRooms !== null && forecastAdr !== null ? forecastRooms * forecastAdr : null),
    fcLo80: band(['forecast_lo80_occupancy_pct', 'forecast_occupancy_lo_80', 'forecast_lo_80_pct', 'interval_80_low_pct'], 'forecast_lo80_occupancy_pct'),
    fcHi80: band(['forecast_hi80_occupancy_pct', 'forecast_occupancy_hi_80', 'forecast_hi_80_pct', 'interval_80_high_pct'], 'forecast_hi80_occupancy_pct'),
    fcLo50: band(['forecast_lo50_occupancy_pct', 'forecast_occupancy_lo_50', 'forecast_lo_50_pct', 'interval_50_low_pct'], 'forecast_lo50_occupancy_pct'),
    fcHi50: band(['forecast_hi50_occupancy_pct', 'forecast_occupancy_hi_50', 'forecast_hi_50_pct', 'interval_50_high_pct'], 'forecast_hi50_occupancy_pct'),
    pu7: optionalNumber(first(raw, ['pickup_7d_room_nights', 'pickup_room_nights', 'pickup_7d_rooms', 'net_pickup_7d']), `${path}.pickup_room_nights`),
    pu1: optionalNumber(first(raw, ['pickup_24h_room_nights', 'pickup_1d_rooms', 'net_pickup_24h']), `${path}.pickup_24h_room_nights`),
    cxl7: optionalNumber(first(raw, ['cancellations_7d', 'cancelled_room_nights_7d', 'cancellations']), `${path}.cancellations`),
    stlyOtbRooms: optionalNumber(first(raw, ['stly_otb_room_nights', 'stly_otb_rooms']), `${path}.stly_otb_room_nights`)
  };
}

function normalizedMetadata(output, rawDaily) {
  const run = requireObject(output.run_metadata, 'dashboard_output.run_metadata');
  const status = requireObject(output.data_status, 'dashboard_output.data_status');
  const asOfValue = first(run, ['as_of', 'as_of_time', 'data_as_of']) ?? first(status, ['as_of', 'as_of_time', 'data_as_of']);
  if (!asOfValue) throw new DashboardContractError('dashboard_output.run_metadata.as_of is required.');
  const asOf = instant(asOfValue, 'dashboard_output.run_metadata.as_of');
  const asOfDay = dateOnly(asOfValue, 'dashboard_output.run_metadata.as_of');
  const currency = String(first(run, ['currency'], first(status, ['currency'], ''))).trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(currency)) {
    throw new DashboardContractError('dashboard_output.run_metadata.currency must be a three-letter ISO code.');
  }
  const sourceFiles = first(run, ['source_files', 'sources'], []);
  if (!Array.isArray(sourceFiles)) throw new DashboardContractError('dashboard_output.run_metadata.source_files must be an array.');
  const propertiesRaw = first(run, ['properties'], []);
  if (!Array.isArray(propertiesRaw)) throw new DashboardContractError('dashboard_output.run_metadata.properties must be an array.');
  const fallbackProperties = [...new Set(rawDaily.map((row) => row.property))];
  const properties = (propertiesRaw.length ? propertiesRaw : fallbackProperties).map((raw, index) =>
    normalizeProperty(raw, index, rawDaily)
  );
  return {
    asOf,
    asOfDay,
    asOfBasis: String(first(run, ['as_of_basis'], 'unspecified')),
    currency,
    timezone: String(first(run, ['timezone'], 'Asia/Ho_Chi_Minh')),
    sourceFiles: sourceFiles.map((source) => (typeof source === 'string' ? source : String(first(source, ['name', 'filename'], 'Source')))),
    sourceLabel: String(first(run, ['source_label'], sourceFiles.length ? sourceFiles.join(', ') : 'Forecast input data')),
    generatedAt: first(run, ['generated_at', 'completed_at']) ? instant(first(run, ['generated_at', 'completed_at']), 'run_metadata.generated_at') : null,
    properties,
    freshness: first(status, ['freshness', 'freshness_status'], null),
    acceptedRows: optionalNumber(first(status, ['accepted_rows', 'rows_accepted']), 'data_status.accepted_rows'),
    rejectedRows: optionalNumber(first(status, ['rejected_rows', 'rows_rejected']), 'data_status.rejected_rows'),
    missingFeeds: Array.isArray(first(status, ['missing_feeds'], [])) ? first(status, ['missing_feeds'], []) : []
  };
}

/** Validate a completed forecast result and normalize it for dashboard selectors. */
export function normalizeForecastResult(result) {
  requireObject(result, 'forecast result');
  const output = result.dashboard_output ?? result.data?.dashboard_output ?? (result.schema_version ? result : null);
  requireObject(output, 'forecast result.dashboard_output');
  if (output.schema_version !== DASHBOARD_SCHEMA_VERSION) {
    throw new DashboardContractError(
      `Unsupported dashboard schema ${JSON.stringify(output.schema_version)}; expected ${DASHBOARD_SCHEMA_VERSION}.`,
      'unsupported_schema'
    );
  }
  if (typeof output.available !== 'boolean') {
    throw new DashboardContractError('dashboard_output.available must be a boolean.');
  }
  if (!output.available) {
    throw new DashboardContractError(
      String(output.unavailable_reason || output.reason || 'This forecast did not produce dashboard data.'),
      'dashboard_unavailable'
    );
  }

  const rawDaily = requireArray(output.daily_forecast, 'dashboard_output.daily_forecast');
  if (!rawDaily.length) throw new DashboardContractError('dashboard_output.daily_forecast cannot be empty when available is true.');
  const metadata = normalizedMetadata(output, rawDaily);
  const normalizedDaily = rawDaily.map((row, index) => normalizeDailyRow(row, index, metadata.asOfDay));
  const breakdowns = requireObject(output.breakdowns, 'dashboard_output.breakdowns');
  const risks = requireArray(output.risks, 'dashboard_output.risks');
  const actions = requireArray(output.actions, 'dashboard_output.actions');
  const modelChecks = requireObject(output.model_checks, 'dashboard_output.model_checks');
  const capabilities = requireObject(output.capabilities, 'dashboard_output.capabilities');
  const daily = normalizedDaily.map((row) => ({
    ...row,
    ...(capabilities.point_forecast === false
      ? { fcRooms: null, fcOcc: null, fcAdr: null, fcRevenue: null }
      : {}),
    ...(capabilities.forecast_intervals === false
      ? { fcLo80: null, fcHi80: null, fcLo50: null, fcHi50: null }
      : {}),
    ...(capabilities.pickup === false ? { pu7: null, pu1: null } : {}),
    ...(capabilities.cancellations === false ? { cxl7: null } : {}),
    ...(capabilities.pace_vs_stly === false ? { stlyOtbRooms: null } : {})
  }));

  return {
    schemaVersion: output.schema_version,
    available: true,
    jobId: result.job?.job_id ?? result.data?.job?.job_id ?? null,
    metadata,
    daily,
    breakdowns,
    risks,
    actions,
    modelChecks,
    capabilities,
    raw: output
  };
}

function groupBy(items, key) {
  const groups = new Map();
  for (const item of items) {
    const value = key(item);
    groups.set(value, [...(groups.get(value) || []), item]);
  }
  return groups;
}

const finiteSum = (rows, key) => rows.reduce((sum, row) => sum + (Number.isFinite(row[key]) ? row[key] : 0), 0);
const allFinite = (rows, key) => rows.length > 0 && rows.every((row) => Number.isFinite(row[key]));
const weighted = (rows, valueKey, weightKey) => {
  const usable = rows.filter((row) => Number.isFinite(row[valueKey]) && Number.isFinite(row[weightKey]) && row[weightKey] > 0);
  const denominator = finiteSum(usable, weightKey);
  return denominator ? usable.reduce((sum, row) => sum + row[valueKey] * row[weightKey], 0) / denominator : null;
};

function rollupDaily(rows) {
  const capacity = finiteSum(rows, 'capacity');
  const roomsSold = finiteSum(rows, 'roomsSold');
  const revenue = allFinite(rows, 'revenue') ? finiteSum(rows, 'revenue') : null;
  const forecastRooms = allFinite(rows, 'fcRooms') ? finiteSum(rows, 'fcRooms') : null;
  const budgetRooms = allFinite(rows, 'budgetRooms') ? finiteSum(rows, 'budgetRooms') : null;
  const lyRooms = allFinite(rows, 'lyRooms') ? finiteSum(rows, 'lyRooms') : null;
  const budgetRevenue = allFinite(rows, 'budgetRevenue') ? finiteSum(rows, 'budgetRevenue') : null;
  const lyRevenue = allFinite(rows, 'lyRevenue') ? finiteSum(rows, 'lyRevenue') : null;
  return {
    capacity,
    roomsSold,
    revenue,
    occ: capacity ? roomsSold / capacity : null,
    adr: roomsSold && revenue !== null ? revenue / roomsSold : weighted(rows, 'adr', 'capacity'),
    revpar: capacity && revenue !== null ? revenue / capacity : null,
    budgetOcc: capacity && budgetRooms !== null ? budgetRooms / capacity : weighted(rows, 'budgetOcc', 'capacity'),
    budgetAdr: budgetRooms ? budgetRevenue / budgetRooms : weighted(rows, 'budgetAdr', 'budgetRooms'),
    lyOcc: capacity && lyRooms !== null ? lyRooms / capacity : weighted(rows, 'lyOcc', 'capacity'),
    lyAdr: lyRooms ? lyRevenue / lyRooms : weighted(rows, 'lyAdr', 'lyRooms'),
    fcOcc: capacity && forecastRooms !== null ? forecastRooms / capacity : weighted(rows, 'fcOcc', 'capacity'),
    fcLo80: allFinite(rows, 'fcLo80') ? weighted(rows, 'fcLo80', 'capacity') : null,
    fcHi80: allFinite(rows, 'fcHi80') ? weighted(rows, 'fcHi80', 'capacity') : null,
    fcLo50: allFinite(rows, 'fcLo50') ? weighted(rows, 'fcLo50', 'capacity') : null,
    fcHi50: allFinite(rows, 'fcHi50') ? weighted(rows, 'fcHi50', 'capacity') : null,
    pu7: allFinite(rows, 'pu7') ? finiteSum(rows, 'pu7') : null,
    pu1: allFinite(rows, 'pu1') ? finiteSum(rows, 'pu1') : null,
    cxl7: allFinite(rows, 'cxl7') ? finiteSum(rows, 'cxl7') : null,
    stlyOtbRooms: allFinite(rows, 'stlyOtbRooms') ? finiteSum(rows, 'stlyOtbRooms') : null
  };
}

export function selectSeries(dashboard, selectedProperty, fromLead, toLead) {
  const asOfDay = dashboard.metadata.asOfDay;
  const scoped = dashboard.daily.filter(
    (row) => selectedProperty === 'ALL' || row.property === selectedProperty
  );
  const byDate = groupBy(scoped, (row) => row.date.getTime());
  const output = [];
  for (const [timestamp, rows] of byDate) {
    const date = new Date(Number(timestamp));
    const lead = Math.round((date.getTime() - asOfDay.getTime()) / DAY_MS);
    if (lead >= fromLead && lead <= toLead) output.push({ date, lead, ...rollupDaily(rows) });
  }
  return output.sort((a, b) => a.date - b.date);
}

function breakdownArray(dashboard, key) {
  const value = dashboard.breakdowns[key];
  if (value === null || value === undefined) return [];
  if (!Array.isArray(value)) throw new DashboardContractError(`dashboard_output.breakdowns.${key} must be an array.`);
  return value;
}

function normalizedBreakdownRow(raw, index, type) {
  requireObject(raw, `breakdowns.${type}[${index}]`);
  const nameKey = type === 'segments' ? ['segment', 'market_segment', 'name'] : ['channel', 'source', 'name'];
  const name = String(first(raw, nameKey, '')).trim();
  if (!name) throw new DashboardContractError(`breakdowns.${type}[${index}] is missing its name.`);
  const property = first(raw, ['property', 'property_id'], 'ALL');
  return {
    property: property === 'ALL' ? 'ALL' : propertyId(property, `breakdowns.${type}[${index}].property`),
    name,
    roomNights: optionalNumber(first(raw, ['on_the_books_room_nights', 'room_nights', 'rooms']), `${type}[${index}].on_the_books_room_nights`) ?? 0,
    revenue: optionalNumber(first(raw, ['revenue', 'revenue_vnd']), `${type}[${index}].revenue`),
    adr: optionalNumber(first(raw, ['adr', 'adr_vnd']), `${type}[${index}].adr`),
    cxlRate: ratioField(raw, ['cancellation_rate_pct'], ['cancellation_rate', 'cxl_rate'], `${type}[${index}]`),
    cxlPrev: ratioField(raw, ['previous_cancellation_rate_pct'], ['previous_cancellation_rate', 'cancellation_rate_previous', 'cxl_prev'], `${type}[${index}]`),
    deltaLy: ratioField(raw, ['delta_last_year_pct', 'room_nights_change_vs_last_year_pct'], ['delta_vs_last_year', 'delta_ly'], `${type}[${index}]`),
    lastYearRoomNights: optionalNumber(first(raw, ['last_year_room_nights', 'ly_room_nights']), `${type}[${index}].last_year_room_nights`)
  };
}

function aggregateBreakdown(rows) {
  return [...groupBy(rows, (row) => row.name).entries()].map(([name, values]) => {
    const roomNights = finiteSum(values, 'roomNights');
    const revenueKnown = values.every((row) => Number.isFinite(row.revenue));
    const revenue = revenueKnown ? finiteSum(values, 'revenue') : null;
    const lastYearKnown = values.every((row) => Number.isFinite(row.lastYearRoomNights));
    const lastYear = lastYearKnown ? finiteSum(values, 'lastYearRoomNights') : null;
    return {
      name,
      roomNights,
      revenue,
      adr: roomNights && revenue !== null ? revenue / roomNights : weighted(values, 'adr', 'roomNights'),
      cxlRate: weighted(values, 'cxlRate', 'roomNights'),
      cxlPrev: weighted(values, 'cxlPrev', 'roomNights'),
      deltaLy: lastYear ? (roomNights - lastYear) / lastYear : weighted(values, 'deltaLy', 'roomNights')
    };
  });
}

export function selectSegments(dashboard, selectedProperty = 'ALL') {
  const source = breakdownArray(dashboard, 'segments').map((row, index) => normalizedBreakdownRow(row, index, 'segments'));
  const exact = source.filter((row) => row.property === selectedProperty);
  const rows = exact.length ? exact : source.filter((row) => row.property !== 'ALL' && (selectedProperty === 'ALL' || row.property === selectedProperty));
  return aggregateBreakdown(rows)
    .map((row) => ({ segment: row.name, ...row }))
    .sort((a, b) => {
      const left = SEGMENTS.indexOf(a.segment);
      const right = SEGMENTS.indexOf(b.segment);
      return (left < 0 ? Number.MAX_SAFE_INTEGER : left) - (right < 0 ? Number.MAX_SAFE_INTEGER : right);
    });
}

export function selectSegmentMix(dashboard) {
  const source = breakdownArray(dashboard, 'segments').map((row, index) => normalizedBreakdownRow(row, index, 'segments'));
  return dashboard.metadata.properties.map((property) => {
    const rows = source.filter((row) => row.property === property.id);
    const total = finiteSum(rows, 'roomNights');
    return {
      property: { ...property, color: property.color || PROPERTY_BY_ID.get(property.id)?.color },
      mix: rows
        .map((row) => ({ segment: row.name, share: total ? row.roomNights / total : 0 }))
        .sort((a, b) => SEGMENTS.indexOf(a.segment) - SEGMENTS.indexOf(b.segment))
    };
  }).filter((row) => row.mix.length);
}

export function selectChannels(dashboard) {
  const source = breakdownArray(dashboard, 'channels').map((row, index) => normalizedBreakdownRow(row, index, 'channels'));
  const exact = source.filter((row) => row.property === 'ALL');
  return aggregateBreakdown(exact.length ? exact : source.filter((row) => row.property !== 'ALL'))
    .map((row) => ({ channel: row.name, ...row }))
    .sort((a, b) => {
      const left = CHANNELS.indexOf(a.channel);
      const right = CHANNELS.indexOf(b.channel);
      return (left < 0 ? Number.MAX_SAFE_INTEGER : left) - (right < 0 ? Number.MAX_SAFE_INTEGER : right);
    });
}

export function selectNationalities(dashboard) {
  const source = breakdownArray(dashboard, 'nationalities');
  const rows = source.map((raw, index) => {
    requireObject(raw, `breakdowns.nationalities[${index}]`);
    const name = String(first(raw, ['name', 'nationality', 'guest_nationality'], '')).trim();
    if (!name) throw new DashboardContractError(`breakdowns.nationalities[${index}] is missing its name.`);
    return {
      name,
      share: ratioField(raw, ['share_pct'], ['share'], `nationalities[${index}]`),
      roomNights: optionalNumber(first(raw, ['room_nights', 'rooms']), `nationalities[${index}].room_nights`),
      lastYearRoomNights: optionalNumber(first(raw, ['last_year_room_nights', 'ly_room_nights']), `nationalities[${index}].last_year_room_nights`),
      deltaLy: ratioField(raw, ['delta_last_year_pct', 'change_vs_last_year_pct'], ['delta_vs_last_year', 'delta_ly'], `nationalities[${index}]`) ?? 0
    };
  });
  const grouped = [...groupBy(rows, (row) => row.name).entries()].map(([name, values]) => {
    const roomNights = finiteSum(values, 'roomNights');
    const lastYear = values.every((row) => Number.isFinite(row.lastYearRoomNights))
      ? finiteSum(values, 'lastYearRoomNights')
      : null;
    return {
      name,
      roomNights,
      deltaLy: lastYear ? (roomNights - lastYear) / lastYear : weighted(values, 'deltaLy', 'roomNights') ?? 0
    };
  });
  const total = finiteSum(grouped, 'roomNights');
  return grouped.map((row) => ({ ...row, share: total ? row.roomNights / total : 0 }));
}

export function selectPaceCurve(dashboard, selectedProperty) {
  if (!dashboard.capabilities?.pace_vs_stly) {
    return { points: [], currentWeeksOut: 0, monthLabel: 'next 90 days', isSnapshot: true };
  }
  const source = breakdownArray(dashboard, 'pace');
  const rows = source.filter((row) => first(row, ['property', 'property_id'], selectedProperty) === selectedProperty);
  const isSnapshot = rows.some((row) => first(row, ['date', 'stay_date'], null) !== null)
    && rows.every((row) => first(row, ['weeks_out', 'lead_weeks'], null) === null);
  const pointRows = rows.map((raw, index) => {
    const explicitWeeks = optionalNumber(first(raw, ['weeks_out', 'lead_weeks']), `pace[${index}].weeks_out`);
    const stayDate = first(raw, ['date', 'stay_date'], null);
    const weeksOut = explicitWeeks ?? Math.max(0, Math.round(
      (dateOnly(stayDate, `pace[${index}].date`).getTime() - dashboard.metadata.asOfDay.getTime()) / DAY_MS / 7
    ));
    return {
      weeksOut,
      ty: optionalNumber(first(raw, ['on_the_books_rooms', 'this_year_room_nights', 'current_room_nights', 'ty']), `pace[${index}].on_the_books_rooms`),
      ly: optionalNumber(first(raw, ['stly_otb_rooms', 'last_year_room_nights', 'ly']), `pace[${index}].stly_otb_rooms`),
      date: stayDate ? dateOnly(stayDate, `pace[${index}].date`) : null
    };
  });
  const points = [...groupBy(pointRows, (row) => row.weeksOut).entries()]
    .map(([weeksOut, values]) => ({
      weeksOut: Number(weeksOut),
      ty: values.every((row) => row.ty === null) ? null : finiteSum(values, 'ty'),
      ly: allFinite(values, 'ly') ? finiteSum(values, 'ly') : null
    }))
    .filter((point) => Number.isFinite(point.ty) && Number.isFinite(point.ly))
    .sort((a, b) => b.weeksOut - a.weeksOut);
  const currentWeeksOut = optionalNumber(first(rows[0], ['current_weeks_out'], null), 'pace.current_weeks_out') ?? 0;
  const monthLabel = isSnapshot ? 'next 90 days' : 'forward arrivals';
  return {
    points,
    currentWeeksOut,
    monthLabel: String(first(rows[0], ['month_label', 'arrival_month'], monthLabel)),
    isSnapshot
  };
}

export function selectPickupCalendar(dashboard, selectedProperty) {
  if (!dashboard.capabilities?.pickup) return [];
  const source = breakdownArray(dashboard, 'pickup');
  if (source.length) {
    return source
      .filter((row) => first(row, ['property', 'property_id'], selectedProperty) === selectedProperty)
      .map((raw, index) => ({
        date: dateOnly(first(raw, ['date', 'stay_date']), `pickup[${index}].date`),
        pu7: optionalNumber(first(raw, ['pickup_7d_room_nights', 'pickup_room_nights', 'pickup_7d_rooms']), `pickup[${index}].pickup_room_nights`)
      }))
      .filter((row) => Number.isFinite(row.pu7))
      .sort((a, b) => a.date - b.date)
      .slice(0, 56);
  }
  return selectSeries(dashboard, selectedProperty, 1, 56)
    .filter((row) => Number.isFinite(row.pu7))
    .map((row) => ({ date: row.date, pu7: row.pu7 }));
}

function evidenceValues(risk) {
  const values = first(risk, ['evidence_values', 'evidence_series'], null);
  if (Array.isArray(values)) return values.map(Number).filter(Number.isFinite);
  const evidence = risk.evidence;
  if (Array.isArray(evidence)) {
    const numeric = evidence.map((item) => (typeof item === 'number' ? item : Number(first(item, ['value'], NaN)))).filter(Number.isFinite);
    if (numeric.length) return numeric;
  }
  if (isObject(evidence)) {
    return Object.values(evidence).map(Number).filter(Number.isFinite);
  }
  return [];
}

function actionImpact(value, currency) {
  if (value === null || value === undefined) return 'Impact not quantified';
  if (!isObject(value)) return String(value);
  const minimum = optionalNumber(value.minimum, 'action.impact.minimum');
  const maximum = optionalNumber(value.maximum, 'action.impact.maximum');
  const unit = String(value.currency || currency || '').trim();
  if (minimum !== null && maximum !== null) return `${unit} ${minimum.toLocaleString()}–${maximum.toLocaleString()}`.trim();
  if (maximum !== null) return `Up to ${unit} ${maximum.toLocaleString()}`.trim();
  if (minimum !== null) return `At least ${unit} ${minimum.toLocaleString()}`.trim();
  return 'Impact not quantified';
}

export function selectAlerts(dashboard) {
  const actionsByRisk = new Map();
  for (const [index, action] of dashboard.actions.entries()) {
    requireObject(action, `actions[${index}]`);
    const riskId = String(first(action, ['risk_id', 'related_risk_id', 'alert_id'], ''));
    if (riskId) actionsByRisk.set(riskId, action);
  }
  return dashboard.risks.map((risk, index) => {
    requireObject(risk, `risks[${index}]`);
    const id = String(first(risk, ['id', 'risk_id'], `risk-${index + 1}`));
    const action = actionsByRisk.get(id) || dashboard.actions[index] || {};
    const type = String(first(risk, ['severity', 'kind', 'level', 'type', 'category'], 'watch')).toLowerCase();
    const severity = ['opportunity', 'upside'].includes(type)
      ? 'opportunity'
      : ['risk', 'high', 'critical'].includes(type)
        ? 'risk'
        : 'watch';
    const property = first(risk, ['property', 'property_id'], 'ALL');
    const evidence = evidenceValues(risk);
    return {
      id,
      severity,
      property: property === 'ALL' ? 'ALL' : propertyId(property, `risks[${index}].property`),
      title: String(first(risk, ['title', 'headline', 'trigger'], 'Forecast item needs review')),
      body: String(first(risk, ['body', 'summary', 'description', 'reason', 'rationale'], 'Review the supporting forecast evidence.')),
      evidence: evidence.length ? evidence : [0, 0],
      evidenceLabel: String(first(risk, ['evidence_label', 'evidence_window'], 'Evidence supplied by forecast run')),
      action: String(first(action, ['recommendation', 'action', 'description'], first(risk, ['recommendation'], 'Review and decide the next commercial step.'))),
      impact: actionImpact(first(action, ['impact', 'impact_range', 'expected_impact'], first(risk, ['impact'], null)), dashboard.metadata.currency),
      impactValue: isObject(action.impact)
        ? optionalNumber(first(action.impact, ['maximum', 'minimum']), `actions[${index}].impact`)
        : null,
      owner: String(first(action, ['owner'], 'Commercial')),
      deadline: first(action, ['deadline', 'due_at'], null),
      confidence: ratioField(risk, ['confidence_pct'], ['confidence'], `risks[${index}]`)
    };
  });
}

export function dashboardMetadata(dashboard) {
  return dashboard.metadata;
}
