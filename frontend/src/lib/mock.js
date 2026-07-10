// ---------------------------------------------------------------------------
// Mock data for UI review while parts 1–3 (data / forecast / intelligence)
// are still in progress. Mirrors the shapes the FastAPI backend will return.
//
// Not pure random noise: a handful of commercial "stories" are injected so the
// dashboard reads like a real trading week (pace gap in early August at Cam
// Ranh, a cancellation spike at Mui Ne, National Day compression at Nha
// Trang). Alerts below reference the same numbers.
// ---------------------------------------------------------------------------
import { PROPERTIES, SEGMENTS, CHANNELS, TODAY } from './constants.js';

// deterministic PRNG so every demo run shows identical numbers
function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(20260710);
const noise = (amp) => (rand() - 0.5) * 2 * amp;
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

const DAY = 24 * 3600 * 1000;
export const addDays = (d, n) => new Date(d.getTime() + n * DAY);
const sameDay = (a, b) =>
  a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

// monthly occupancy seasonality (Vietnam coast: winter international season,
// Jul–Aug domestic summer, Sep–Oct typhoon trough; Mui Ne peaks in kite season)
const SEASON = {
  ACR: [0.86, 0.88, 0.84, 0.76, 0.72, 0.78, 0.85, 0.83, 0.6, 0.58, 0.68, 0.82],
  AMN: [0.88, 0.87, 0.82, 0.74, 0.65, 0.62, 0.71, 0.69, 0.55, 0.6, 0.78, 0.86],
  ANT: [0.84, 0.86, 0.82, 0.75, 0.7, 0.76, 0.83, 0.81, 0.58, 0.57, 0.66, 0.8]
};
const BASE_ADR = { ACR: 214, AMN: 152, ANT: 186 }; // USD
const BUDGET_BIAS = { ACR: 0.03, AMN: -0.02, ANT: 0.04 }; // plan vs likely actual
const YOY = 0.055; // portfolio running ~5.5% ahead of last year

const PAST_DAYS = 120;
const FUTURE_DAYS = 92;

