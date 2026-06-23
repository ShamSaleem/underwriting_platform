 Underwriting Platform

An enterprise-style showcase app for Life & Health underwriting eligibility.

- **Frontend** — React + TypeScript (Vite). Classy console UI: sidebar nav,
  portfolio dashboard with KPIs, applicant intake form (individual *and* company
  schemes), decision detail with cited findings, and case history.
- **Backend** — FastAPI reusing the hybrid **rules + Claude** underwriting engine,
  backed by a **database** (SQLite) that persists every assessed case.
- **Packaging** — one container (built SPA served by FastAPI) → **Google Cloud Run**.

```
underwriting-cloud/
  frontend/          React + Vite + TS app (builds into backend/static)
  backend/
    engine/          the underwriting engine (rules tables, LLM assessor, combiner)
    store.py         SQLite persistence (cases, stats)
    main.py          FastAPI: /api/* + serves the SPA
    requirements.txt
  Dockerfile         multi-stage: node build -> python runtime
  deploy/deploy.sh   one-command Cloud Run deploy
```

## Run locally

Two terminals during development (hot reload), or one container for prod-like.

**Backend**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8080 --reload
```

**Frontend (dev server, proxies /api → :8080)**
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

**Or prod-like (one process):** build the SPA, then just run the backend —
it serves the built app at `/`.
```bash
cd frontend && npm run build      # emits into backend/static
cd ../backend && uvicorn main:app --port 8080
# open http://localhost:8080
```

> Without `ANTHROPIC_API_KEY` the engine runs **rules-only** (all numeric
> thresholds work; free-text disclosures are skipped). Set the key to enable the
> Claude layer (`claude-opus-4-8`). `GET /api/health` reports the active mode.

## API

| Method | Path | Purpose |
|---|---|---|
| GET  | `/api/health`       | status + model + mode |
| GET  | `/api/stats`        | portfolio KPIs (counts, acceptance %, avg rating) |
| POST | `/api/underwrite`   | assess an applicant, **persist** the case, return the decision |
| GET  | `/api/cases`        | recent case history |
| GET  | `/api/cases/{id}`   | full case (request + decision) |

## Deploy to Google Cloud Run

One-time setup:
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
```

Deploy (builds the Dockerfile with Cloud Build, deploys to Cloud Run):
```bash
# optional: export ANTHROPIC_API_KEY=sk-ant-...   (enables the AI layer in prod)
./deploy/deploy.sh
```
The script prints the public HTTPS URL when finished.

### Notes for production
- **Database:** the demo uses SQLite on the container's `/tmp`, which resets when a
  Cloud Run instance is recycled — fine for a showcase. For durable storage, point
  `UW_DB_PATH` at a mounted **Cloud SQL** volume, or swap the three helpers in
  `store.py` for a Postgres driver (the rest of the app is unchanged). **Firestore**
  is also a clean serverless fit.
- **Secrets:** put `ANTHROPIC_API_KEY` in **Secret Manager** and reference it with
  `--set-secrets` instead of `--set-env-vars`.
- **Scaling:** `min-instances 0` keeps it scale-to-zero (cheap); raise it to avoid
  cold starts.
