# ReverseX Engineer — UX Audit Fixes Report

**Branch:** `ui/hackathon-redesign`  
**Date:** 2026-11-03  
**Basis:** `docs/FIRST_TIME_USER_UX_AUDIT.md`  
**Scope:** Frontend UX / IA / copy only. No investigation/reconstruction/verification/repair algorithm changes. No custom URL capability. No git push.

---

## 1. Original audit findings (summary)

Critical / high issues from the first-time UX audit:

| # | Issue | Severity |
|---|--------|----------|
| 1 | Product implied general-purpose URL investigation | Critical |
| 2 | Explore Verified Demo opened empty EvidenceGraph | Critical |
| 3 | No history; Investigations/Results overlapped | Critical / High |
| 4 | Engineering Workspace jargon (FastAPI, `?job=`) | High |
| 5 | Controlled repair demo broken with loaded job | High |
| 6 | Six technical tabs exposed by default | High |
| 7 | Demo vs Live jargon for nontechnical users | Medium |
| 8 | Simple Report nested under engineering chrome | High |
| 9 | Hackathon branding + “Warm light workspace” | Medium |
| 10 | FastAPI field names beside Launch | Medium |

---

## 2. Issues fixed

| Area | Change |
|------|--------|
| Branding | Removed “Meta Global AI Developer Hackathon”; subtitle → **AI Software Investigation Platform** |
| Home | Honest product + scope copy; sample apps called out; **Start Investigation** / **Explore Completed Example** |
| Explore Completed Example | Loads a real completed job (candidate IDs) → **Simple Report**; fallback Guided Demo with reuse if none available |
| Setup | **Start an Investigation**; Sample applications; **Guided Demo** / **Fresh AI Investigation**; Advanced settings; no FastAPI field dump |
| Navigation | **Home / New Investigation / Current Investigation / Results** — no fake history list |
| Progress | Human stages Exploring → Discovering → Reconstructing → Testing → Preparing Results from real stage data |
| Results default | Completed runs and deep links land on Simple Report; auto-switch after busy→terminal |
| Developer tools | Collapsed by default; EvidenceGraph labeled **How We Know** |
| Controlled repair | Isolated `demoRepair` + dedicated view; does not overwrite job results |
| Persistence honesty | Empty states explain session/backend limitation; no permanent history claim |

---

## 3. Issues not fixed (or only partial)

| Issue | Status | Why |
|-------|--------|-----|
| Custom website URL investigation | **NOT FIXED** (intentional) | Backend only allows `taskboard` \| `calculator` |
| Permanent investigation history | **NOT FIXED** | No list API (`GET /api/investigations` → 405) |
| Simple Report “What happened” raw page dumps | **NOT FIXED** | Report content preserved per accuracy requirement |
| Genuine sample app preview screenshots on Setup | **NOT FIXED** | No approved productized preview assets; avoided fabricating mocks |
| Full WCAG certification | **NOT FIXED** | Out of scope; `:focus-visible` already in CSS |

---

## 4. Navigation before and after

| Before | After |
|--------|--------|
| Home | Home |
| New Investigation | New Investigation |
| Investigations (Live workspace, not a list) | **Current Investigation** (Progress + developer tools) |
| Results (Reports tab) | Results (Simple Report default) |
| Six always-visible workspace tabs | Results \| Progress; developer tools collapsed |

---

## 5. New Investigation before and after

| Before | After |
|--------|--------|
| “Investigation setup” + FastAPI field names | **Start an Investigation** + plain helper text |
| Demonstration targets / Kanban jargon | **Sample applications** with behavior-focused blurbs |
| Demo Mode / Live AI Mode | **Guided Demo** / **Fresh AI Investigation** |
| Advanced options always mentioning API schema | **Advanced settings** without request-field dump |

---

## 6. Demo entry behavior

**Before:** Explore a Verified Demo → EvidenceGraph tab → often “No evidence graph loaded yet.”

**After:** Explore Completed Example:

1. Tries known completed job IDs still served by the backend.
2. On success: sets `?job=…`, opens workspace **Results**, loads Simple Report (VerifiedResults / human-report).
3. If none available: starts Guided Demo (`scripted` + `reuse_reconstruction` for TaskBoard) and shows Progress until complete, then Results.
4. On hard failure: honest error on Home with Guided Demo guidance.

**Browser evidence:** Job `69f0a4845ee347c8831d691aac18951a` opened with TaskBoard Simple Report (5/5, 100%). Screenshot: `docs/ux-fix-screenshots/02-explore-completed-simple-report.png`.