function buildDaily() {
  const rows = [];
  for (const p of PROPERTIES) {
    for (let i = -PAST_DAYS; i <= FUTURE_DAYS; i++) {
      const date = addDays(TODAY, i);
      const m = date.getMonth();
      const dow = date.getDay();
      const weekendLift = dow === 5 || dow === 6 ? 0.06 : dow === 0 ? 0.02 : -0.02;
      const finalOcc = clamp(SEASON[p.id][m] + weekendLift + noise(0.045), 0.3, 0.98);
      const lead = i;

      // how much of final demand is already on the books at this lead time
      const otbShare = i <= 0 ? 1 : clamp(0.08 + 0.92 * Math.exp(-lead / 70) + noise(0.03), 0.05, 1);
      const otbOcc = finalOcc * otbShare;

      const seasonAdr = BASE_ADR[p.id] * (0.82 + SEASON[p.id][m] * 0.32);
      const adr = seasonAdr * (dow === 5 || dow === 6 ? 1.08 : 1) * (1 + noise(0.035));

      const row = {
        property: p.id,
        date,
        lead,
        capacity: p.rooms,
        // past = actual, future = on the books
        roomsSold: Math.round((i <= 0 ? finalOcc : otbOcc) * p.rooms),
        occ: i <= 0 ? finalOcc : otbOcc,
        adr,
        // references
        budgetOcc: clamp(finalOcc * (1 + BUDGET_BIAS[p.id] + noise(0.025)), 0.3, 0.99),
        budgetAdr: seasonAdr * (1 + BUDGET_BIAS[p.id] * 0.6),
        lyOcc: clamp(finalOcc / (1 + YOY + noise(0.03)), 0.25, 0.98),
        lyAdr: adr / (1 + 0.06 + noise(0.02)),
        stlyOtbRooms: 0, // filled below for future dates
        // movement
        pu7: 0,
        pu1: 0,
        cxl7: 0
      };
      row.revenue = row.roomsSold * adr;
      row.revpar = row.occ * adr;

      if (i > 0) {
        // forecast sits between OTB and capacity; bands widen with horizon
        const fcOcc = clamp(finalOcc * (1 + noise(0.025)), otbOcc, 0.99);
        const w80 = 0.045 + 0.09 * (lead / FUTURE_DAYS);
        row.fcOcc = fcOcc;
        row.fcLo80 = Math.max(otbOcc, fcOcc - w80);
        row.fcHi80 = Math.min(0.995, fcOcc + w80 * 0.8);
        row.fcLo50 = Math.max(otbOcc, fcOcc - w80 * 0.45);
        row.fcHi50 = Math.min(0.99, fcOcc + w80 * 0.38);
        row.stlyOtbRooms = Math.round(row.roomsSold / (1 + 0.06 + noise(0.09)));
        row.pu7 = Math.max(0, Math.round(row.roomsSold * (0.06 + 0.1 * Math.exp(-lead / 40)) + noise(2)));
        row.pu1 = Math.max(0, Math.round(row.pu7 / 6 + noise(1.2)));
        row.cxl7 = Math.max(0, Math.round(row.roomsSold * 0.02 + noise(1.5)));
      }
      rows.push(row);
    }
  }

  // ---- story injections (alerts below quote these numbers) ----------------
  for (const r of rows) {
    const d = r.date;
    // 1. Cam Ranh: pace gap for stays 3–9 Aug (week 32) — OTB exactly 18%
    // behind STLY, anchored to the STLY denominator so the alert copy,
    // the KPI table and this series can never drift apart
    if (r.property === 'ACR' && r.lead > 0 && d >= new Date(2026, 7, 3) && d <= new Date(2026, 7, 9)) {
      r.roomsSold = Math.min(r.capacity, Math.round(r.stlyOtbRooms * 0.82));
      r.occ = r.roomsSold / r.capacity;
      r.pu7 = Math.round(r.pu7 * 0.55);
      r.pu1 = Math.round(r.pu1 * 0.5);
      r.revenue = r.roomsSold * r.adr;
      r.revpar = r.occ * r.adr;
    }
    // 2. Mui Ne: cancellation spike for stays within 30 days
    if (r.property === 'AMN' && r.lead > 0 && r.lead <= 30) {
      r.cxl7 = Math.round(r.cxl7 * 2.3 + 1);
    }
    // 3. Nha Trang: National Day (1–2 Sep) compression — nearly sold out
    if (r.property === 'ANT' && d >= new Date(2026, 8, 1) && d <= new Date(2026, 8, 2)) {
      r.occ = 0.92 + noise(0.01);
      r.roomsSold = Math.round(r.occ * r.capacity);
      r.fcOcc = 0.97;
      r.fcLo80 = 0.93;
      r.fcHi80 = 0.99;
      r.fcLo50 = 0.95;
      r.fcHi50 = 0.985;
      r.revenue = r.roomsSold * r.adr;
      r.revpar = r.occ * r.adr;
    }
  }
  return rows;
}

const DAILY = buildDaily();

export function daily(propertyId = 'ALL') {
  return propertyId === 'ALL' ? DAILY : DAILY.filter((r) => r.property === propertyId);
}

// aggregate a set of per-property rows for one date into portfolio numbers
export function rollup(rows) {
  const capacity = rows.reduce((s, r) => s + r.capacity, 0) || 1;
  const roomsSold = rows.reduce((s, r) => s + r.roomsSold, 0);
  const revenue = rows.reduce((s, r) => s + r.revenue, 0);
  const w = (key) => rows.reduce((s, r) => s + r[key] * r.capacity, 0) / capacity;
  // reference ADRs must be room-night weighted — a simple mean of property
  // ADRs shifts the portfolio comparison by several dollars
  const budgetRooms = rows.reduce((s, r) => s + r.budgetOcc * r.capacity, 0);
  const budgetRev = rows.reduce((s, r) => s + r.budgetOcc * r.capacity * r.budgetAdr, 0);
  const lyRooms = rows.reduce((s, r) => s + r.lyOcc * r.capacity, 0);
  const lyRev = rows.reduce((s, r) => s + r.lyOcc * r.capacity * r.lyAdr, 0);
  return {
    capacity,
    roomsSold,
    revenue,
    occ: roomsSold / capacity,
    adr: roomsSold ? revenue / roomsSold : 0,
    revpar: revenue / capacity,
    budgetOcc: w('budgetOcc'),
    lyOcc: w('lyOcc'),
    budgetAdr: budgetRooms ? budgetRev / budgetRooms : 0,
    lyAdr: lyRooms ? lyRev / lyRooms : 0,
    fcOcc: rows.every((r) => r.fcOcc != null) ? w('fcOcc') : null,
    fcLo80: rows.every((r) => r.fcLo80 != null) ? w('fcLo80') : null,
    fcHi80: rows.every((r) => r.fcHi80 != null) ? w('fcHi80') : null,
    fcLo50: rows.every((r) => r.fcLo50 != null) ? w('fcLo50') : null,
    fcHi50: rows.every((r) => r.fcHi50 != null) ? w('fcHi50') : null,
    pu7: rows.reduce((s, r) => s + r.pu7, 0),
    pu1: rows.reduce((s, r) => s + r.pu1, 0),
    cxl7: rows.reduce((s, r) => s + r.cxl7, 0),
    stlyOtbRooms: rows.reduce((s, r) => s + r.stlyOtbRooms, 0)
  };
}

