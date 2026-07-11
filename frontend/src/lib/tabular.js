export const SUPPORTED_UPLOAD_EXTENSIONS = ['csv', 'xlsx', 'md', 'markdown'];
export const MAX_UPLOAD_FILES = 10;
export const MAX_SOURCE_BYTES = 50 * 1024 * 1024;
export const MAX_MARKDOWN_BYTES = 50 * 1024 * 1024;
export const PERFORMANCE_SCHEMA_IDS = ['canonical-performance', 'pms-daily-export'];

export const HOTEL_SCHEMAS = [
  {
    id: 'canonical-performance',
    label: 'Canonical performance export',
    columns: [
      'date',
      'property',
      'occupancy_pct',
      'adr_vnd',
      'revpar_vnd',
      'room_nights',
      'revenue_vnd',
      'booking_pace_pct',
      'pickup_room_nights',
      'pickup_24h_room_nights',
      'market_segment',
      'source',
      'channel',
      'guest_nationality',
      'lead_time_days',
      'cancellations',
      'budget_room_nights',
      'budget_adr_vnd',
      'last_year_room_nights',
      'ly_adr_vnd',
      'on_the_books_room_nights',
      'stly_otb_room_nights'
    ]
  },
  {
    id: 'pms-daily-export',
    label: 'PMS / CRS daily export',
    columns: [
      'date',
      'property',
      'rooms_available',
      'rooms_sold',
      'room_revenue',
      'adr',
      'occupancy',
      'market_segment',
      'channel',
      'guest_nationality',
      'lead_time_days',
      'cancellations',
      'budget_occupancy',
      'budget_adr',
      'ly_occupancy',
      'ly_adr',
      'otb_rooms'
    ]
  },
  {
    id: 'property-reference',
    label: 'Property reference export',
    columns: [
      'property',
      'city',
      'province',
      'country',
      'property_type',
      'room_count',
      'currency',
      'timezone'
    ]
  },
  {
    id: 'room-inventory',
    label: 'Room inventory export',
    columns: [
      'property',
      'room_id',
      'room_type',
      'floor',
      'bed_type',
      'max_guests',
      'size_sqm',
      'base_rate_vnd'
    ]
  },
  {
    id: 'daily-guest-flow',
    label: 'Daily guest-flow export',
    columns: [
      'date',
      'property',
      'bookings_checking_in',
      'bookings_staying',
      'bookings_checking_out',
      'guests_checking_in',
      'guests_staying',
      'guests_checking_out',
      'staffing_risk_index',
      'staffing_status'
    ]
  }
];

function extensionOf(filename) {
  return String(filename).split('.').pop()?.toLowerCase() || '';
}

function cellText(value) {
  if (value == null) return '';
  if (value instanceof Date && !Number.isNaN(value.getTime())) {
    return value.toISOString().slice(0, 10);
  }
  return String(value).trim();
}

function normalizeHeader(value, index, used) {
  const base = cellText(value) || `column_${index + 1}`;
  const key = base.toLowerCase();
  const count = (used.get(key) || 0) + 1;
  used.set(key, count);
  return count === 1 ? base : `${base}_${count}`;
}

function trimTable(rawRows) {
  const rows = rawRows
    .map((row) => (Array.isArray(row) ? row.map(cellText) : []))
    .filter((row) => row.some(Boolean));
  if (!rows.length) return [];

  const width = rows.reduce((largest, row) => {
    let lastValue = row.length - 1;
    while (lastValue >= 0 && !row[lastValue]) lastValue -= 1;
    return Math.max(largest, lastValue + 1);
  }, 0);

  return rows.map((row) => Array.from({ length: width }, (_, index) => row[index] || ''));
}

