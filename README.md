# The Anam — Commercial Intelligence & Demand Forecasting

Hackathon entry for the [Commercial Intelligence & Demand Forecasting track](https://aitalent.genaifund.ai/tracks/retail-hospitality/commercial-demand): an AI system that ingests daily hotel data from The Anam's three resorts, forecasts demand by date and segment, and returns a clear performance read with recommended commercial actions — replacing a morning of manual Excel work with a ten-minute decision routine.

## Quick start

Requires Node 20.19+ (or 22.12+) and `uv`.

```bash
cp mirofish/.env.example mirofish/.env # first run only
# Set LLM_API_KEY and ZEP_API_KEY in mirofish/.env
./run.sh
npm install --prefix frontend
npm run dev --prefix frontend
```

Open **http://localhost:5173/#data**, upload a supported hotel CSV/XLSX/Markdown
file, and open the generated report or select it for the dashboard. MiroFish runs
on port 3000, its Flask API on 5001, and the Anam dashboard on 5173. Vite reads
the API target from the local environment and proxies browser `/api` requests to
Flask. All three development services bind to loopback by default.

For an offline UI-only review, start the dashboard with
`VITE_DASHBOARD_DEMO=true npm run dev --prefix frontend`; live results are the
default and never silently fall back to mock figures.

Production build: `npm run build --prefix frontend` → static files in `frontend/dist` (~500 KB total).

## MiroFish service controls

The project-level launcher reads `.env`, installs missing dependencies, and
starts the MiroFish frontend and backend with hot reload:

```bash
./run.sh
```

MiroFish's own UI runs on port 3000 and its Flask API on port 5001. The Anam
dashboard on port 5173 proxies `/api` directly to port 5001. The local forecast
API does not require a separate application key; keep it on loopback or put
authentication in front of it before exposing it to a network.

Every normal launch stops the previous managed instance first. Use
`./run.sh --setup-only` to install dependencies without starting services,
`./run.sh --skip-install` for a quick restart, or `./run.sh --stop` to stop it.

## Project structure

| Part | What | Where | Status |
|---|---|---|---|
| 1 | Data preparation & ingest | `data/`, `frontend/src/lib/tabular.js` | CSV/XLSX/Markdown upload live |
| 2 | Demand forecasting (MiroFish) | `mirofish/backend/app/services/` | Async hotel pipeline live |
| 3 | Commercial intelligence & recommendations | `mirofish/backend/app/services/hotel_dashboard.py` | Deterministic dashboard output live |
| 4 | **Dashboard & report UX** | `frontend/`, `docs/` | Live `hotel-dashboard.v1` integration |

The dashboard consumes the versioned `hotel-dashboard.v1` result returned with
each completed MiroFish report. Story-driven data in `frontend/src/lib/mock.js`
is retained only for explicit demo mode. The supported CSV contracts are
documented in [docs/data_upload_plan.md](docs/data_upload_plan.md).

## Documentation

- [Design plan & UX rules](docs/dashboard_plan.md) — design direction, 10 UX rules, chart rules, anti-AI-look checklist (Vietnamese)
- [User flow](docs/user_flow.md) — daily routines per persona and the alert lifecycle
- [Deployment plan](docs/deployment_plan.md) — 3-phase rollout, in-region hosting, PDPD compliance
- [Data upload / connection plan](docs/data_upload_plan.md) — ingest routes, CSV schema, validation
- [Demo script](docs/demo_script.md) — timed 6-minute presentation with verified click path

## Views

`#daily` morning briefing · `#forecast` demand forecast with 50/80% bands · `#property` pace & pickup deep-dive · `#segments` segment/channel/source-market mix · `#alerts` decision queue with accept/dismiss · `#data` ingest status & CSV upload