// portfolio (or single property) series by date over a range of leads
export function series(propertyId, fromLead, toLead) {
  const out = [];
  for (let i = fromLead; i <= toLead; i++) {
    const date = addDays(TODAY, i);
    const rows = daily(propertyId).filter((r) => sameDay(r.date, date));
    if (rows.length) out.push({ date, lead: i, ...rollup(rows) });
  }
  return out;
}

// ---- segments / channels / nationalities (next-30-day on-the-books) -------
const SEG_SHARE = {
  ACR: [0.24, 0.32, 0.19, 0.08, 0.17],
  AMN: [0.18, 0.41, 0.22, 0.04, 0.15],
  ANT: [0.22, 0.36, 0.16, 0.11, 0.15]
};
const SEG_LY_SHARE = {
  ACR: [0.22, 0.31, 0.2, 0.11, 0.16],
  AMN: [0.16, 0.38, 0.25, 0.05, 0.16],
  ANT: [0.21, 0.34, 0.17, 0.12, 0.16]
};
const SEG_CXL = [0.06, 0.18, 0.1, 0.08, 0.22];
const SEG_ADR_X = [1.12, 0.97, 0.84, 1.02, 0.9];

export function segments(propertyId = 'ALL') {
  const props = propertyId === 'ALL' ? PROPERTIES.map((p) => p.id) : [propertyId];
  return SEGMENTS.map((name, i) => {
    let rn = 0,
      rev = 0,
      lyRn = 0;
    for (const pid of props) {
      const next30 = daily(pid).filter((r) => r.lead > 0 && r.lead <= 30);
      const totRn = next30.reduce((s, r) => s + r.roomsSold, 0);
      const avgAdr = next30.reduce((s, r) => s + r.adr, 0) / next30.length;
      rn += totRn * SEG_SHARE[pid][i];
      rev += totRn * SEG_SHARE[pid][i] * avgAdr * SEG_ADR_X[i];
      lyRn += (totRn / (1 + YOY)) * SEG_LY_SHARE[pid][i];
    }
    return {
      segment: name,
      roomNights: Math.round(rn),
      revenue: rev,
      adr: rev / rn,
      cxlRate: SEG_CXL[i],
      deltaLy: (rn - lyRn) / lyRn
    };
  });
}

export function segmentMixByProperty() {
  return PROPERTIES.map((p) => ({
    property: p,
    mix: SEGMENTS.map((name, i) => ({ segment: name, share: SEG_SHARE[p.id][i] }))
  }));
}

const CH_SHARE = [0.17, 0.23, 0.12, 0.21, 0.08, 0.19];
const CH_CXL = [0.07, 0.19, 0.16, 0.09, 0.11, 0.05];
const CH_CXL_PREV = [0.07, 0.08, 0.15, 0.09, 0.1, 0.05]; // Booking.com spike is new
const CH_ADR_X = [1.08, 0.95, 0.93, 0.88, 1.04, 1.1];
const CH_DELTA_LY = [0.14, 0.09, -0.03, 0.02, -0.08, 0.05];

export function channels() {
  const next30 = daily('ALL').filter((r) => r.lead > 0 && r.lead <= 30);
  const totRn = next30.reduce((s, r) => s + r.roomsSold, 0);
  const avgAdr = next30.reduce((s, r) => s + r.revenue, 0) / totRn;
  return CHANNELS.map((name, i) => ({
    channel: name,
    roomNights: Math.round(totRn * CH_SHARE[i]),
    adr: avgAdr * CH_ADR_X[i],
    revenue: totRn * CH_SHARE[i] * avgAdr * CH_ADR_X[i],
    cxlRate: CH_CXL[i],
    cxlPrev: CH_CXL_PREV[i],
    deltaLy: CH_DELTA_LY[i]
  }));
}