---

## 7. Report entry behavior

- Deep link `?job=` → Results / Simple Report (unchanged contract, clearer chrome).
- Investigation completion (busy → terminal) → auto-navigate to Results.
- Downloads: Simple + Developer markdown endpoints still **HTTP 200** for the test job.

---

## 8. Developer tooling access

Path: **Current Investigation → Progress → Developer tools → Show**

Tools:

- Browser & events  
- Reconstruction  
- Validation details  
- **How We Know** (React Flow graph retained)  
- Repair details  

Screenshot: `docs/ux-fix-screenshots/05-developer-tools-how-we-know.png`.

---

## 9. Controlled repair behavior

**Before:** With a job loaded, Controlled repair demo often still showed “No repair results for this job” (job repair 404 raced with demo payload in one state).

**After:**

- `demoRepair` is separate from job `repair`.
- Opening the example shows a dedicated **Controlled Repair Example** screen with deliberate-fault labeling.
- Job Simple Report remains intact via **Back to investigation results**.

Browser evidence: 60% → 100%, `calc_addition` / `calc_negative`; job results still present after return. Screenshot: `03-controlled-repair-isolated.png`.

---

## 10. Actual browser tests

Performed against `http://127.0.0.1:5173` + API `8000`:

| Journey | Result |
|---------|--------|
| Home honesty (samples, no custom URL claim, no hackathon) | Pass |
| Explore Completed Example → Simple Report | Pass |
| Downloads endpoints 200 | Pass |
| New Investigation copy / Guided vs Fresh AI | Pass |
| Current Investigation progress + View results | Pass |
| Developer tools → How We Know | Pass |
| Controlled Repair Example with loaded job + back | Pass |
| Deep link `?job=` | Pass (brief empty flash until poll finishes — residual) |

No paid Meta investigation launched during this verification.

---

## 11. Regression results

| Check | Result |
|-------|--------|
| `python -m pytest` | **104 passed, 2 skipped** |
| Frontend `tsc -b && vite build` | **Pass** |
| Verification / reporting backend | Untouched; tests green |

---

## 12. Screenshots

| File | Content |
|------|---------|
| `docs/ux-fix-screenshots/01-home-honest.png` | Honest home + product subtitle |
| `docs/ux-fix-screenshots/02-explore-completed-simple-report.png` | Completed example → Results |
| `docs/ux-fix-screenshots/03-controlled-repair-isolated.png` | Controlled repair separate from job |
| `docs/ux-fix-screenshots/04-current-investigation-progress.png` | Human progress stages |
| `docs/ux-fix-screenshots/05-developer-tools-how-we-know.png` | Progressive disclosure + How We Know |

---

## 13. Remaining limitations

- Only TaskBoard and MiniCalc are investigable.
- No browsable permanent job history.
- Deep-link / Explore may show a short empty Results state while artifacts load.
- Simple Report timeline still includes verbose page-text observations (content preserved on purpose).
- Guided Demo fallback still depends on local targets + Docker/validation stack when no prior job is available.

---

## Critical / high issue status matrix

| Original issue | Status | Evidence |
|----------------|--------|----------|
| No custom URL / oversold generality | **FIXED** (framing) | Home + Setup copy; capability unchanged |
| Explore demo empty EvidenceGraph | **FIXED** | Loads real job Simple Report |
| No history; Investigations/Results overlap | **PARTIALLY FIXED** | Nav renamed/clarified; history still not implemented |
| Engineering jargon shell | **FIXED** | Results/Progress product chrome |
| Controlled repair vs loaded job | **FIXED** | Isolated demo state + dedicated view |
| Six tabs up front | **FIXED** | Results/Progress + collapsed developer tools |
| Demo/Live clarity | **FIXED** | Guided Demo / Fresh AI Investigation |
| Hackathon branding | **FIXED** | Removed from shell |
| FastAPI fields beside Launch | **FIXED** | Removed from Setup |

---

## Files touched

- `frontend/src/App.tsx`
- `frontend/src/components/ui.tsx`
- `frontend/src/components/RepairPanel.tsx`
- `frontend/src/hooks/useInvestigation.ts`
- `frontend/src/pages/OverviewPage.tsx`
- `frontend/src/pages/SetupPage.tsx`
- `frontend/src/pages/WorkspacePage.tsx`
- `docs/UX_AUDIT_FIXES_REPORT.md` (this file)
- `docs/ux-fix-screenshots/*`
