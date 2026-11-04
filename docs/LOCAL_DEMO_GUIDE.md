# ReverseX Engineer — Local Demo Guide (Beginner)

This guide helps you run and operate the app that Cursor built. You do **not** need to understand every file to try it.

## 1. Exact URL to open

**Open this in your browser:**

### http://127.0.0.1:5173/

That is the React dashboard. The FastAPI backend is at `http://127.0.0.1:8000` (you usually do not open that directly except for health checks).

## 2. Required services

| Service | Port | Purpose |
|---------|------|---------|
| TaskBoard fixture | 8001 | Original app under test |
| MiniCalc fixture | 8003 | Second original app |
| ContactPad fixture (optional) | 8005 | Custom allowlisted form app |
| FastAPI backend | 8000 | Orchestration API |
| React frontend | 5173 | Dashboard UI |
| Docker Desktop | — | Needed for validation preview of reconstructions |
| Playwright Chromium | — | `python -m playwright install chromium` (once per machine) |

## 3. Exact start commands (PowerShell)

From the project folder:

```powershell
cd C:\Users\sohit\Downloads\ReverseX_Engineer_Phase1a_Starter\reversex-engineer-starter
```

**If services are already running, skip to step 4.** Check with:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:5173/ -UseBasicParsing | Select-Object StatusCode
```

**Start each in its own PowerShell window:**

```powershell
# Window A — TaskBoard
.\.venv\Scripts\python.exe -m http.server 8001 --bind 127.0.0.1 --directory sample_app
```

```powershell
# Window B — MiniCalc
.\.venv\Scripts\python.exe -m http.server 8003 --bind 127.0.0.1 --directory fixtures\calculator
```

```powershell
# Optional — ContactPad
.\.venv\Scripts\python.exe -m http.server 8005 --bind 127.0.0.1 --directory fixtures\contactpad
```

```powershell
# Window C — FastAPI
.\.venv\Scripts\python.exe -m uvicorn reversex.api:app --host 127.0.0.1 --port 8000
```

```powershell
# Window D — React
cd frontend
npm run dev
```

Start **Docker Desktop** before any full validation demo.  
If investigations fail at browser start, run: `.\.venv\Scripts\python.exe -m playwright install chromium`.

### Recommended zero-Meta demo (Understand and Reconstruct)

1. Open http://127.0.0.1:5173 → **New**.  
2. Select **TaskBoard**.  
3. Choose **Understand and reconstruct**.  
4. Choose **Guided Demo** (not Fresh AI Investigation).  
5. Advanced → ensure reconstruction reuse is enabled for TaskBoard.  
6. **Launch investigation** → wait for **completed**.  
7. Open **Results** → Simple Report + Developer Report → download both.  
8. Confirm the job appears under **Saved investigations**.

Details and submission gates: `docs/FINAL_RELEASE_READINESS.md`.

## 4. What each dashboard section means

| Section | Meaning |
|---------|---------|
| **Overview** | Landing page + backend health + demo loaders |
| **Workspace** | Where you configure and watch investigations |
| **Application** | TaskBoard or MiniCalc (authorized targets only) |
| **Mode** | `Scripted` = free offline smoke; `Live Muse` = spends Meta credits |
| **Pipeline** | `Full` = investigate → spec → reconstruct → validate; or investigate only |
| **Reuse reconstruction** | TaskBoard only: reuse prior Phase 2 files (no Muse reconstruct call) |
| **Live status** | Job lifecycle; look for `completed ← current` |
| **Recorded events** | Browser actions that ran |
| **Behavioral specification** | Whether a frozen spec exists for this job |
| **Validation results** | Independent oracle pass/fail (from backend) |
| **Repair results** | Bounded repair / controlled evaluation display |
| **EvidenceGraph** | Clickable map of evidence links |

## 5. How to select TaskBoard

1. Click **Workspace**.
2. Open **Application**.
3. Choose **TaskBoard**.
4. Origin should show `http://127.0.0.1:8001`.

## 6. How to select MiniCalc

1. **Application** → **MiniCalc**.
2. Origin should show `http://127.0.0.1:8003`.
3. “Reuse Phase 2 reconstruction” becomes **disabled** (correct).

## 7. How to start an investigation (safe first demo)

Recommended first run (**no Meta credits**):

1. Application: **TaskBoard**
2. Mode: **Scripted browser smoke test**
3. Pipeline: **Full**
4. Check: **Reuse existing Phase 2 reconstruction**
5. Click **Start investigation**

Watch **Live status** move: queued → investigating → … → **completed**.

## 8. How to identify real progress