export function nationalities() {
  return [
    { name: 'South Korea', share: 0.21, deltaLy: 0.34 },
    { name: 'Vietnam', share: 0.18, deltaLy: 0.08 },
    { name: 'Russia', share: 0.14, deltaLy: -0.05 },
    { name: 'Germany', share: 0.09, deltaLy: 0.02 },
    { name: 'United Kingdom', share: 0.08, deltaLy: 0.04 },
    { name: 'Australia', share: 0.07, deltaLy: -0.02 },
    { name: 'United States', share: 0.06, deltaLy: 0.11 },
    { name: 'Other', share: 0.17, deltaLy: 0.03 }
  ];
}

// ---- booking pace curve (August arrivals, cumulative room nights) ---------
export function paceCurve(propertyId) {
  const p = PROPERTIES.find((x) => x.id === propertyId);
  const lyTotal = Math.round(p.rooms * 31 * (SEASON[propertyId][7] / (1 + YOY) + 0.02));
  const tyTotal = Math.round(lyTotal * (1 + YOY));
  const share = (w) => 0.06 + 0.94 * Math.exp((-w * 7) / 60);
  const currentWeeksOut = 4; // early August is ~4 weeks from TODAY
  const points = [];
  for (let w = 20; w >= 0; w--) {
    const ly = Math.round(lyTotal * share(w) * (1 + noise(0.015)));
    let ty = null;
    if (w >= currentWeeksOut) {
      ty = Math.round(tyTotal * share(w) * (1 + noise(0.015)));
      // Cam Ranh's early-August gap shows at the head of the curve (same
      // 0.82 factor as the daily-series injection; the whole-month gap is
      // smaller than the week-32 gap because only one week is affected)
      if (propertyId === 'ACR' && w <= 6) ty = Math.round(ty * 0.82);
    }
    points.push({ weeksOut: w, ty, ly });
  }
  return { points, currentWeeksOut, monthLabel: 'August 2026' };
}

// ---- 7-day pickup by stay date, calendar layout (next 6 weeks) ------------
export function pickupCalendar(propertyId) {
  const rows = daily(propertyId).filter((r) => r.lead > 0 && r.lead <= 42);
  const byDate = new Map();
  for (const r of rows) {
    const k = r.date.toDateString();
    byDate.set(k, (byDate.get(k) || 0) + r.pu7);
  }
  return Array.from({ length: 42 }, (_, i) => {
    const date = addDays(TODAY, i + 1);
    return { date, pu7: byDate.get(date.toDateString()) || 0 };
  });
}

// ---- alerts & recommendations (part 3 will produce these for real) --------
// Numbers quoted in alert copy are DERIVED from the generated series above,
// so the story a card tells always matches what the charts and KPIs show.
const acrWk32 = DAILY.filter(
  (r) =>
    r.property === 'ACR' && r.lead > 0 && r.date >= new Date(2026, 7, 3) && r.date <= new Date(2026, 7, 9)
);
const ACR_PACE_GAP = Math.round(
  (1 - acrWk32.reduce((s, r) => s + r.roomsSold, 0) / acrWk32.reduce((s, r) => s + r.stlyOtbRooms, 0)) * 100
);
const amnNext30 = DAILY.filter((r) => r.property === 'AMN' && r.lead > 0 && r.lead <= 30);
const AMN_CXL_7D = amnNext30.reduce((s, r) => s + r.cxl7, 0);
// same trailing-norm definition the Property view KPI uses (~2% of OTB)
const AMN_CXL_X = (AMN_CXL_7D / amnNext30.reduce((s, r) => s + r.roomsSold * 0.02, 0)).toFixed(1);
const cxlCurve = [0.15, 0.12, 0.17, 0.15, 0.2, 0.29, 0.44, 0.54, 0.63, 0.76, 0.83, 0.93, 0.98, 1];

