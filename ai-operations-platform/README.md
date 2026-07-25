# AI Operations Platform

A support-operations intelligence platform built on a frozen, Zendesk-shaped
dataset (8,000 tickets with comments, metrics, audits, SLA events). React +
Vite frontend, FastAPI backend, with an `ai/` layer for the ML / embeddings /
GenAI features.

## Structure

```
ai-operations-platform/
├── frontend/          React + Vite + TypeScript dashboard
│   └── src/{pages,layouts,components,services,hooks,types,styles}
├── backend/           FastAPI
│   └── app/{api,services,repositories,ai,schemas,core,utils}
├── data/
│   ├── raw/zendesk/   frozen dataset — the SOURCE OF TRUTH (tickets, comments,
│   │                  ticket_metrics, ticket_audits, ticket_metric_events, sla_policies, …)
│   ├── processed/     AI pipeline artifacts (embeddings, models, clusters) — regenerable
│   └── sample/        small sample for docs/tests
├── scripts/           operational scripts (verify_data, future: build_embeddings, train_risk)
├── docs/              project documentation (markdown) — empty for now
├── Dockerfile · docker-compose.yml
```

## The dataset
The Zendesk store in `data/raw/zendesk/` is **frozen and will not be
regenerated** — it is the source of truth. It is 8,000 tickets (4,000 real seed
tickets + 4,000 unique GPT-5 Mini paraphrased variants), with fully consistent
companion objects (metrics / audits / SLA events) derived from a per-ticket
lifecycle. The generation methodology and provenance are archived outside the
app under `.parked/data-generation/` (kept out of the project for cleanliness).

## Run

Everything is driven from the `Makefile` — run `make` (or `make help`) to list targets.

```bash
make dev        # backend :8000 + frontend :5173 together (Ctrl-C stops both)
```

First run bootstraps the backend virtualenv (`backend/.venv`) and installs
frontend deps automatically. For AI features, add `OPENAI_API_KEY` to
`backend/.env` (`cp backend/.env.example backend/.env`).

| Command | What it does |
|---|---|
| `make dev` | Run backend + frontend together (auto-installs on first run) |
| `make dev-backend` / `make dev-frontend` | Run one side only |
| `make install` | Install backend + frontend dependencies |
| `make test` | Backend tests (pytest) |
| `make typecheck` | Frontend type-check (`tsc --noEmit`) |
| `make build` | Production build of the frontend |
| `make verify` | Validate the frozen Zendesk dataset |
| `make docker` / `make down` | Run / stop the full stack in Docker Compose |
| `make clean` / `make clean-all` | Remove build caches / also venv + node_modules |

Ports and interpreter are overridable, e.g. `make dev BACKEND_PORT=8080 PYBOOT=python3.12`.

## Health check
- `GET /` → service status
- `GET /api/health` → liveness
- `GET /api/health/data` → dataset summary (from the frozen store's manifest)

## Roadmap (AI features)
Grounded in the dataset's real labels/signal:
1. **SLA breach-risk prediction** — classical ML on real breach labels.
2. **Root-cause clustering** — embeddings + unsupervised + LLM cluster labels.
3. **Client health score** — statistical scoring over 120 organizations.
