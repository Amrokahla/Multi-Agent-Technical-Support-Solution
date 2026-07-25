# 01 — Deploying the AI Service Operations Copilot on Azure

A practical, copy-pasteable guide to running this project on Azure. It covers what
ships, the deployment shape, the one code change and two build files you need, and
three deployment paths (managed container, serverless container, single VM) with a
clear recommendation.

> **TL;DR (recommended path):** build one Docker image that serves the React
> frontend *and* the FastAPI API, push it to Azure Container Registry, and run it
> on **Azure App Service for Containers** as a **single instance** (Basic B2).
> Put the OpenAI key in App Settings. ~30 minutes, ~$30/month + OpenAI usage.
> **Prefer clicking?** §5.1 is a full portal walkthrough (open this blade, click this button).

---

## 1. What we are deploying

| Piece | Tech | Notes |
|---|---|---|
| Backend | FastAPI + Uvicorn (Python 3.12) | API served under `/api`; pandas + scikit-learn + statsmodels do the analytics |
| Frontend | React 19 + Vite (static build) | Calls the API at `VITE_API_URL ?? "/api"` (same-origin by default) |
| Data | Frozen Zendesk store (~102 MB) + WFM roster (~0.5 MB) | `data/raw/zendesk`, `data/raw/wfm` — **not in git** |
| Model | `sla_model.pkl` (~4 MB) | `data/processed/models/`; trains lazily on first use if missing |
| Calibration | JSON profiles (~8 KB) | `data/processed/profiles/` — these *are* in git |
| LLM | OpenAI GPT-5 (planner) + GPT-5-mini (synth) | Needs `OPENAI_API_KEY`; without it the copilot returns 503 (tools/reports still work) |

### Two facts that drive every decision below

1. **The dataset is not in git.** `data/raw/zendesk` is gitignored (102 MB). A build
   that starts from a fresh `git clone` will have no data. So the image must be built
   **where the data exists on disk** (your machine, or an `az acr build` that uploads
   your working tree) — not from a git-only CI checkout. See §7 for CI options.

2. **The app holds state in memory.** "Sync data" runs the pipeline once and caches
   the reports in-process (`functools.lru_cache`). The whole point is *sync once, then
   chat from cache*. If two instances run behind a load balancer, a user who syncs on
   instance A and then chats on instance B gets an unsynced backend. **Run exactly one
   instance.** This is a demo-grade, vertical-scale product by design — do not scale out.

### Target topology (recommended)

```
                        ┌─────────────────────────────────────────┐
   Browser  ──HTTPS──►  │  Azure App Service (Linux, 1 instance)   │
                        │  ┌─────────────────────────────────────┐ │
                        │  │ Docker image (from ACR)             │ │
                        │  │  /        → React static bundle     │ │
                        │  │  /api/*   → FastAPI (Uvicorn:8000)  │ │
                        │  │  bundled: data/ + sla_model.pkl     │ │
                        │  └─────────────────────────────────────┘ │
                        │  App Settings: OPENAI_API_KEY, …          │
                        └───────────────────┬─────────────────────┘
                                            │ HTTPS
                                            ▼
                                    api.openai.com  (GPT-5 / GPT-5-mini)
```

One image, one URL, no CORS, no separate frontend host.

---

## 2. Deployment options at a glance

| Path | Azure service | Best when | Idle cost | Effort |
|---|---|---|---|---|
| **A (recommended)** | App Service for Containers | You want a managed URL + TLS + simple secrets, always warm | ~$26–52/mo | Low |
| **B** | Azure Container Apps | You want consumption pricing / scale-to-zero (accepting cold starts) | $0 when idle* | Low–Med |
| **C** | Single VM + Docker Compose | You want full control / cheapest predictable box / matches "one VM, vertical only" | ~$30–70/mo | Medium |
| (split) | App Service (API) + Static Web Apps (frontend) | You specifically want the frontend on a CDN | Higher | Higher |

\* Container Apps can scale to zero, but this app's in-memory sync means cold starts
lose the cached reports; keep `min-replicas 1` for a demo, which removes the idle saving.

**Recommendation:** Path A. It is the least moving parts for a single-instance,
always-warm, stateful demo, and gives you HTTPS + a clean `*.azurewebsites.net` URL
out of the box. Paths B and C are documented in full in §6.

---

## 3. Prerequisites

- An **Azure subscription** (`az login` works).
- **Azure CLI** ≥ 2.60 — `az version`.
- **Docker** (only if you build locally; `az acr build` builds in the cloud instead).
- An **OpenAI API key** with access to `gpt-5` and `gpt-5-mini`.
- This repo checked out **with the data present** (`data/raw/zendesk/*.jsonl` on disk).

