# ReverseX Engineer

**Solo project for the Meta Global AI Developer Hackathon 2026 — theme: Push the Frontier.**

ReverseX investigates an *explicitly authorized* local web application with Meta Muse Spark, freezes an evidence-backed behavioral specification, reconstructs the observed feature **without original source**, validates behavior with an independent Playwright oracle, and can attempt **bounded** autonomous repair when the oracle finds mismatches.

> This is a controlled hackathon prototype—not a general-purpose reverse-engineering product for arbitrary sites. Two fixtures and a labeled fault-injection repair do **not** prove universal reconstruction.

## The engineering problem

Teams often need to understand unfamiliar UI behavior without trusting screenshots or manual notes—and without handing original source to a model. ReverseX turns authorized black-box interaction into:

1. Model-selected browser observations  
2. A frozen behavioral specification (observations vs hypotheses)  
3. An independent static reconstruction  
4. Differential oracle validation  
5. Optional bounded repair when validation fails  
6. An EvidenceGraph grounded in real artifacts  

## How Meta Muse Spark is used

| Stage | Muse role | Muse does **not** |
|-------|-----------|-------------------|
| Investigation | Selects allowlisted browser actions (`observe` / `click` / `fill` / `reload` / `stop`) | Execute actions without schema validation; leave the approved origin |
| Reconstruction | Generates `index.html` / `style.css` / `script.js` from a **frozen** spec | Receive original app source; score its own output |
| Repair | Receives failed oracle evidence + current recon; proposes a repaired candidate | Run unbounded retries; judge pass/fail |

All Meta calls use **httpx** against the Meta Model API (`muse-spark-1.3`). The OpenAI SDK is not used.

## What is implemented

| Capability | Status | Notes |
|------------|--------|-------|
| Autonomous Muse browser investigation | Yes | Allowlisted `127.0.0.1` origins only |
| Scripted offline smoke investigation | Yes | Deterministic; not AI-led |
| Behavioral specification + freeze/checksum | Yes | Observation vs hypothesis |
| Muse reconstruction (allowlisted files) | Yes | Spec-only context |
| Docker-restricted reconstruction preview | Yes | Bridge fallback possible; **not** a perfect sandbox |
| Independent Playwright oracle | Yes | Fresh holdouts; model does not score itself |
| EvidenceGraph | Yes | Built only from recorded artifacts |
| FastAPI orchestration | Yes | Local-only, **no auth** |
| React + TypeScript workspace | Yes | Target selector, validation, repair panel |
| TaskBoard + MiniCalc targets | Yes | `target_id`: `taskboard` \| `calculator` |
| ContactPad + IT-Tools allowlisted custom apps | Yes | Understand supported; independent validation only where a suite exists |
| Simple + Developer reports (shared VerifiedResults) | Yes | Downloadable markdown per job |
| Saved investigation history (disk-backed) | Yes | `GET /api/investigations` + Results panel |
| Bounded autonomous repair (max 2 attempts) | Yes | After real validation failures, or labeled controlled eval |

## Controlled evaluation results

### TaskBoard (authorized fixture on `:8001`)

- Fresh Muse investigation + fresh reconstruction (Phase 5A).  
- Independent oracle: **5/5** valid tests, **100%** match rate.

### MiniCalc (authorized fixture on `:8003`)

- Fresh Muse investigation + fresh reconstruction (Phase 5B).  
- Independent oracle: **5/5** valid tests, **100%** match rate.

### Controlled Repair Evaluation (Phase 5C) — labeled fault injection

We **intentionally** introduced a documented off-by-one defect into a **copy** of the MiniCalc reconstruction (original generated files left untouched). This is **not** an organically occurring Muse reconstruction failure.

| Metric | Value |
|--------|--------|
| Before repair | **60%** (3/5) |
| After repair | **100%** (5/5) |
| Muse repair API requests | **1** |
| Regressions in accepted candidate | None |

Do **not** interpret these results as proof that ReverseX reliably reconstructs or repairs arbitrary applications.

## Technology stack

- **Python 3.11+** / FastAPI / Pydantic / Playwright / httpx  
- **Meta Muse Spark 1.3** via Meta Model API  
- **Docker** (restricted nginx preview for untrusted reconstruction)  
- **React + TypeScript + Vite** frontend  

## System architecture

```
sample_app (:8001)           TaskBoard oracle / original
fixtures/calculator (:8003)  MiniCalc oracle / original
reversex/                    investigate → specify → reconstruct → validate → [repair]
artifacts/                   local evidence (mostly gitignored)
frontend/                    React UI → FastAPI (:8000)
```