function analyzeSheet(name, rawRows) {
  const table = trimTable(rawRows);
  if (!table.length) return null;

  const usedHeaders = new Map();
  const headers = table[0].map((value, index) => normalizeHeader(value, index, usedHeaders));
  const headerKeys = headers.map((header) => header.trim().toLowerCase());
  const rows = table.slice(1).filter((row) => row.some(Boolean));
  const candidates = HOTEL_SCHEMAS.map((schema) => ({
    ...schema,
    missing: schema.columns.filter((column) => !headerKeys.includes(column))
  })).sort((left, right) => left.missing.length - right.missing.length);
  const matchedSchema = candidates.find((schema) => schema.missing.length === 0) || null;
  const closestSchema = matchedSchema || candidates[0];
  const expectedColumns = new Set(closestSchema.columns);
  const dateIndex = headerKeys.indexOf('date');
  const propertyIndex = headerKeys.indexOf('property');
  const dates = [];
  const properties = new Set();

  for (const row of rows) {
    if (dateIndex >= 0 && row[dateIndex]) dates.push(row[dateIndex]);
    if (propertyIndex >= 0 && row[propertyIndex]) properties.add(row[propertyIndex]);
  }
  dates.sort();

  return {
    name,
    headers,
    headerKeys,
    rows,
    rowCount: rows.length,
    matchedSchema,
    closestSchema,
    missing: closestSchema.missing,
    extra: headerKeys.filter((column) => column && !expectedColumns.has(column)),
    dateFrom: dates[0] || null,
    dateTo: dates[dates.length - 1] || null,
    properties: [...properties].sort()
  };
}

export function escapeMarkdownCell(value) {
  return cellText(value)
    .replaceAll('\\', '\\\\')
    .replaceAll('|', '\\|')
    .replace(/\r?\n/g, '<br>');
}

function markdownHeading(value) {
  return cellText(value).replace(/[\r\n#]+/g, ' ').trim() || 'Sheet';
}

function sheetToMarkdown(sheet) {
  const header = `| ${sheet.headers.map(escapeMarkdownCell).join(' | ')} |`;
  const divider = `| ${sheet.headers.map(() => '---').join(' | ')} |`;
  const rows = sheet.rows.map(
    (row) => `| ${sheet.headers.map((_, index) => escapeMarkdownCell(row[index])).join(' | ')} |`
  );
  return [
    `## ${markdownHeading(sheet.name)}`,
    '',
    `Rows: ${sheet.rowCount}`,
    '',
    header,
    divider,
    ...rows
  ].join('\n');
}

function markdownFilename(sourceName) {
  const basename = String(sourceName).replace(/\.[^.]+$/, '');
  const safeName = basename.replace(/[^a-zA-Z0-9._-]+/g, '_').replace(/^_+|_+$/g, '');
  return `${safeName || 'hotel_data'}.md`;
}

function splitMarkdownRow(line) {
  let value = String(line).trim();
  if (!value.includes('|')) return null;
  if (value.startsWith('|')) value = value.slice(1);
  if (value.endsWith('|') && !value.endsWith('\\|')) value = value.slice(0, -1);

  const cells = [];
  let cell = '';
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index];
    const next = value[index + 1];
    if (character === '\\' && (next === '|' || next === '\\')) {
      cell += next;
      index += 1;
    } else if (character === '|') {
      cells.push(cell.trim());
      cell = '';
    } else {
      cell += character;
    }
  }
  cells.push(cell.trim());
  return cells;
}

function analyzeMarkdownTables(markdown) {
  const lines = markdown.split(/\r?\n/);
  const sheets = [];

  for (let index = 0; index < lines.length - 1; index += 1) {
    const headers = splitMarkdownRow(lines[index]);
    const divider = splitMarkdownRow(lines[index + 1]);
    if (
      !headers?.length ||
      divider?.length !== headers.length ||
      !divider.every((cell) => /^:?-{3,}:?$/.test(cell))
    ) {
      continue;
    }

    const rows = [headers];
    let rowIndex = index + 2;
    while (rowIndex < lines.length) {
      const row = splitMarkdownRow(lines[rowIndex]);
      if (!row) break;
      rows.push(row);
      rowIndex += 1;
    }
    const sheet = analyzeSheet(`Markdown table ${sheets.length + 1}`, rows);
    if (sheet) sheets.push(sheet);
    index = rowIndex - 1;
  }

  return sheets;
}