Verify the data is there before you build:

```bash
cd ai-operations-platform
ls -lh data/raw/zendesk/tickets.jsonl data/processed/models/sla_model.pkl
```

If `sla_model.pkl` is missing, generate it (the image will otherwise train it on the
first request, which is slow):

```bash
make train-sla        # writes data/processed/models/sla_model.pkl
```

---

## 4. Prepare the app for production

Three changes, all additive. Do these once and commit them (except secrets).

### 4.1 Serve the frontend from FastAPI (one code change)

In production we serve the built React bundle from the same process as the API, so
there is one origin and no CORS. Edit `backend/app/main.py`:

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles
# ... existing imports ...

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    app.include_router(api_router, prefix="/api")

    # Serve the built frontend at "/" when it is present (production image).
    # In dev this folder does not exist, so the API-only app is unchanged.
    web_dir = Path(__file__).resolve().parent.parent / "web"
    if web_dir.exists():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    else:
        @app.get("/")
        def root() -> dict:
            return {"service": settings.app_name, "status": "ok"}

    return app
```

> The current `@app.get("/")` JSON handler is kept only for the dev (no-bundle) case —
> when the bundle is mounted at `/`, that mount serves `index.html`. The app renders a
> single view (no client-side routing), so a plain `StaticFiles(html=True)` mount is
> enough. If you reintroduce client-side routes, add a catch-all that returns
> `index.html` for non-`/api` paths.

Use `/api/health` (already exists) for the platform health probe.

### 4.2 Production Dockerfile (multi-stage)

Create `Dockerfile.prod` in the project root. Stage 1 builds the frontend; stage 2
installs the backend, copies the data + model, and copies the built bundle to `web/`.

```dockerfile
# ---- Stage 1: build the React frontend ----
FROM node:20-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
# Vite outputs to /web/dist
RUN npm run build

# ---- Stage 2: backend + bundled data + static frontend ----
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    DATA_DIR=/app/data/raw/zendesk \
    WFM_DIR=/app/data/raw/wfm \
    PROCESSED_DIR=/app/data/processed \
    PROFILES_DIR=/app/data/processed/profiles

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
# ships the Zendesk store + sla_model.pkl + profiles
COPY data ./data
# the built frontend, served at "/"
COPY --from=frontend /web/dist ./web

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

> The `RUN python -c …` line is optional insurance. If you already ran `make train-sla`
> (recommended), the pkl is copied by `COPY data ./data` and the model never rebuilds.
> If the introspection helper name differs, just delete that RUN line — the app trains
> lazily on first request regardless.

### 4.3 A `.dockerignore` (do not skip this)

Without it, the build context balloons with `.venv`, `node_modules`, `.git`, notebooks,
etc. — slow uploads and a bloated image. Create `.dockerignore` in the project root:

```
**/.venv
**/node_modules
**/__pycache__
**/.pytest_cache
**/.mypy_cache
frontend/dist
backend/notebooks
.git
.gitignore
*.md
docs
plan
.env
.env.local
.DS_Store
```

Keep `data/` (needed at runtime) and `data/processed/` (the model + profiles).

### 4.4 Environment / configuration reference

The backend reads process env vars (they override any `.env`). In a container there is
no `.env` file, so set these as App Settings / container env vars.

| Variable | Required | Default | Set to (prod) |
|---|---|---|---|
| `OPENAI_API_KEY` | **yes** (for copilot) | — | your key (secret) |
| `ENVIRONMENT` | no | `development` | `production` |
| `DATA_DIR` | no | `…/data/raw/zendesk` | `/app/data/raw/zendesk` (set in image) |
| `WFM_DIR` | no | `…/data/raw/wfm` | `/app/data/raw/wfm` (set in image — see note) |
| `PROCESSED_DIR` | no | `…/data/processed` | `/app/data/processed` (set in image — see note) |
| `PROFILES_DIR` | no | `…/data/processed/profiles` | `/app/data/processed/profiles` (set in image — see note) |
| `PLANNER_MODEL` | no | `gpt-5` | `gpt-5` |
| `SYNTH_MODEL` | no | `gpt-5-mini` | `gpt-5-mini` |
| `OPENAI_MODEL` | no | `gpt-5-mini` | `gpt-5-mini` |
| `EMBEDDING_MODEL` | no | `text-embedding-3-small` | leave default |
| `CORS_ORIGINS` | no | `["http://localhost:5173"]` | `["https://<app>.azurewebsites.net"]` |
| `WEBSITES_PORT` | App Service only | — | `8000` (tells App Service the container port) |

