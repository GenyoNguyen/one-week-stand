# The Anam — Commercial Intelligence & Demand Forecasting

Hackathon entry for the [Commercial Intelligence & Demand Forecasting track](https://aitalent.genaifund.ai/tracks/retail-hospitality/commercial-demand): an AI system that ingests daily hotel data from The Anam's three resorts, forecasts demand by date and segment, and returns a clear performance read with recommended commercial actions — replacing a morning of manual Excel work with a ten-minute decision routine.

## Quick start (dashboard)

Requires Node 18+.

```bash
npm install --prefix frontend
npm run dev --prefix frontend
```

Open **http://localhost:5173/#daily**. The demo runs fully offline (self-hosted fonts, bundled mock data) and is verified at 1280×860 and 1920×1080.

Production build: `npm run build --prefix frontend` → static files in `frontend/dist` (~500 KB total).

## Project structure

| Part | What | Where | Status |
|---|---|---|---|
| 1 | Data preparation & ingest | `backend/`, `data/` | Scaffold — in progress |
| 2 | Demand forecasting (MiroFish) | `backend/services/forecast.py`, `mirofish/` | Scaffold — in progress |
| 3 | Commercial intelligence & recommendations | `backend/services/intelligence.py` | Scaffold — in progress |
| 4 | **Dashboard, UX & deployment plan** | `frontend/`, `docs/` | **Complete** (6-round review, core signed off 27/27) |

The dashboard currently runs on story-driven mock data (`frontend/src/lib/mock.js`) whose shapes mirror the future FastAPI contract — when parts 1–3 land, only `frontend/src/lib/api.js` changes. The 17-column CSV data contract between ingest and dashboard is defined in [docs/data_upload_plan.md](docs/data_upload_plan.md).

## Documentation

- [Design plan & UX rules](docs/dashboard_plan.md) — design direction, 10 UX rules, chart rules, anti-AI-look checklist (Vietnamese)
- [User flow](docs/user_flow.md) — daily routines per persona and the alert lifecycle
- [Deployment plan](docs/deployment_plan.md) — 3-phase rollout, in-region hosting, PDPD compliance
- [Data upload / connection plan](docs/data_upload_plan.md) — ingest routes, CSV schema, validation
- [Demo script](docs/demo_script.md) — timed 6-minute presentation with verified click path

## Views

`#daily` morning briefing · `#forecast` demand forecast with 50/80% bands · `#property` pace & pickup deep-dive · `#segments` segment/channel/source-market mix · `#alerts` decision queue with accept/dismiss · `#data` ingest status & CSV upload
