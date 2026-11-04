# ReverseX Engineer — Hackathon Release Checklist

Updated for release readiness **2026-11-04** (local verification). Checkboxes reflect actual runs on this machine.

## GitHub repository review

- [ ] Confirm remote URL and that intended branch contains all demo work
- [ ] Keep repository **PRIVATE** until hackathon rules require public
- [ ] Hackathon portal submission links filed
- [ ] **Commit** all intended product/docs changes on `ui/hackathon-redesign` (or merge to `main`) before push — large uncommitted set was present at readiness time

## Credential scan

- [x] `.gitignore` preserves `.env`, `artifacts/**`, `.venv/`, `node_modules/`
- [x] Working `.env` / `frontend/.env` ignored (`git check-ignore`)
- [x] Tracked env templates only: `.env.example`, `frontend/.env.example` (empty `MODEL_API_KEY=`)
- [x] `scripts/scan_staged_secrets.py` available — run **after staging**, before commit
- [x] Residual Docker bridge risk documented in README

## Regression tests (2026-11-04 readiness)

- [x] `pytest -q` → **149 passed, 2 skipped**
- [x] `frontend` `npm run build` → **passed**
- [x] API `GET /health` → `status=ok`
- [x] Playwright Chromium launches
- [x] Docker Desktop ready for validation

## Full demo workflow (zero Meta spend)

- [x] TaskBoard Guided Demo + Understand and reconstruct
- [x] Reconstruction reused
- [x] Independent validation with Docker isolation **running**
- [x] Oracle **5/5 (100%)** — job `8307f8d9aa304926b57f91de7171bc9a` status **completed**
- [x] Simple + Developer report endpoints return content
- [x] Saved investigations lists and reopens the job
- [ ] Optional: Fresh Muse investigation video (costs credits) — not required for Guided Demo path

## Frontend / local demo verification

- [x] Understand / Understand and reconstruct goals visible for sample + URL entry
- [x] Guided Demo vs Fresh AI Investigation clearly labeled
- [x] Controlled Repair Example remains labeled fault injection (60% → 100%)
- [x] Deep-link `?job=` and history Open work for finalized jobs

## Docker readiness

- [x] Docker Desktop running during readiness E2E
- [x] Validation isolation status `running` on release job
- [x] README states bridge fallback residual risk

## Demo video / portal

- [x] Script: `docs/DEMO_SCRIPT.md`
- [ ] Screen recording exported
- [ ] Video uploaded / linked for submission
- [ ] Final readiness summary: `docs/FINAL_RELEASE_READINESS.md`

## Push gate (do not skip)

Only push after:

1. Intentional `git add` of source/docs (never `.env` / raw job `artifacts/`)  
2. `python scripts/scan_staged_secrets.py` = clean  
3. pytest + frontend build green  
4. No force-push unless explicitly required  
5. Visibility unchanged unless intentionally required  

**No push was performed during automated readiness preparation.**