function uniqueMatchedSchemas(sheets) {
  const schemas = new Map();
  for (const sheet of sheets) {
    if (sheet.matchedSchema) schemas.set(sheet.matchedSchema.id, sheet.matchedSchema);
  }
  return [...schemas.values()];
}

function selectPrimarySheet(sheets) {
  return (
    sheets.find((sheet) => PERFORMANCE_SCHEMA_IDS.includes(sheet.matchedSchema?.id)) ||
    sheets.find((sheet) => sheet.matchedSchema) ||
    sheets[0] ||
    null
  );
}

export async function convertTabularFile(file) {
  const extension = extensionOf(file?.name);
  if (!SUPPORTED_UPLOAD_EXTENSIONS.includes(extension)) {
    throw new Error('Choose a CSV, XLSX, or Markdown file.');
  }
  if (!file.size) throw new Error('The selected file is empty.');
  if (file.size > MAX_SOURCE_BYTES) throw new Error('The selected file exceeds the 50 MB limit.');

  if (extension === 'md' || extension === 'markdown') {
    const markdown = await file.text();
    if (!markdown.trim()) throw new Error('The selected Markdown file is empty.');
    const sheets = analyzeMarkdownTables(markdown);
    const primarySheet = selectPrimarySheet(sheets);
    const matchedSchemas = uniqueMatchedSchemas(sheets);
    const markdownFile = new File([markdown], file.name, {
      type: 'text/markdown;charset=utf-8',
      lastModified: file.lastModified || Date.now()
    });
    return {
      sourceName: file.name,
      sourceFormat: 'MD',
      sourceSize: file.size,
      filename: file.name,
      markdown,
      markdownFile,
      markdownSize: markdownFile.size,
      sheets,
      sheetCount: sheets.length,
      rowCount: sheets.reduce((sum, sheet) => sum + sheet.rowCount, 0),
      primarySheet,
      matchedSchema: primarySheet?.matchedSchema || null,
      matchedSchemas,
      missing: primarySheet?.missing || [],
      extra: primarySheet?.extra || [],
      dateFrom: primarySheet?.dateFrom || null,
      dateTo: primarySheet?.dateTo || null,
      properties: primarySheet?.properties || [],
      error: primarySheet?.matchedSchema
        ? null
        : 'Markdown must contain a table matching a supported hotel data schema.',
      ok: Boolean(primarySheet?.matchedSchema && primarySheet.rowCount > 0)
    };
  }

  let workbook;
  let XLSX;
  try {
    XLSX = await import('xlsx');
    workbook = XLSX.read(await file.arrayBuffer(), {
      type: 'array',
      cellDates: true,
      dense: true
    });
  } catch {
    throw new Error('The spreadsheet could not be parsed.');
  }

  const sheets = workbook.SheetNames.map((name) => {
    const rows = XLSX.utils.sheet_to_json(workbook.Sheets[name], {
      header: 1,
      defval: '',
      raw: false,
      dateNF: 'yyyy-mm-dd',
      blankrows: false
    });
    return analyzeSheet(name, rows);
  }).filter(Boolean);

  if (!sheets.length || !sheets.some((sheet) => sheet.rowCount > 0)) {
    throw new Error('The spreadsheet has no data rows.');
  }

  const primarySheet = selectPrimarySheet(sheets);
  const matchedSchemas = uniqueMatchedSchemas(sheets);
  const sourceName = cellText(file.name).replace(/[\r\n]+/g, ' ');
  const markdown = [
    '# The Anam Hotel Data Export',
    '',
    `Source file: ${sourceName}`,
    `Source format: ${extension.toUpperCase()}`,
    `Worksheets: ${sheets.length}`,
    `Data rows: ${sheets.reduce((sum, sheet) => sum + sheet.rowCount, 0)}`,
    '',
    ...sheets.map(sheetToMarkdown)
  ].join('\n\n') + '\n';
  const filename = markdownFilename(file.name);
  const markdownFile = new File([markdown], filename, {
    type: 'text/markdown;charset=utf-8',
    lastModified: Date.now()
  });

  if (markdownFile.size > MAX_MARKDOWN_BYTES) {
    throw new Error('The converted Markdown exceeds the backend 50 MB limit.');
  }

  return {
    sourceName: file.name,
    sourceFormat: extension.toUpperCase(),
    sourceSize: file.size,
    filename,
    markdown,
    markdownFile,
    markdownSize: markdownFile.size,
    sheets,
    sheetCount: sheets.length,
    rowCount: sheets.reduce((sum, sheet) => sum + sheet.rowCount, 0),
    primarySheet,
    matchedSchema: primarySheet.matchedSchema,
    matchedSchemas,
    missing: primarySheet.missing,
    extra: primarySheet.extra,
    dateFrom: primarySheet.dateFrom,
    dateTo: primarySheet.dateTo,
    properties: primarySheet.properties,
    ok: Boolean(primarySheet.matchedSchema && primarySheet.rowCount > 0)
  };
}

