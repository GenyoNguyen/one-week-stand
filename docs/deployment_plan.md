# Deployment Plan

> From the track brief: cloud-based or hybrid is acceptable, no on-premise requirement, a widely supported cloud is preferred for ease of support. No live guest data during the build; a later pilot on real data should respect Vietnam's personal data protection requirements, with guest data remaining in-region preferred.

## Architecture overview

```
PMS / CRS (Opera, SynXis, …)
   │  daily CSV export at 05:30 (SFTP / shared folder)      ← Phase 1
   │  (direct API connector                                  ← Phase 3)
   ▼
Ingest service (part 1 — FastAPI job): validate 17-column schema → clean → store
   ▼
Forecast engine (part 2 — MiroFish) + intelligence (part 3 — alerts/recommendations)
   ▼
REST API (FastAPI): /kpis /forecast /alerts /recommendations /upload
   ▼
Dashboard (part 4 — Svelte, static build ~500KB including self-hosted fonts)
```

The frontend is static files — no secrets, no third-party calls at runtime (fonts are self-hosted), and it talks to the API on a single origin.

## Three rollout phases

### Phase 0 — Hackathon demo (current state)
- Runs locally: `npm run dev --prefix frontend` (mock data, works offline).
- No infrastructure required. This is the state that passed a 4-round review sign-off at 27/27.

### Phase 1 — Pilot on one property (weeks 1–4 after the hackathon)
- **Infrastructure:** one small VM (2 vCPU / 4GB) running Docker Compose: `nginx` (static files + reverse proxy) + `api` (FastAPI) + `postgres`. A single machine comfortably holds 3 properties × several years of daily data.
- **Region:** prefer an in-country provider (VNG Cloud, FPT Cloud, Viettel Cloud), or AWS `ap-southeast-1` (Singapore) if the group already uses it — satisfying the "data remaining in-region would be preferred" requirement.
- **Data in:** scheduled CSV export over SFTP at 05:30 (no access to the production PMS itself). Manual upload via the Data page remains the fallback path.
- **Access:** HTTPS behind the group's SSO (or basic auth for the pilot); internal network/VPN only.

### Phase 2 — All three properties + go-live (weeks 5–8)
- Enable all three export feeds; backfill two years of history so pace and LY comparisons are accurate.
- Training: one 45-minute session for the commercial teams (following `user_flow.md`), 15 minutes for GMs.
- Run in parallel with the Excel process for two weeks → reconcile numbers → retire the Excel workflow.

### Phase 3 — Direct connector (post-pilot, optional)
- API pull from Opera Cloud / SynXis replaces the file export. The schema is unchanged, so neither the dashboard nor the forecast needs modification.

## Compliance & data protection

| Requirement | How it is met |
|---|---|
| No live guest data during the build | The entire build/demo runs on mock + anonymised sample data |
| Vietnam PDPD (Decree 13/2023/ND-CP) | The pilot ingests aggregated/anonymised data only: no guest names, room numbers, or contact details. `guest_nationality` stays at country level (non-identifying) |
| Data in-region | VN/SG regions as above; no third-party SaaS receives the data |
| Access control | Pilot: one read-all role; go-live: per-property roles if the group requires them |

## Operations & monitoring

- **Health:** `GET /api/health` + an uptime ping every 5 minutes.
- **Ingest guard:** if fewer than 3 files have arrived by 06:00 → email/Zalo alert to the admin, and the dashboard shows a banner with the stale date (old numbers are never presented as fresh — the data-freshness principle).
- **Backups:** nightly `pg_dump`, 30-day retention. Source-of-truth is the export files, so a full re-ingest is always possible.
- **Rollback:** static frontend + version-tagged Docker images — rollback = switch the tag, under 5 minutes.

## Estimated cost (pilot)

One 4GB in-region VM ≈ $25–40/month plus domain/TLS. No licence fees — the whole stack is open source.
