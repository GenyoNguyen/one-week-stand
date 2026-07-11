# Demo Script — Final Presentation Structure

> Target length: **6 minutes of demo + 2 minutes of Q&A**. The click path below was verified end-to-end by an independent "judge dry-run" (review rounds 3–4, no dead ends). Every core performance figure has a second on-screen source — the "If challenged" column says where to point. Recommendation impacts ($38K, BAR steps) are modeled estimates that live on their card: own them as estimates rather than pointing elsewhere.

## Pre-stage checklist

- [ ] `npm run dev --prefix frontend` running; open `http://localhost:5173/#daily`; filters at **All properties · vs Budget**
- [ ] Refresh the page to reset Accept/Dismiss state
- [ ] Projector at 1280×860 or 1920×1080 (both verified, no layout breakage); the demo **runs offline** (self-hosted fonts, mock data)
- [ ] Have two CSVs ready for the Data section: one valid against the schema, one with missing columns

## Narrative: "From three hours of Excel to a ten-minute decision"

### 0. Hook — the problem (30 seconds, before opening the dashboard)

> "Every morning, The Anam's analysts spend most of the morning pulling data from disconnected systems into Excel — for each resort, every single day. Insight arrives late, forecasting is intuition-led, and every property does it differently. We replaced that morning with these ten minutes."

### 1. Daily overview — the morning briefing (90 seconds)

| Do | Say | If challenged |
|---|---|---|
| Open `#daily`, point at the freshness line in the filter bar | "It's 06:00 — data from all three resorts has already assembled itself." | "Data to 06:00 · PMS + CRS daily export" |
| Point at the hero | "The whole portfolio tonight: RevPAR **$204** — about 5% over budget and roughly 14% ahead of last year." | The **Portfolio** row at the bottom of the table: 91% · $224 · $204 — every digit matches; the hero's own delta lines show +4.9% and +13.7% |
| Sweep the 4 KPIs | "Occupancy **91%**, pickup in the last 24 hours, 30-day OTB revenue — each with its comparison. No naked numbers." | The delta under every KPI |
| Point at the outlook chart | "The next 30 days: the black line is what's on the books; the dashed line is the forecast with 50/80% confidence bands — we're honest about uncertainty." | "View as table" directly below the chart |

### 2. Alert → action — the centrepiece (2 minutes, the track's success criterion)

| Do | Say | If challenged |
|---|---|---|
| Point at "Needs attention", click **"Pace 18% behind for stays 3–9 Aug"** | "The system doesn't just report — it points at what needs a decision. The first week of August at Cam Ranh is pacing **18%** behind the same time last year." | The exact alert opens, with a 14-day pickup evidence sparkline |
| Read the recommended action | "A concrete recommendation: open the promotional BAR tier midweek 3–7 Aug on Brand.com and OTA, hold weekend rates. Roughly **$38K** if pace recovers to last year's trajectory." | The accent-bordered action block + impact line (a modeled estimate — say so if asked, don't point elsewhere) |
| **Click Accept** | "One click — the action is assigned to the Revenue team. This is the brief's own success measure: *teams acting on the recommendation, not merely reading a dashboard*." | Card shows "Accepted · sent to Revenue" under Resolved today; the subtitle counts "1 accepted today" |
| Open the Mui Ne alert | "A cancellation spike: **114** room nights in seven days, **2.6×** the norm — Booking.com's cancellation rate jumped from **8% to 19%**." | Segments & channels: the Booking.com row reads "19% (8%)"; Property view Mui Ne: KPI "114 rm · vs trailing norm (2.6×)" |

### 3. Forecast — one number for all three resorts (60 seconds)

| Do | Say | If challenged |
|---|---|---|
| Go to `#forecast`, switch 30d → 60d, hover the crosshair | "One consistent forecast by date and by property — replacing three different guesses. Hover any day: OTB, forecast, confidence band, budget." | "Forecast detail by stay date" table + "Show all 60 days" |
| **Select "The Anam Nha Trang" in the property filter**, then point at 1–2 Sep in the chart/table | "National Day at Nha Trang: **92%** already on the books, forecast closing at **97%** — so the system recommends raising BAR 12–15% with a 2-night minimum stay. Opportunities, not just risks." (The 92%/97% figures are per-property — they only show with Nha Trang selected; at "All properties" the portfolio blend is much lower.) | The forecast table rows for 1–2 Sep read OTB 92% / Forecast 97% (click "Show all 60 days" or hover the chart); the "National Day compression" alert quotes the same pair. **Reset the filter to All properties before the next step.** |

### 4. Property drill-down (45 seconds)

| Do | Say |
|---|---|
| Back to `#daily`, click the Cam Ranh row | "Overview to detail in one click. The pace curve — colour is this year, gray is last year — shows exactly the early-August gap we just acted on. The heatmap is 7-day pickup by stay date." |

### 5. Data & rollout — closing the loop (45 seconds)

| Do | Say |
|---|---|
| Go to `#data`, drag the valid CSV in | "Data arrives via a scheduled export every morning — no manual work. For corrections, drag and drop: the system validates all **17 columns** on the spot, and names exactly what's missing when a file is wrong." (drop the broken file if time allows) |
| Closing line | "The stack is deliberately boring — a static frontend and FastAPI; one in-region VM runs it, compliant with Vietnam's data-protection rules because only aggregated data ever leaves the PMS. Four weeks to pilot." |

### 6. Close (15 seconds)

> "The commercial team's morning now starts with decisions, not with Excel. Thank you."

## Anticipated Q&A

| Question | Answer + where to point |
|---|---|
| "Where does that number come from?" | Every core performance figure has a second source: the Portfolio row, the detail tables, the channel table (listed per step under "If challenged"). Recommendation impacts ($38K, BAR steps) are modeled estimates shown on their card — say so directly |
| "How accurate is the forecast?" | The dashboard shows confidence bands rather than a single point — honest about uncertainty; backtesting accuracy belongs to part 2 (MiroFish) |
| "Is this real data?" | The demo runs on mock data with the exact schema of the real export (17 columns — open the Data page); every UI component is unchanged when the backend connects |
| "What about guest privacy?" | Only aggregated/anonymised data is ingested, nationality at ISO-2 level, in-region hosting — see `deployment_plan.md` |
| "How long to deploy?" | Pilot on one property in 4 weeks on a single VM; all three properties by weeks 5–8 |

## Suggested staging (if presenting as a team)

- One speaker (this script) + one driver on the mouse (knows the click path cold) — never narrate and navigate at once.
- Rehearse at least twice on the actual projector; time the final run.