Supported demo targets are **allowlisted** only (`taskboard`, `calculator`, `contactpad`, `it-tools` on approved local ports). Arbitrary public URLs are rejected.

### Autonomous browser investigation

Playwright runs against an approved `127.0.0.1` origin with service workers blocked and off-origin requests aborted. Element IDs come from the latest snapshot only.

### Behavioral specification

Requirements are derived from recorded observations. Hypotheses (e.g. storage mechanism) are labeled separately and are not hard requirements for reconstruction.

### Independent reconstruction

Produces only allowlisted static files. Output is size- and path-validated. Original fixture paths are never opened for model context.

### Oracle-based validation

The original application is the behavioral authority. Holdout inputs are chosen at validation time and are not sent to Muse during reconstruction. Invalid tests are not counted as passes.

### EvidenceGraph

Lightweight JSON graph linking investigation actions, requirements, reconstruction artifacts, validation outcomes, and (when present) repair attempts—no invented edges.

### Bounded autonomous repair

Runs only after differential validation failures (or a clearly labeled controlled evaluation). Max **2** Muse repair attempts. Candidates are versioned; a worse candidate never silently replaces the best. Fresh holdouts are used on revalidation.

### React frontend

Local Vite app at `http://127.0.0.1:5173` talks to FastAPI (`VITE_REVERSEX_API_BASE_URL`). Application selector, live status, events, validation, repair panel, EvidenceGraph, and `?job=` deep links.

## Installation and local setup

### Backend

```powershell
cd reversex-engineer-starter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
# Set MODEL_API_KEY only when using Muse mode — never commit the real key
```

Terminals:

```powershell
# A — TaskBoard fixture
python -m http.server 8001 --bind 127.0.0.1 --directory sample_app

# B — MiniCalc fixture
python -m http.server 8003 --bind 127.0.0.1 --directory fixtures/calculator

# Optional — ContactPad fixture
python -m http.server 8005 --bind 127.0.0.1 --directory fixtures/contactpad

# C — API
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

**Zero-Meta demonstration path (recommended for live demos):**

1. Start Docker Desktop (required for independent validation preview).  
2. New Investigation → **TaskBoard** → goal **Understand and reconstruct** → mode **Guided Demo**.  
3. Advanced settings: keep **Reuse existing reconstruction** enabled.  
4. Launch → wait for **completed** → open Results (Simple + Developer reports).  

Fresh AI Investigation spends Meta credits — use only when intentionally authorized.

## Docker requirements

Validation preview expects **Docker Desktop**. The reconstruction is served from a restricted container (read-only app mount, dropped capabilities, loopback bind). On some hosts, an **internal** network publish fails and the system falls back to **bridge** networking.

**Residual risk:** bridge networking may allow residual container outbound/DNS exposure. Treat generated JavaScript as untrusted. Browser request filtering remains required. This is **not** completely secure sandbox isolation.

## Automated testing

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

Latest local regression (release readiness 2026-11-04): **149 passed, 2 skipped**; frontend production build **passed**.  
Latest zero-Meta TaskBoard E2E with Docker validation: job `8307f8d9…` → **completed**, oracle **5/5 (100%)**. See `docs/FINAL_RELEASE_READINESS.md`.

## Security limitations

- Local API has **no authentication** — do not expose publicly.  
- Targets are allowlisted local origins only.  
- API keys stay in backend `.env` (gitignored; never sent to the frontend).  
- Screenshot endpoints only serve allowlisted PNGs under a job id.  
- Repair context excludes original fixture source fingerprints (code-enforced).  
- Do not claim OS-level isolation for untrusted reconstruction code.

## Repository contents vs local-only files

**Committed (source / docs):**

- `reversex/`, `frontend/src/`, `sample_app/`, `fixtures/calculator/`, `tests/`, `docs/`, configs  
- `artifacts/demo/` — sanitized demo summary when present  

**Gitignored (local):**

- `.env`, `.venv/`, `node_modules/`, `frontend/dist/`  
- Full `artifacts/` investigation dumps, screenshots, Phase 5* reports, repair candidates  

## Planned / not claimed

- Multi-tenant auth / hosted public execution  
- Unrestricted public URL investigation  
- Reliable reconstruction of arbitrary third-party apps  
- Perfect container isolation on all Docker Desktop configurations  
- Unlimited autonomous repair loops  

## Demo materials

- Three-minute talk track: [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md)  
- Release checklist: [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md)  
- Frontend API contract: [`docs/FRONTEND_API_CONTRACT.md`](docs/FRONTEND_API_CONTRACT.md)  
