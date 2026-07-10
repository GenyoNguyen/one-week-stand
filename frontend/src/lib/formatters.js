const nf0 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export const fmtInt = (v) => nf0.format(Math.round(v));

export const fmtMoney = (v) =>
  v >= 1000000
    ? `$${nf1.format(v / 1000000)}M`
    : v >= 100000
      ? `$${nf0.format(Math.round(v / 1000))}K`
      : `$${nf0.format(Math.round(v))}`;

export const fmtMoneyFull = (v) => `$${nf0.format(Math.round(v))}`;

export const fmtPct = (v, digits = 0) =>
  `${(digits ? nf1 : nf0).format(v * 100)}%`;

// signed delta: "+4.2%" / "−1.8%" (true minus sign — the detail people notice)
export function fmtDelta(v, { pct = true, digits = 1 } = {}) {
  const n = pct ? v * 100 : v;
  const abs = digits ? nf1.format(Math.abs(n)) : nf0.format(Math.abs(n));
  const sign = n > 0.0001 ? '+' : n < -0.0001 ? '−' : '±';
  return `${sign}${abs}${pct ? '%' : ''}`;
}

export function deltaClass(v, goodWhenUp = true) {
  if (Math.abs(v) < 0.0005) return 'flat';
  return v > 0 === goodWhenUp ? 'pos' : 'neg';
}

export const deltaArrow = (v) => (Math.abs(v) < 0.0005 ? '·' : v > 0 ? '▲' : '▼');

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export const fmtDate = (d) => `${d.getDate()} ${MONTHS[d.getMonth()]}`;
export const fmtDateFull = (d) => `${DAYS[d.getDay()]} ${d.getDate()} ${MONTHS[d.getMonth()]}`;
export const fmtDow = (d) => DAYS[d.getDay()];
export const isWeekend = (d) => d.getDay() === 5 || d.getDay() === 6; // Fri/Sat peak nights
