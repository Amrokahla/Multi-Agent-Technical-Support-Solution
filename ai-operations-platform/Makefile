# AI Operations Platform — developer commands.
# Quick start:  make dev   (backend :8000 + frontend :5173, Ctrl-C stops both)

SHELL := /bin/bash

VENV := backend/.venv
PYBOOT ?= python3
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

.PHONY: install
install: $(VENV) frontend/node_modules ## Install backend + frontend dependencies

# Create the backend virtualenv and install requirements (rebuilds on change).
$(VENV): backend/requirements.txt
	$(PYBOOT) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	@touch $(VENV)

frontend/node_modules: frontend/package.json
	cd frontend && npm install
	@touch frontend/node_modules

# ---------------------------------------------------------------------------
# Develop
# ---------------------------------------------------------------------------

.PHONY: dev
dev: $(VENV) frontend/node_modules ## Run backend + frontend together (Ctrl-C stops both)
	@echo "→ backend   http://localhost:$(BACKEND_PORT)  (API docs at /docs)"
	@echo "→ frontend  http://localhost:$(FRONTEND_PORT)"
	@trap 'kill 0' EXIT INT TERM; \
	( cd backend && .venv/bin/uvicorn app.main:app --reload --port $(BACKEND_PORT) ) & \
	( cd frontend && npm run dev -- --port $(FRONTEND_PORT) ) & \
	wait

.PHONY: dev-backend
dev-backend: $(VENV) ## Run only the FastAPI backend (auto-reload)
	cd backend && .venv/bin/uvicorn app.main:app --reload --port $(BACKEND_PORT)

.PHONY: dev-frontend
dev-frontend: frontend/node_modules ## Run only the Vite frontend
	cd frontend && npm run dev -- --port $(FRONTEND_PORT)

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

.PHONY: test
test: $(VENV) ## Run backend tests (pytest)
	cd backend && .venv/bin/python -m pytest -q

.PHONY: typecheck
typecheck: frontend/node_modules ## Type-check the frontend (tsc --noEmit)
	cd frontend && npx tsc --noEmit

.PHONY: build
build: frontend/node_modules ## Production build of the frontend
	cd frontend && npm run build

.PHONY: verify
verify: $(VENV) ## Validate the frozen Zendesk dataset
	$(PY) scripts/verify_data.py

.PHONY: train-sla
train-sla: $(VENV) ## Train + pickle the SLA-risk model
	cd backend && .venv/bin/python -c "from app.ai.sla.model import train, save; print('wrote', save(train()))"

.PHONY: agent-demo
agent-demo: $(VENV) ## Ask the copilot the flagship question (needs OPENAI_API_KEY)
	cd backend && .venv/bin/python -c "from app.agent.orchestrator import answer; r=answer('We expect 30% more tickets tomorrow. Can we still meet SLA with 24 agents?'); print('\nANSWER:\n'+r.answer); print('\nTOOLS:'); [print(' -', t.tool, t.arguments, 'OK' if t.ok else t.error) for t in r.tool_trace]; print('\ngrounded:', r.grounding_ok)"

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

.PHONY: docker
docker: ## Build + run the full stack with Docker Compose
	docker compose up --build

.PHONY: up
up: docker ## Alias for `make docker`

.PHONY: down
down: ## Stop the Docker Compose stack
	docker compose down

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf frontend/dist
	find backend -type d -name __pycache__ -prune -exec rm -rf {} +
	find backend -type d -name .pytest_cache -prune -exec rm -rf {} +

.PHONY: clean-all
clean-all: clean ## Also remove the venv and node_modules
	rm -rf $(VENV) frontend/node_modules

.PHONY: help
help: ## Show this help
	@echo "AI Operations Platform — make targets:"
	@echo
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