Same-origin single-container deploys don't strictly need `CORS_ORIGINS`, but set it to
your public URL anyway — harmless, and correct if you later split the frontend out.

> **Why `WFM_DIR` / `PROCESSED_DIR` / `PROFILES_DIR` must be set explicitly.** `config.py`
> derives its default data paths from `PROJECT_ROOT = Path(__file__).parents[2]`, which is
> correct in the repo layout (`…/backend/app/config.py`) but resolves to `/` in the image
> (`/app/app/config.py`). `DATA_DIR` alone isn't enough — the other three dirs fall back to
> the broken `/data/...` default and the pipeline 500s on the first sync. The `Dockerfile.prod`
> above sets all four, so a fresh build needs no extra app settings.

### 4.5 The single-instance rule (repeat, because it matters)

- **App Service:** do not enable scale-out / autoscale. Keep it at 1 instance. Turn
  **Always On** on (Basic tier+) so the container never idles out and drops the cache.
- **Container Apps:** set `--min-replicas 1 --max-replicas 1`.
- **VM:** one container, naturally.

---

## 5. Path A (recommended) — App Service for Containers

Two routes to the **same result**: a click-by-click **Portal** walkthrough (§5.1) and
the equivalent **CLI** (§5.2). New to Azure? Follow §5.1.

> **Before you start**, do the §4 prep once on your machine and keep the terminal handy:
> add the `main.py` static mount (§4.1), create `Dockerfile.prod` (§4.2) and
> `.dockerignore` (§4.3), and run `make train-sla` so the model is bundled. There is
> exactly **one** step the portal can't do with a button — building your local Docker
> image (§5.1 step D) — and even that runs from the portal's own Cloud Shell.

### 5.1 Portal walkthrough (click-by-click)

#### A. Sign in
1. Open a new browser tab → go to **https://portal.azure.com** → sign in.
2. You land on the Azure **Home**. The **search bar** across the top is how you reach
   every service below.

#### B. Create a resource group (a folder for everything)
1. In the top search bar, type **Resource groups** → click **Resource groups** in the results.
2. Click **➕ Create** (top-left).
3. **Subscription:** pick yours. **Resource group:** type `aiops-rg`. **Region:** `(Europe) West Europe` (or nearest to you).
4. Click **Review + create** → **Create**.

#### C. Create the container registry (ACR)
1. Top search bar → type **Container registries** → click it.
2. Click **➕ Create**.
3. **Resource group:** `aiops-rg`. **Registry name:** `aiopsacr` + a few random digits
   (must be globally unique, lowercase letters/numbers only). **Location:** West Europe. **SKU:** **Basic**.
4. Click **Review + create** → **Create**. When it finishes, click **Go to resource**.
5. In the registry's left menu, click **Settings → Access keys**. Toggle **Admin user** to **Enabled**.
   Leave this tab open — you'll see **Login server**, **Username**, **Password** here.

#### D. Build & push your image into ACR
The portal has no "build my local code" button, so use the portal's built-in terminal:
1. In the Azure top bar, click the **Cloud Shell** icon (**`>_`**, next to the bell). Choose **Bash**.
   If prompted, click **Create storage** (one-time).
2. Get your code + data into the build. Two options — pick one:
   - **Easiest (your own terminal):** on your Mac run
     ```bash
     az login
     az acr build -r <YOUR_ACR_NAME> -t aiops:latest -f Dockerfile.prod .
     ```
     This uploads your working tree (data included, junk excluded by `.dockerignore`) and builds in Azure.
   - **Browser only (Cloud Shell):** locally zip the project first
     (`zip -r aiops.zip . -x '*/.venv/*' '*/node_modules/*' '*/.git/*'`), then in Cloud Shell click
     **Manage files → Upload**, choose `aiops.zip`, and run:
     ```bash
     unzip -q aiops.zip -d aiops && cd aiops
     az acr build -r <YOUR_ACR_NAME> -t aiops:latest -f Dockerfile.prod .
     ```
3. Wait for **"Build complete."** Verify: go to your ACR resource → **Services → Repositories** →
   you should see **`aiops`** with tag `latest`.

#### E. Create the Web App (App Service, container)
1. Top search bar → type **App Services** → click it → **➕ Create → Web App**.
2. **Basics** tab:
   - **Resource group:** `aiops-rg`.
   - **Name:** `aiops-copilot-` + a few digits → this becomes `https://aiops-copilot-….azurewebsites.net`.
   - **Publish:** select **Container**.
   - **Operating System:** **Linux**.
   - **Region:** West Europe.
   - **Pricing plan:** click **Create new**, name it `aiops-plan`; for size click **Change size → Basic → B2** → **Apply**.
