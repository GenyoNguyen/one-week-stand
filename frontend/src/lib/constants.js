// Demo anchor date — mock data is generated around this morning's export
export const TODAY = new Date(2026, 6, 10); // Fri 10 Jul 2026
export const DATA_ASOF = '06:00 · Fri 10 Jul 2026';
export const DATA_SOURCE = 'PMS + CRS daily export';

// Fixed categorical order (validated palette) — a property keeps its colour
// on every screen, filters never repaint survivors.
export const SERIES = ['#0b8a76', '#c2540a', '#2e62b8', '#a03a6b', '#5f8321', '#7a52c7'];
export const GRAY_CONTEXT = '#b9b3a7'; // de-emphasis series (e.g. last year)

export const PROPERTIES = [
  { id: 'ACR', name: 'The Anam Cam Ranh', short: 'Cam Ranh', rooms: 213, color: SERIES[0] },
  { id: 'AMN', name: 'The Anam Mui Ne', short: 'Mui Ne', rooms: 127, color: SERIES[1] },
  { id: 'ANT', name: 'The Anam Nha Trang', short: 'Nha Trang', rooms: 156, color: SERIES[2] }
];

export const SEGMENTS = ['Direct', 'OTA', 'Wholesale', 'Corporate', 'Group'];

export const CHANNELS = [
  'Brand.com',
  'Booking.com',
  'Expedia',
  'Travel agents',
  'GDS',
  'Voice / email'
];

export const COMPARE_MODES = [
  { id: 'budget', label: 'vs Budget' },
  { id: 'ly', label: 'vs Last year' }
];

export const HORIZONS = [30, 60, 90];
