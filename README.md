# ReverseX Engineer

**Solo project for the Meta Global AI Developer Hackathon — theme: Push the Frontier.**

ReverseX investigates an *authorized* local web application, freezes an evidence-backed behavioral specification, asks Meta Muse Spark to reconstruct the observed feature **without original source**, and independently validates observables with Playwright.

> This is a controlled hackathon prototype—not a general-purpose reverse-engineering product for arbitrary sites.

## Problem

Teams often need to understand unfamiliar UI behavior without trusting screenshots or manual notes. ReverseX turns authorized black-box interaction into:

1. recorded observations  
2. a frozen behavioral spec  
3. an independent reconstruction  
4. differential validation evidence  

## What is implemented

| Capability | Implemented | Independently tested | Notes |
|------------|-------------|----------------------|-------|
| Local Playwright investigation (scripted) | Yes | Yes | Deterministic smoke path |
| Meta Muse Spark investigation (httpx) | Yes | Yes (Phase 1B) | Live model decisions |
| Behavioral specification + freeze/checksum | Yes | Yes | Observation vs hypothesis |
| Muse reconstruction (`index.html`/`style.css`/`script.js`) | Yes | Structural + oracle tests | From frozen spec only |
| Docker-restricted reconstruction preview | Yes | Yes (Phase 3) | Bridge fallback may remain; not a perfect sandbox |
| Independent Playwright oracle validation | Yes | Yes | 5/5 on controlled TaskBoard fixture |
| EvidenceGraph from real artifacts | Yes | Yes | No invented edges |
| FastAPI orchestration API | Yes | Yes | Local-only, no auth |
| React + TypeScript workspace UI | Yes | Build + browser smoke | Vite app in `frontend/` |

### Demonstration results (controlled fixture)

On the authorized TaskBoard sample app:

- Phase 3 behavioral oracle: **5 valid tests passed**, match rate **100%** (one controlled app).
- Latest Phase 4B demo pipeline: **scripted** investigation + **reused** previously generated reconstruction (no fresh Muse reconstruction in that smoke path).
- Pytest (latest local run before GitHub packaging): **58 passed, 1 skipped**.

Do **not** interpret these results as proof that ReverseX reliably reconstructs arbitrary applications.

## Technology stack

- **Python 3.11+** / FastAPI / Pydantic / Playwright / httpx  
- **Meta Muse Spark 1.3** via Meta Model API (`https://api.meta.ai/v1`)  
- **Docker** (restricted nginx container for untrusted reconstruction preview)  
- **React + TypeScript + Vite** frontend  

## Architecture

```
sample_app (:8001)  →  oracle / original behavior
reversex/           →  investigate → specify → reconstruct → validate
artifacts/          →  local evidence (mostly gitignored)
frontend/           →  React UI polling FastAPI (:8000)
```

### Meta Muse Spark’s role

- Chooses browser actions during Muse-mode investigation (validated before execution).  
- Generates reconstruction files from a **frozen** behavioral specification.  
- Does **not** receive `sample_app` source, and does **not** decide pass/fail for validation.

### Autonomous browser investigation

Playwright runs against an allowlisted `127.0.0.1` origin with service workers blocked and off-origin requests aborted.

### Behavioral specification

Requirements are derived from recorded observations. Hypotheses (e.g. storage mechanism) are labeled separately and are not treated as hard requirements.

### AI-generated reconstruction

Produces only allowlisted static files under a job or demo folder. Output is size- and path-validated before write.

### Independent Playwright validation

Original app is the behavioral oracle. Holdout inputs are chosen at validation time and are not sent to Muse. Scores come from executable assertions, not the model.

### EvidenceGraph

Lightweight JSON graph linking investigation actions, requirements, reconstruction artifacts, and validation outcomes—built only from recorded files.

### React frontend

Local Vite app talks to FastAPI using `VITE_REVERSEX_API_BASE_URL`. Hosted Lovable/cloud previews cannot reach your localhost API without a secure deployment.

## Local development

### Backend

```powershell
cd reversex-engineer-starter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
# Set MODEL_API_KEY only when using Muse mode
```

Terminals:

```powershell
# A — original fixture
python -m http.server 8001 --bind 127.0.0.1 --directory sample_app

# B — API
python -m uvicorn reversex.api:app --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open `http://127.0.0.1:5173`.

Zero-Meta demo path: mode **scripted**, pipeline **full**, **reuse reconstruction** enabled.

## Docker requirements

Validation preview expects Docker Desktop. The reconstruction is served from a restricted container (read-only app mount, dropped capabilities, loopback bind). On some hosts, an **internal** network publish fails and the system falls back to **bridge** networking. Treat generated JS as untrusted; browser request filtering is still required. This is **not** a completely secure sandbox.

## Security limitations

- Local API has **no authentication** — do not expose publicly.  
- Target URLs are allowlisted to configured local origins.  
- API keys stay in backend `.env` (never committed; never sent to the frontend).  
- Screenshot endpoints only serve allowlisted PNGs under a job id.  
- Do not claim OS-level isolation for untrusted reconstruction code.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

## Repository contents vs local-only files

Committed:

- `reversex/`, `frontend/src/`, `sample_app/`, `tests/`, `docs/`, configs  
- `artifacts/demo/` — sanitized demo summary + reconstruction copy  

Gitignored (kept locally):

- `.env`, `.venv/`, `node_modules/`, `frontend/dist/`  
- Full `artifacts/` investigation dumps, screenshots, backups  

## Planned / not claimed

- Autonomous bounded repair loops  
- Multi-tenant auth / hosted public execution  
- Reliable reconstruction of arbitrary third-party apps  
- Perfect container isolation on all Docker Desktop configurations  