3. Click the **Container** tab:
   - **Image Source:** **Azure Container Registry**.
   - **Registry:** your ACR. **Image:** `aiops`. **Tag:** `latest`.
4. Click **Review + create** → **Create**. When done, click **Go to resource**.

#### F. Add configuration + the OpenAI secret
1. In the Web App's left menu, click **Settings → Environment variables**
   (older portals: **Configuration → Application settings**).
2. Click **➕ Add** once per row, entering **Name** and **Value**:

   | Name | Value |
   |---|---|
   | `WEBSITES_PORT` | `8000` |
   | `ENVIRONMENT` | `production` |
   | `PLANNER_MODEL` | `gpt-5` |
   | `SYNTH_MODEL` | `gpt-5-mini` |
   | `OPENAI_API_KEY` | `sk-…` (your key) |
   | `CORS_ORIGINS` | `["https://aiops-copilot-….azurewebsites.net"]` |

3. Click **Apply** → **Confirm**.

#### G. Always On, HTTPS-only, health check, single instance
1. Left menu → **Settings → Configuration** → **General settings** tab:
   **Always on = On**. Click **Save**.
2. Left menu → **Settings → TLS/SSL settings** (or the Configuration general tab) →
   **HTTPS Only = On**.
3. Left menu → **Monitoring → Health check** → **Enable**, path `/api/health` → **Save**.
4. Left menu → **Settings → Scale out (App Service plan)** → make sure it is **Manual, 1 instance**
   (do **not** turn on autoscale — the app is single-instance by design).

#### H. Restart and test
1. Top of the Web App page → **Restart** → **Yes**.
2. **Overview** → click the **Default domain** URL (or **Browse**) → opens `https://…azurewebsites.net`.
3. In the app: click **Sync data** (the first sync is slow — pipeline + model), then ask a question.

#### I. Connect your GoDaddy domain (`copilot.classiox.com`)
1. Web App left menu → **Settings → Custom domains** → **➕ Add custom domain**.
2. **Domain provider:** *All other domain services*. **Certificate:** *App Service Managed Certificate*.
   **TLS/SSL type:** *SNI SSL*. **Domain:** type `copilot.classiox.com`.
   The blade now shows a **CNAME target** (`…azurewebsites.net`) and a **TXT verification value** — copy both.
3. Open a second tab → **GoDaddy → your domain → Domain → DNS → Manage DNS → Add** and create:

   | Type | Name | Value |
   |---|---|---|
   | CNAME | `copilot` | `<app>.azurewebsites.net` |
   | TXT | `asuid.copilot` | `<verification value from Azure>` |

4. Back in Azure → click **Validate**. When both checks go green, click **Add**. Azure issues and
   binds the free certificate automatically (a minute or two).
5. Left menu → **Environment variables** → edit `CORS_ORIGINS` to
   `["https://copilot.classiox.com"]` → **Apply** → **Restart**.

Your copilot is live at **https://copilot.classiox.com**.

#### (optional) Auto-redeploy on new images
Web App → **Deployment → Deployment Center** → **Settings**: source **Azure Container Registry**,
registry/image `aiops:latest`, **Continuous deployment = On** → **Save**. Now every new
`az acr build … -t aiops:latest` push auto-redeploys via a webhook.

### 5.2 Same result via the Azure CLI

All commands use the Azure CLI. Set your variables first (names in caps are yours to
choose; ACR and the web app name must be globally unique).

```bash
# --- variables ---
RG=aiops-rg
LOC=westeurope
ACR=aiopsacr$RANDOM              # lowercase alphanumeric, globally unique
PLAN=aiops-plan
APP=aiops-copilot-$RANDOM        # becomes https://<APP>.azurewebsites.net
IMAGE=aiops:latest
OPENAI_KEY='sk-...'              # your key — do not commit
```

### Step 1 — Resource group + container registry

```bash
az group create -n "$RG" -l "$LOC"
az acr create -n "$ACR" -g "$RG" --sku Basic --admin-enabled true
```

### Step 2 — Build the image and push to ACR

**Option 1 — build in the cloud (no local Docker needed).** `az acr build` tars your
current working tree (honoring `.dockerignore`, so the data is included but junk is not),
uploads it, and builds on Azure:

```bash
az acr build -r "$ACR" -t "$IMAGE" -f Dockerfile.prod .
```

**Option 2 — build locally and push:**