export const ALERTS = [
  {
    id: 'a1',
    severity: 'risk',
    property: 'ACR',
    title: `Pace ${ACR_PACE_GAP}% behind for stays 3–9 Aug`,
    body: `On-the-books for the first week of August is ${ACR_PACE_GAP}% behind same time last year. Daily pickup for these stays is running at roughly half of last year's rate.`,
    evidence: [16, 15, 17, 14, 15, 13, 12, 11, 10, 9, 9, 8, 9, 9],
    evidenceLabel: 'Daily pickup, rooms — last 14 days',
    action:
      'Open the promotional BAR tier for midweek 3–7 Aug on Brand.com and OTA. Hold weekend rates — weekend pace is on plan.',
    impact: '≈ $38K room revenue if pace recovers to LY trajectory',
    owner: 'Revenue'
  },
  {
    id: 'a2',
    severity: 'risk',
    property: 'AMN',
    title: 'Cancellation spike from Booking.com',
    body: `${AMN_CXL_7D} room nights cancelled in the last 7 days for stays within 30 days — ${AMN_CXL_X}× the trailing average. Booking.com's cancellation rate has jumped from ${Math.round(CH_CXL_PREV[1] * 100)}% to ${Math.round(CH_CXL[1] * 100)}% over the same window (see Segments & channels).`,
    evidence: cxlCurve.map((f) => Math.round(f * AMN_CXL_7D)),
    evidenceLabel: 'Rolling 7-day cancellations, room nights',
    action:
      'Rebalance 60% of released inventory to Expedia and Brand.com. Add a non-refundable fence at −12% to defend the base.',
    impact: 'Protects ≈ $22K of at-risk July revenue',
    owner: 'Distribution'
  },
  {
    id: 'a3',
    severity: 'opportunity',
    property: 'ANT',
    title: 'National Day compression, 1–2 Sep',
    body: 'Already 92% on the books for 1–2 Sep with 8 weeks of lead time left. Forecast closes at 97%.',
    evidence: [61, 64, 66, 70, 73, 75, 78, 81, 83, 86, 88, 90, 91, 92],
    evidenceLabel: 'OTB occupancy %, last 14 days',
    action: 'Raise BAR 12–15% for 1–3 Sep and set a 2-night minimum stay across OTA channels.',
    impact: '≈ $19K incremental ADR upside',
    owner: 'Revenue'
  },
  {
    id: 'a4',
    severity: 'watch',
    property: 'ACR',
    title: 'Corporate midweek softness in September',
    body: 'Corporate room nights for September are 21% behind last year while leisure segments hold. Two LRA accounts have gone quiet.',
    evidence: [54, 50, 52, 48, 47, 45, 44, 45, 42, 41, 43, 40, 42, 41],
    evidenceLabel: 'Corporate RN on the books for Sep, trailing view',
    action: 'Brief the sales team for targeted re-engagement on the two lapsed LRA accounts before end of July.',
    impact: 'Gap to close: ≈ 310 room nights',
    owner: 'Sales'
  },
  {
    id: 'a5',
    severity: 'opportunity',
    property: 'ALL',
    title: 'Korean market up 34% year on year',
    body: 'South Korea is now the #1 source market (21% of forward room nights), led by Cam Ranh direct flights. Growth is broad across all three properties.',
    evidence: [12, 13, 13, 14, 15, 15, 16, 17, 18, 18, 19, 20, 21, 21],
    evidenceLabel: 'KR share of forward room nights, %',
    action: 'Shift 20% of OTA marketing budget to Naver and Kakao placements; publish KR-language pages on Brand.com.',
    impact: 'Compounding — supports winter season base',
    owner: 'Marketing'
  },
  {
    id: 'a6',
    severity: 'watch',
    property: 'AMN',
    title: 'Kite-season pace strong but ADR flat',
    body: 'Nov–Dec occupancy pace is +12% vs LY while ADR is up only 1%. Demand is being sold too cheaply, too early.',
    evidence: [98, 102, 104, 105, 109, 108, 112, 113, 111, 114, 116, 115, 118, 112],
    evidenceLabel: 'Pace index vs LY = 100',
    action: 'Test +8% BAR on peak demand dates 15 Nov – 20 Dec; review wholesale allotment caps.',
    impact: '≈ $31K if ADR closes half the gap to pace',
    owner: 'Revenue'
  },
  {
    id: 'a7',
    severity: 'risk',
    property: 'ANT',
    title: 'Group block 62% unmaterialised, cutoff in 12 days',
    body: 'The 120-room MICE block for 22–25 Jul has confirmed only 46 rooms with the rooming-list cutoff on 22 Jul.',
    evidence: [10, 14, 18, 22, 25, 28, 31, 34, 36, 39, 42, 44, 45, 46],
    evidenceLabel: 'Rooms confirmed against block of 120',
    action: 'Chase the rooming list this week; release 40 rooms back to transient now while OTA demand is firm.',
    impact: 'Avoids ≈ 200 distressed room nights',
    owner: 'Reservations'
  }
];
