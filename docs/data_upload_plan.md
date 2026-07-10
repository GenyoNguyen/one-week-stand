# Data Upload / Connection Plan

> From the track brief: "Integration: read structured daily exports from property management and reservation systems. A direct connector is welcome, but a scheduled file export is acceptable."

## Three routes into the system (one shared validation pipeline)

| # | Route | When to use | Status |
|---|---|---|---|
| 1 | **Scheduled file export** (recommended) | Daily operations — PMS/CRS drops the CSV to SFTP/a shared folder at 05:30, the ingest job loads it, dashboards are ready by 06:00. No manual step. | Designed; needs part 1 |
| 2 | **Manual upload** (Data page in the UI) | Corrections, historical backfill, or as a fallback when the automated feed fails | **UI + client-side validation shipped** |
| 3 | **Direct PMS/CRS connector** (Opera Cloud / SynXis API) | Post-pilot, once credentials are provisioned — removes the file step entirely | Phase 3 |

All three routes land in the same validation before anything is written: a file that fails schema checks is rejected whole with a specific error — never partially ingested.

## Daily CSV schema (17 required columns)

One row = one combination of `stay date × property × segment × channel`. A file may contain many dates (backfill) or a single day (daily feed).

| Column | Type | Example | Notes |
|---|---|---|---|
| `date` | YYYY-MM-DD | 2026-07-09 | Stay date |
| `property` | code | ACR / AMN / ANT | Cam Ranh, Mui Ne, Nha Trang |
| `rooms_available` | int | 213 | |
| `rooms_sold` | int | 196 | Actual (past) / on-the-books (future) |
| `room_revenue` | number | 41160 | USD |
| `adr` | number | 210.00 | |
| `occupancy` | 0–1 | 0.92 | |
| `market_segment` | text | OTA / Direct / Corporate / Group / Wholesale | |
| `channel` | text | Booking.com / Brand.com / GDS … | |
| `guest_nationality` | ISO-2 | KR | Country level only — no guest-identifying data |
| `lead_time_days` | int | 21 | |
| `cancellations` | int | 3 | Room nights cancelled on the reporting day |
| `budget_occupancy` | 0–1 | 0.89 | |
| `budget_adr` | number | 205.00 | |
| `ly_occupancy` | 0–1 | 0.87 | Same time last year |
| `ly_adr` | number | 198.00 | |
| `otb_rooms` | int | 180 | On the books at export time |

A sample file is one click away: the **"Download CSV template"** button on the Data page generates the exact header plus two example rows. This table is also the data contract between part 1 (ingest) and part 4 (dashboard) — any schema change must update both sides and this document.

## Validation — two layers

**Layer 1 — client-side (already live in the UI, no backend needed):**
- File is `.csv`, readable, and has data rows.
- All 17 required columns present (missing ones are named individually); extra columns are listed and ignored.
- A pre-import summary — row count, date range, properties found — so the user confirms it's the right file before importing.

**Layer 2 — server-side (part 1, once the backend is connected):**
- Per-column types, `occupancy ∈ [0,1]`, `rooms_sold ≤ rooms_available`.
- Date continuity per property (gaps produce a warning); duplicate `date×property×segment×channel` keys → latest version wins.
- An ingest log — file, uploader/source, rows accepted/rejected, timestamp — surfaced back into the Data page's "Ingest status" table.

## Failure handling

| Situation | System behaviour |
|---|---|
| One property's file missing at 06:00 | Dashboard opens with the other two; a banner plus the freshness line state exactly which property is on stale data; admin is alerted |
| File fails schema validation | Rejected whole — no partial ingest; the error shows on the Data page and in the log |
| Re-upload of an existing day (restated figures) | Upsert by key — the new version overwrites, with a version log entry |
| Historical backfill | Same schema, one file spanning many dates; ≤ 1 year per file recommended |

## Current status

- The **Data** page (`#data`) ships today: ingest-status table (mock), dropzone with 17-column client-side validation, template download, and both connection options described — **fully usable without a backend**.
- The Import button currently ends at a "Queued" state (mock). When part 1 is ready, one function in `frontend/src/lib/api.js` switches to POST `/api/upload` — the UI is unchanged.
