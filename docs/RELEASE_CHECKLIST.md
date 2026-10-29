# ReverseX Engineer — Hackathon Release Checklist

Evidence dated for Phase 6A prep (local machine). Update checkboxes only with actual verification.

## GitHub repository review

- [x] Remote exists: `https://github.com/Sohithha24/ReverseX-Engineer`
- [x] Default branch `main` tracks `origin/main`
- [x] Visibility remains **PRIVATE** (`gh repo view` → `isPrivate: true`) — do not flip public until submission rules require it
- [ ] Public visibility change (only if hackathon requires public repo) — **not done**
- [ ] Hackathon portal submission links filed — **not done**

## Credential scan

- [x] `.gitignore` preserves `.env`, `artifacts/**`, `.venv/`, `node_modules/`
- [x] Working `.env` / `frontend/.env` are ignored (`git check-ignore`)
- [x] Tracked env templates only: `.env.example`, `frontend/.env.example` (empty `MODEL_API_KEY=`)
- [x] No `.env` in git history as a committed secret file (only `.env.example` added in initial commit)
- [x] Pre-commit style scan: `scripts/scan_staged_secrets.py` available; run after staging
- [x] Residual Docker risk documented in README (bridge ≠ full sandbox)

## Regression tests

- [x] `pytest -q` → **71 passed, 1 skipped** (Phase 6A prep run)
- [x] `frontend` `npm run build` (`tsc -b && vite build`) → **passed**
- [x] API `GET /health` → `status=ok`, `phase=5c`, targets listed
- [x] `GET /api/targets` → `taskboard`, `calculator` only

## Frontend / local demo verification

- [x] TaskBoard in application selector
- [x] MiniCalc in application selector; origin switches to `:8003`; reuse disabled
- [x] Deep-link MiniCalc job shows `completed`, calc validation cards, EvidenceGraph sources
- [x] Validation data from backend (not hardcoded scores)
- [x] Screenshots listed for MiniCalc job (12 PNGs via API)
- [x] Controlled Repair Evaluation labeled; shows **60% → 100%**
- [x] `completed` / `incomplete` / `failed` remain distinct in timeline
- [ ] Full live Muse end-to-end re-run for video (optional; costs Meta credits) — **not required for checklist if prerecorded**

## Docker readiness

- [x] Docker used successfully in prior Phase 5B/5C validation (`isolation: running`)
- [ ] Confirm Docker Desktop running immediately before any live validation demo
- [x] README states bridge fallback residual risk

## Demo video

- [x] Script written: `docs/DEMO_SCRIPT.md` (≤3 minutes)
- [ ] Screen recording exported — **not done**
- [ ] Video uploaded / linked for submission — **not done**

## README

- [x] Updated for Phases 5B–5C (targets, repair, truthful limits)
- [x] Controlled repair clearly labeled as fault injection on a copy

## Final deadline / submission

- [ ] Confirm Meta hackathon deadline and required public/private state
- [ ] Attach demo video + repo URL in submission form
- [ ] Final private→public decision per event rules

## Push gate

Only push after:

1. Secrets scan on staged files = clean  
2. pytest + frontend build green  
3. No force-push  
4. Visibility unchanged unless intentionally required  