- Status timeline updates (not stuck forever on `queued`).
- **Recorded events** fill with JSON steps.
- When finished: **Validation results** show tests with pass/fail pills.
- Job JSON includes `id`, `stages`, and `meta_api_requests_total`.

For a finished job you can also open:

`http://127.0.0.1:5173/?job=<32-char-hex-id>`

Example from a free scripted smoke test:

`http://127.0.0.1:5173/?job=7ae1600203bf4135aebf5fe9090afa24`

## 9. How to view Meta-selected actions

Only appear when Mode = **Live Muse Spark investigation**.

In **Recorded events**, each step shows `action`, `element_id`, `value`, `reason` chosen by Muse.

Scripted mode uses a fixed offline plan — useful for learning, **not** Muse decisions.

## 10. How to view reconstruction results

In Live status JSON / Results area:

- `reconstruction.status`: `reused` or `generated`
- Files live under `artifacts/<job-id>/reconstructed-app/`

UI shows reconstruction stage summary; files themselves are on disk.

## 11. How to interpret validation scores

| Field | Meaning |
|-------|---------|
| Passed | Valid tests where original ≈ reconstruction |
| Failed | Behavior mismatch |
| Invalid | Test could not run (infra / missing controls) |
| Match rate | Passed ÷ valid tests (invalids excluded) |

**100%** means all *valid* oracle tests matched — for that fixture and that run only.

## 12. How to navigate EvidenceGraph

1. Scroll to **EvidenceGraph**.
2. Click colored **nodes** or **edges**.
3. Detail pane shows type, description, evidence reference.

## 13. How to view controlled repair results

1. Go to **Overview**.
2. Click **Load Controlled Repair Evaluation**.
3. Open **Workspace** if needed.
4. Scroll to **Repair results**.

You should see a label that this is **fault injection**, not an organic Muse failure, plus before/after scores (historically **60% → 100%**).

## 14. What spends Meta credits

| Action | Spends Meta? |
|--------|----------------|
| Scripted mode | **No** |
| Reuse reconstruction | **No** |
| Live Muse investigation | **Yes** (per decide call) |
| Fresh Muse reconstruction | **Yes** |
| Bounded repair Muse call | **Yes** |
| Load Controlled Repair Evaluation (read saved report) | **No** |
| Viewing old `?job=` results | **No** |

## 15. Safe shutdown

Close the four PowerShell windows (Ctrl+C in each), or stop the processes listening on 8000/8001/8003/5173. Leave Docker running if you still need it for other work.

Do **not** delete `artifacts/` — those are your local evidence.

## 16. Scripted vs Muse

| | Scripted | Muse |
|--|----------|------|
| Cost | Free | Uses API key / credits |
| Actions | Fixed offline plan | Model-chosen |
| Good for | Learning UI + pipeline | Real AI demo |

## 17. Reused vs fresh reconstruction

| | Reused | Fresh |
|--|--------|-------|
| When | TaskBoard + checkbox on | Unchecked, or MiniCalc |
| Meta reconstruct call | No | Yes |
| What you get | Prior Phase 2 files copied into job | New Muse-generated files |

## 18. Common errors and fixes

| Symptom | Fix |
|---------|-----|
| Frontend loads but empty/errors | Confirm API at `:8000` (`/health`) |
| `409` / only one investigation | Wait for current job to finish |
| Validation blocked / Docker | Start Docker Desktop; retry later |
| MiniCalc can’t reuse Phase 2 | Expected — TaskBoard-only reuse |
| CORS / wrong API | `frontend/.env` must be `VITE_REVERSEX_API_BASE_URL=http://127.0.0.1:8000` then restart `npm run dev` |
| Port already in use | Reuse healthy service; don’t kill unrelated apps |

## 19. MiniCalc demonstration (after TaskBoard)

1. Select **MiniCalc**.
2. Prefer viewing an existing completed job first (no Meta):  
   `http://127.0.0.1:5173/?job=5b4a5d5ccd2c41a5b16e33fefd6bdcac`
3. Only start a new Muse MiniCalc run when you are ready to spend credits.

## 20. Recommended click order (first session)

1. Open **http://127.0.0.1:5173/**
2. Click **Workspace**
3. Confirm **TaskBoard** is selected
4. Confirm Mode = **Scripted**, Reuse = **checked**
5. Optionally click **Start investigation** OR open  
   `http://127.0.0.1:5173/?job=7ae1600203bf4135aebf5fe9090afa24`
6. Scroll validation + EvidenceGraph
7. Overview → **Load Controlled Repair Evaluation** → see Repair results