export async function convertTabularFiles(fileList) {
  const sourceFiles = Array.from(fileList || []);
  if (!sourceFiles.length) throw new Error('Choose at least one hotel data file.');
  if (sourceFiles.length > MAX_UPLOAD_FILES) {
    throw new Error(`Choose no more than ${MAX_UPLOAD_FILES} hotel data files.`);
  }

  const files = await Promise.all(sourceFiles.map((file) => convertTabularFile(file)));
  const invalid = files.find((file) => !file.ok);
  if (invalid) {
    throw new Error(
      `${invalid.sourceName}: ${invalid.error || `missing columns: ${invalid.missing.join(', ')}`}`
    );
  }

  const schemas = new Map();
  for (const file of files) {
    for (const schema of file.matchedSchemas || [file.matchedSchema]) {
      if (schema) schemas.set(schema.id, schema);
    }
  }
  const matchedSchemas = [...schemas.values()];
  const performanceSchema = matchedSchemas.find((schema) =>
    PERFORMANCE_SCHEMA_IDS.includes(schema.id)
  );
  if (!performanceSchema) {
    throw new Error(
      'Include at least one daily reservation/performance dataset before running a forecast.'
    );
  }

  const markdownSize = files.reduce((sum, file) => sum + file.markdownSize, 0);
  if (markdownSize > MAX_MARKDOWN_BYTES) {
    throw new Error('The converted Markdown bundle exceeds the backend 50 MB limit.');
  }

  const datedFiles = files.filter((file) => file.dateFrom && file.dateTo);
  const properties = new Set(files.flatMap((file) => file.properties || []));
  const extras = new Set(files.flatMap((file) => file.extra || []));

  return {
    files,
    markdownFiles: files.map((file) => file.markdownFile),
    sourceNames: files.map((file) => file.sourceName),
    name: files.length === 1 ? files[0].sourceName : `${files.length} hotel data files`,
    sourceSize: files.reduce((sum, file) => sum + file.sourceSize, 0),
    markdownSize,
    rowCount: files.reduce((sum, file) => sum + (file.rowCount || 0), 0),
    sheetCount: files.reduce((sum, file) => sum + file.sheetCount, 0),
    matchedSchema: performanceSchema,
    matchedSchemas,
    missing: [],
    extra: [...extras].sort(),
    dateFrom: datedFiles.map((file) => file.dateFrom).sort()[0] || null,
    dateTo: datedFiles.map((file) => file.dateTo).sort().at(-1) || null,
    properties: [...properties].sort(),
    ok: true
  };
}