```bash
az acr login -n "$ACR"
docker build -f Dockerfile.prod -t "$ACR.azurecr.io/$IMAGE" .
docker push "$ACR.azurecr.io/$IMAGE"
```

Either way the ~106 MB of data is baked into the image. Expect a final image around
0.8–1.2 GB (Python + scientific libs + data). That is normal.

### Step 3 — App Service plan + web app

B2 (2 vCPU, 3.5 GB RAM) gives comfortable headroom for pandas loading the ~100 MB of
JSONL plus the sklearn model. B1 (1.75 GB) can work but is tight; start at B2.

```bash
az appservice plan create -n "$PLAN" -g "$RG" --is-linux --sku B2

az webapp create -n "$APP" -g "$RG" -p "$PLAN" \
  -i "$ACR.azurecr.io/$IMAGE"
```

Give the web app the registry credentials so it can pull the image:

```bash
ACR_USER=$(az acr credential show -n "$ACR" --query username -o tsv)
ACR_PASS=$(az acr credential show -n "$ACR" --query 'passwords[0].value' -o tsv)

az webapp config container set -n "$APP" -g "$RG" \
  --docker-custom-image-name "$ACR.azurecr.io/$IMAGE" \
  --docker-registry-server-url "https://$ACR.azurecr.io" \
  --docker-registry-server-user "$ACR_USER" \
  --docker-registry-server-password "$ACR_PASS"
```

### Step 4 — App settings (config + secret)

```bash
az webapp config appsettings set -n "$APP" -g "$RG" --settings \
  WEBSITES_PORT=8000 \
  ENVIRONMENT=production \
  PLANNER_MODEL=gpt-5 \
  SYNTH_MODEL=gpt-5-mini \
  OPENAI_API_KEY="$OPENAI_KEY" \
  CORS_ORIGINS="[\"https://$APP.azurewebsites.net\"]"
```

### Step 5 — Always On, HTTPS-only, health check, single instance

```bash
az webapp config set -n "$APP" -g "$RG" --always-on true --health-check-path /api/health
az webapp update -n "$APP" -g "$RG" --https-only true
# Ensure a single instance (no scale-out):
az appservice plan update -n "$PLAN" -g "$RG" --number-of-workers 1
```

### Step 6 — Restart and verify

```bash
az webapp restart -n "$APP" -g "$RG"
az webapp browse  -n "$APP" -g "$RG"     # opens https://<APP>.azurewebsites.net
```

Smoke test from the terminal:

```bash
URL="https://$APP.azurewebsites.net"
curl -s "$URL/api/health"                       # {"status":"ok",...}
curl -s -X POST "$URL/api/reports/sync" | head  # runs the pipeline once (slow first call)
curl -s "$URL/" | grep -o '<title>.*</title>'   # frontend served
```

Then in the browser: **Sync data → ask a question**. First sync is the slow step
(pipeline + model); chat afterwards is fast (served from the in-memory reports).

### Step 7 — Custom domain + managed TLS (GoDaddy: `classiox.com`)

This project has a GoDaddy domain, `classiox.com`. Use a **subdomain** —
`copilot.classiox.com` — not the apex: a subdomain uses a clean `CNAME`, gets a free
managed cert with no fuss, and leaves whatever is on the GoDaddy apex ("Coming soon"
page, email, etc.) untouched. Apex setup is covered after, if you really want the root.

> **Don't confuse these with GoDaddy's own records.** GoDaddy's "Connect your domain"
> wizard points the apex at *its* website builder — e.g. `A @ → 13.248.243.5` and
> `CNAME www → classiox.com`. Those serve GoDaddy's Coming-soon/AI-builder site, **not**
> your Azure app. They coexist fine with the copilot's subdomain records below: keep
> GoDaddy's `@` and `www` as-is if you want its page on the root, and add the separate
> `copilot` CNAME + `asuid.copilot` TXT for the app. Only if you put the copilot on the
> **apex** do you replace GoDaddy's `A @ 13.248.243.5` with Azure's inbound IP (which
> takes the GoDaddy page offline).

**1. Get the two values Azure needs.** The domain-verification ID proves you own the host:

```bash
HOST=copilot.classiox.com
VERIFY_ID=$(az webapp show -n "$APP" -g "$RG" --query customDomainVerificationId -o tsv)
echo "CNAME  $HOST  ->  $APP.azurewebsites.net"
echo "TXT    asuid.copilot  ->  $VERIFY_ID"
```

**2. Add the DNS records in GoDaddy.** Sign in → your domain → **Domain → DNS →
Manage DNS → Add** (the "Domain" item in the GoDaddy left nav). Add both:

| Type | Name | Value | TTL |
|---|---|---|---|
| `CNAME` | `copilot` | `<APP>.azurewebsites.net` | 1 Hour |
| `TXT` | `asuid.copilot` | `<VERIFY_ID from step 1>` | 1 Hour |

> GoDaddy uses the host **prefix** only in "Name" (put `copilot`, not the full
> `copilot.classiox.com`; put `asuid.copilot`, not `asuid.copilot.classiox.com`).
> DNS can take a few minutes to an hour to propagate — check with
> `dig +short copilot.classiox.com CNAME` and `dig +short asuid.copilot.classiox.com TXT`.

**3. Bind the hostname and issue the certificate in Azure** (once DNS resolves):

```bash
az webapp config hostname add -n "$APP" -g "$RG" --hostname "$HOST"
az webapp config ssl create   -n "$APP" -g "$RG" --hostname "$HOST"   # free App Service managed cert

# bind the new cert (SNI)
THUMB=$(az webapp config ssl list -g "$RG" \
  --query "[?subjectName=='$HOST'].thumbprint" -o tsv)
az webapp config ssl bind -n "$APP" -g "$RG" --certificate-thumbprint "$THUMB" --ssl-type SNI
```

**4. Point the app's config at the domain.** Update the public URL in CORS (harmless for
the single-container deploy, required if you ever split the frontend):

```bash
az webapp config appsettings set -n "$APP" -g "$RG" --settings \
  CORS_ORIGINS='["https://copilot.classiox.com"]'
az webapp restart -n "$APP" -g "$RG"
```

Your app is now at **https://copilot.classiox.com**.

**Apex (`classiox.com`) instead of a subdomain** — only if you want the bare root.
GoDaddy can't `CNAME` the apex, so use an `A` record to the app's inbound IP plus the
same TXT verification (named `asuid` at the root). Note the GoDaddy apex likely already
has an A record / forwarding for the current site — you must remove that first, and it
takes the "Coming soon" page offline.

```bash
IP=$(az webapp show -n "$APP" -g "$RG" --query inboundIpAddress -o tsv)
echo "A     @      -> $IP"
echo "TXT   asuid  -> $VERIFY_ID"
# then: az webapp config hostname add … --hostname classiox.com ; ssl create ; ssl bind (as above)
```

> On Basic/Standard tiers the App Service inbound IP is stable for the life of the app but
> can change if the app is deleted/recreated or scaled across certain tier changes. For a
> long-lived apex, prefer a subdomain, or an IP-SSL binding / Azure Front Door if you need
> a fixed apex IP. For this demo, `copilot.classiox.com` is the low-friction choice.

---

## 6. Alternative paths

### Path B — Azure Container Apps

Good if you prefer consumption pricing. Keep exactly one replica so the in-memory sync
survives; that removes scale-to-zero savings but keeps the model correct.

```bash
RG=aiops-rg; LOC=westeurope; ACR=aiopsacr$RANDOM; ENVN=aiops-env; APP=aiops-copilot; IMAGE=aiops:latest
az group create -n "$RG" -l "$LOC"
az acr create -n "$ACR" -g "$RG" --sku Basic --admin-enabled true
az acr build -r "$ACR" -t "$IMAGE" -f Dockerfile.prod .

az extension add --name containerapp --upgrade
az containerapp env create -n "$ENVN" -g "$RG" -l "$LOC"

az containerapp create -n "$APP" -g "$RG" --environment "$ENVN" \
  --image "$ACR.azurecr.io/$IMAGE" \
  --registry-server "$ACR.azurecr.io" \
  --registry-username "$(az acr credential show -n "$ACR" --query username -o tsv)" \
  --registry-password "$(az acr credential show -n "$ACR" --query 'passwords[0].value' -o tsv)" \
  --target-port 8000 --ingress external \
  --min-replicas 1 --max-replicas 1 \
  --cpu 1.0 --memory 2.0Gi \
  --secrets openai-key="$OPENAI_KEY" \
  --env-vars ENVIRONMENT=production PLANNER_MODEL=gpt-5 SYNTH_MODEL=gpt-5-mini OPENAI_API_KEY=secretref:openai-key
```

The public URL is printed as `properties.configuration.ingress.fqdn`. Bump `--memory`
to `4.0Gi` if you see OOM during the first sync.

### Path C — single VM + Docker Compose

Closest to "one box, vertical only", cheapest predictable cost, full control. You manage
the OS and TLS. A production compose that runs the single combined image behind Caddy
(automatic HTTPS) is the simplest robust setup.

