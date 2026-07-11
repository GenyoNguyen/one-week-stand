# User Flow — Daily Operations

> Design principle: every view answers exactly one business question. Users don't "explore a dashboard" — they follow the morning routine they already have, just faster than Excel.

## Data rhythm

```
05:30  PMS/CRS writes the daily CSV export → shared folder / SFTP
05:35  Ingest service (part 1) validates and loads it
05:45  Forecast (part 2) and intelligence (part 3) re-run
06:00  Dashboard is ready — the "Data to 06:00" line in the filter bar confirms it
```

If the filter bar still shows yesterday's date at 06:15, the export hasn't arrived — contact the admin (see the monitoring section of `deployment_plan.md`).

## Flow 1 — Revenue/Commercial analyst's morning briefing (07:30, ~10 minutes)

The core flow. It replaces the 2–3 hours previously spent assembling Excel every morning.

```
Open the dashboard (#daily)
 │  Read the hero: RevPAR tonight + deltas vs Budget/LY   (30 seconds: good day or bad day?)
 │  Scan the 4 KPIs: Occupancy · ADR · Pickup 24h · Revenue OTB 30d
 │  Glance at "Occupancy outlook — next 30 days": any holes ahead?
 │
 ├─ "Needs attention" column (top 3 alerts by severity)
 │   └─ Click an alert → opens THAT alert in Alerts & actions
 │       │  Read the evidence (sparkline) + recommended action + impact estimate
 │       ├─ Accept → auto-assigned to its owner (Revenue/Sales/Distribution/Reservations)
 │       │           → card moves to "Resolved today"; repeat it in stand-up
 │       └─ Dismiss → give the reason verbally in stand-up (Undo if misclicked)
 │
 └─ "By property — tonight" table + Portfolio total row
     └─ A property is off? → click its row → Property view (Flow 3)
```

**End state of the briefing:** every alert in the queue has been accepted or dismissed. This is the track's success criterion: *teams acting on the system's recommendation, not merely reading its dashboard.*

## Flow 2 — GM / Group Commercial quick read (any time, ~2 minutes)

```
#daily   → the hero and its two delta lines answer "how is tonight?"
#forecast → fan chart: the forward book against budget; narrow bands = high confidence
#alerts  → the "x accepted today" counter in the subtitle: is the team acting?
```

GMs never need to operate anything — every number spoken out loud has a second on-screen source (the Portfolio row, the detail tables) when someone asks "where does that come from?".

## Flow 3 — Revenue manager deep-dive on one property (on an alert, or every Monday)

```
#property (via drill-down, or the Cam Ranh / Mui Ne / Nha Trang tabs)
 │  KPI row: Occ · ADR · Pickup 7d (vs pace needed) · Cancellations (vs norm)
 │  Booking pace curve: coloured line = this year, gray = same time last year
 │     → running ahead or behind LY? A gap at the head of the curve = the problem week
 │  Pickup heatmap: dark cells = dates currently absorbing bookings; an unusually
 │     pale row is worth investigating
 │  Segment mix: OTB for the next 30 days, legend carries exact shares
 └─ Rate/inventory decisions are then executed in the RMS/PMS (outside this system)
```

## Flow 4 — Reservations/Distribution when a channel misbehaves

```
#segments
 │  "By channel" table: the "Cxl rate (prev)" column — bold red = spike
 │  Demo example: Booking.com 19% (8%) ← the exact pair the Mui Ne alert quotes
 │  Segment mix by property + "View as table"
 └─ Top source markets: which markets are up/down vs LY (KR +34%, …)
```

## Flow 5 — Operations planning staffing (afternoon, for the coming week)

```
#forecast → select 30d → read "Forecast detail by stay date"
   The Forecast column + 80% band per day = expected rooms for shift planning
   Weekends (shaded rows) and holidays stand out directly in the table
```

## Flow 6 — Loading data (admin / analyst, when needed)

```
#data
 │  "Ingest status" table: 3 properties × last received × rows × status
 ├─ Normal days: nothing to do (the scheduled export runs itself)
 └─ Exceptions / backfill: drag a CSV into "Manual upload"
     → validated in place (17 required columns, date range, properties)
     → Ready → Import;  on error → the exact missing columns, plus a template download
```

Schema details and connection options: `data_upload_plan.md`.

## Lifecycle of an alert

```
Intelligence (part 3) raises an alert ──▶ Queue (#alerts, ordered Risk > Watch > Opportunity)
        │ the top 3 also surface on #daily under "Needs attention"
        ▼
   Analyst opens it (one card at a time — progressive disclosure)
        ├─ Accept  ──▶ "Resolved today" + owner assigned ──▶ repeated in stand-up
        └─ Dismiss ──▶ "Resolved today" (reason given verbally)
              └─ Undo at any point during the day → back to the open queue
```

Accept/dismiss state is currently session-local (mock). Once the backend is connected, status + owner + timestamp are written through the API, enabling a weekly "acted on" report — the track's success measure, made auditable.
