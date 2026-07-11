const nf0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

const bad = (v) => !Number.isFinite(v);
let displayCurrency = 'USD';

export function setDisplayCurrency(currency) {
  const normalized = String(currency || '').trim().toUpperCase();
  displayCurrency = /^[A-Z]{3}$/.test(normalized) ? normalized : 'USD';
}

export const getDisplayCurrency = () => displayCurrency;

function currencySymbol(currency = displayCurrency) {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      currencyDisplay: 'narrowSymbol',
      maximumFractionDigits: 0
    }).formatToParts(0).find((part) => part.type === 'currency')?.value || currency;
  } catch {
    return currency;
  }
}

export const fmtInt = (v) => (bad(v) ? '—' : nf0.format(Math.round(v)));

export const fmtMoney = (v) =>
  bad(v)
    ? '—'
    : v >= 1000000
      ? `${currencySymbol()}${nf1.format(v / 1000000)}M`
      : v >= 100000
        ? `${currencySymbol()}${nf0.format(Math.round(v / 1000))}K`
        : `${currencySymbol()}${nf0.format(Math.round(v))}`;

export const fmtMoneyFull = (v) =>
  bad(v) ? '—' : `${currencySymbol()}${nf0.format(Math.round(v))}`;

export const fmtPct = (v, digits = 0) => (bad(v) ? '—' : `${(digits ? nf1 : nf0).format(v * 100)}%`);

// signed delta: "+4.2%" / "−1.8%" (true minus sign — the detail people notice)
export function fmtDelta(v, { pct = true, digits = 1 } = {}) {
  if (bad(v)) return '—';
  const n = pct ? v * 100 : v;
  const abs = digits ? nf1.format(Math.abs(n)) : nf0.format(Math.abs(n));
  const sign = n > 0.0001 ? '+' : n < -0.0001 ? '−' : '±';
  return `${sign}${abs}${pct ? '%' : ''}`;
}

// percentage-POINT delta: "+4.2 pts" — occupancy gaps are point differences,
// never relative growth, so they must not carry a % sign
export function fmtPts(v, digits = 1) {
  if (bad(v)) return '—';
  const n = v * 100;
  const abs = digits ? nf1.format(Math.abs(n)) : nf0.format(Math.abs(n));
  const sign = n > 0.0001 ? '+' : n < -0.0001 ? '−' : '±';
  return `${sign}${abs} pts`;
}

export function deltaClass(v, goodWhenUp = true) {
  if (bad(v)) return 'flat';
  if (Math.abs(v) < 0.0005) return 'flat';
  return v > 0 === goodWhenUp ? 'pos' : 'neg';
}

export const deltaArrow = (v) => (bad(v) || Math.abs(v) < 0.0005 ? '·' : v > 0 ? '▲' : '▼');

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const fmtDate = (d) => `${d.getDate()} ${MONTHS[d.getMonth()]}`;
export const fmtDateFull = (d) => `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
export const fmtDow = (d) => DAYS[d.getDay()];
export const isWeekend = (d) => d.getDay() === 5 || d.getDay() === 6; // Fri/Sat peak nights