1. **Create the VM** (Ubuntu 22.04, 2 vCPU / 4 GB, e.g. `Standard_B2s`):

```bash
az group create -n aiops-rg -l westeurope
az vm create -g aiops-rg -n aiops-vm --image Ubuntu2204 --size Standard_B2s \
  --admin-username azureuser --generate-ssh-keys
az vm open-port -g aiops-rg -n aiops-vm --port 80,443
```

2. **Install Docker**, copy the repo up (the data must go too — it is not in git):

```bash
# from your machine — rsync the working tree INCLUDING data, excluding junk
rsync -az --exclude '.venv' --exclude 'node_modules' --exclude '.git' \
  ./ azureuser@<VM_IP>:~/aiops/
ssh azureuser@<VM_IP> 'curl -fsSL https://get.docker.com | sh'
```

3. **`docker-compose.prod.yml`** on the VM (single combined image + Caddy TLS):

```yaml
services:
  app:
    build: { context: ., dockerfile: Dockerfile.prod }
    environment:
      - ENVIRONMENT=production
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PLANNER_MODEL=gpt-5
      - SYNTH_MODEL=gpt-5-mini
    restart: unless-stopped
  caddy:
    image: caddy:2
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
    depends_on: [app]
    restart: unless-stopped
volumes: { caddy_data: {} }
```

`Caddyfile` (replace the host; Caddy fetches a Let's Encrypt cert automatically):

```
copilot.yourdomain.com {
    reverse_proxy app:8000
}
```

4. **Run it:**

```bash
ssh azureuser@<VM_IP>
cd ~/aiops
export OPENAI_API_KEY=sk-...
docker compose -f docker-compose.prod.yml up -d --build
```

> The repo's existing `docker-compose.yml` is the **dev** two-container setup (Vite on
> 5173 + API on 8000). For a VM demo without a domain you can use it directly, but you
> must set `VITE_API_URL` to the VM's public API URL and open ports 5173/8000. The
> combined image above is cleaner for anything public.

---

## 7. Secrets & security

- **The OpenAI key is the only real secret.** Never commit it. It currently lives in
  the workspace `.env.local` (gitignored) — keep it that way locally.
- **Production:** set it as an App Setting (App Service — encrypted at rest) or a
  Container Apps secret. For stronger handling, use **Key Vault references**:

  ```bash
  az keyvault create -n aiops-kv -g "$RG" -l "$LOC"
  az keyvault secret set --vault-name aiops-kv -n openai-api-key --value "$OPENAI_KEY"
  # enable a managed identity on the web app, grant it 'get' on the vault, then:
  az webapp config appsettings set -n "$APP" -g "$RG" --settings \
    OPENAI_API_KEY="@Microsoft.KeyVault(SecretUri=https://aiops-kv.vault.azure.net/secrets/openai-api-key/)"
  ```

- **HTTPS only** — enforced in Step 5 (`--https-only true`); Caddy does it on the VM.
- **Registry** — `--admin-enabled true` is fine for a demo; for anything longer-lived,
  turn it off and let the web app pull via a managed identity (`az webapp identity assign`
  + `AcrPull` role on the ACR).
- **No PII to worry about beyond the dataset** — the Zendesk store is synthetic/frozen;
  still, do not expose the raw `data/` over any public route (it isn't — only the derived
  reports and the CSV sample are).

---

## 8. Cost estimate (rough — verify in the Azure Pricing Calculator)

Prices vary by region and change over time; these are ballpark monthly figures for West
Europe as of mid-2026.

| Item | Choice | ~Monthly |
|---|---|---|
| Compute (Path A) | App Service Linux **B2** | ~$26 (B1 ~$13, B3 ~$52) |
| Compute (Path B) | Container Apps, 1 replica always on, 1 vCPU/2 GiB | ~$30–40 |
| Compute (Path C) | VM `Standard_B2s` | ~$30 (`D2s v5` ~$70) |
| Container registry | ACR **Basic** | ~$5 |
| Bandwidth | Low (single small app) | ~$1–3 |
| **OpenAI usage** | GPT-5 planning + GPT-5-mini synth, per query | **variable** — the real cost driver |

OpenAI is billed separately from Azure and scales with usage. The "sync once, chat from
cache" design keeps token spend down (baseline questions make **zero** tool/LLM planning
calls beyond synthesis), but the investigative tools — especially `analyze_tickets`, which
reads real ticket text — are the expensive ones. Budget from your expected demo volume.

---

## 9. Observability & operations

```bash
# Live logs (App Service)
az webapp log tail -n "$APP" -g "$RG"

# Enable filesystem logging
az webapp log config -n "$APP" -g "$RG" --docker-container-logging filesystem

# Restart after a config change
az webapp restart -n "$APP" -g "$RG"
```

- **Application Insights** (optional): `az monitor app-insights component create …` then
  set `APPLICATIONINSIGHTS_CONNECTION_STRING` as an App Setting for request/latency
  telemetry.
- **Health probe:** `/api/health` (already wired in Step 5) — it does not touch the
  dataset, so it stays green even before the first sync.
- **Redeploy a new build:** rebuild + push the image, then
  `az webapp restart` (App Service pulls the new `:latest`), or push a new tag and
  `az webapp config container set … --docker-custom-image-name …:<newtag>`.

---

## 10. CI/CD (optional) — GitHub Actions

The catch from §1 applies: **the dataset is not in git**, so a plain `checkout → build`
won't have the data. Pick one:

- **Simplest:** don't automate the image build. Build with `az acr build` from a machine
  that has the data (your laptop), and let CI only redeploy/restart.
- **Store data in Azure Blob** (or Git LFS): a workflow step downloads `data/raw/zendesk`
  into the checkout before `docker build`, then pushes to ACR and deploys. Sketch:

```yaml
name: deploy
on: { workflow_dispatch: {} }
jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with: { creds: ${{ secrets.AZURE_CREDENTIALS }} }
      - name: Fetch dataset from Blob        # data is not in git
        run: az storage blob download-batch -d data/raw -s dataset \
             --account-name ${{ secrets.DATA_STORAGE_ACCOUNT }}
      - name: Build & push to ACR
        run: az acr build -r ${{ secrets.ACR_NAME }} -t aiops:${{ github.sha }} -f Dockerfile.prod .
      - name: Point the web app at the new tag
        run: az webapp config container set -n ${{ secrets.APP_NAME }} -g ${{ secrets.RG }} \
             --docker-custom-image-name ${{ secrets.ACR_NAME }}.azurecr.io/aiops:${{ github.sha }}
```

Alternatively, mount the data from **Azure Files** at runtime instead of baking it into
the image (`az webapp config storage-account add …` and set `DATA_DIR` to the mount).
That decouples data from the image but adds a moving part; bundling is simpler for a demo.

---

## 11. Post-deploy checklist

- [ ] `curl $URL/api/health` returns `{"status":"ok"}`
- [ ] `curl $URL/` returns the app HTML (frontend served)
- [ ] "Sync data" succeeds in the UI (first call is slow — pipeline + model)
- [ ] A baseline question answers from reports (fast, no tool calls)
- [ ] An investigative question ("which client is driving load, and why?") runs a tool
- [ ] Only **one** instance is running (`az webapp show … --query 'siteConfig.numberOfWorkers'` → 1)
- [ ] `OPENAI_API_KEY` is set as a secret, not in the image or git
- [ ] HTTPS-only is on; the site redirects http→https

---

## 12. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| App Service shows "Application Error" | Container port mismatch | Set `WEBSITES_PORT=8000` (Step 4) and restart |
| Container starts then exits | Missing data in image | Confirm `.dockerignore` didn't exclude `data/`; rebuild where data exists |
| Copilot returns **503** | `OPENAI_API_KEY` not set/invalid | Set the App Setting; restart |
| First sync times out | Cold model training + big JSONL load | Bundle `sla_model.pkl` (`make train-sla`); use B2+; raise the startup time limit (`WEBSITES_CONTAINER_START_TIME_LIMIT=600`) |
| Chat "forgets" a sync | More than one instance | Scale to 1 worker / `min=max=1 replica`; enable Always On |
| Frontend 404s at `/` | Bundle not copied / mount missing | Confirm the §4.1 static mount and `COPY --from=frontend … ./web` |
| OOM during sync | Not enough RAM | B2→B3, or Container Apps `--memory 4.0Gi` |
| Huge image / slow build | No `.dockerignore` | Add §4.3 `.dockerignore` |

---

## 13. Teardown

```bash
az group delete -n "$RG" --yes --no-wait     # removes everything in the resource group
```

---

### Appendix — files this guide adds to the repo

| File | Purpose | Commit? |
|---|---|---|
| `backend/app/main.py` (edit) | Serve the frontend bundle in prod | yes |
| `Dockerfile.prod` | Multi-stage combined image | yes |
| `.dockerignore` | Lean build context | yes |
| `docker-compose.prod.yml` + `Caddyfile` | VM path only (Path C) | yes (optional) |
| OpenAI key | Runtime secret | **no** — App Setting / Key Vault only |
