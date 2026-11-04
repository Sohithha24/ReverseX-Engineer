# Full Product Interaction Audit

**Date:** 2026-11-04  
**Branch:** `ui/hackathon-redesign`  
**Roles:** Lead QA automation, React/FastAPI engineer, first-time user  
**Frontend:** http://127.0.0.1:5173  
**Backend:** http://127.0.0.1:8000  
**Paid Muse calls during this audit:** **None**

Evidence: `docs/audit-evidence-interaction/`

---

## 1. Test environment

| Service | Status during audit |
|---------|---------------------|
| React Vite `:5173` | Running |
| FastAPI `:8000` | Running (restarted with current code) |
| TaskBoard `:8001` | HTTP 200 |
| MiniCalc `:8003` | HTTP 200 |
| ContactPad `:8005` | HTTP 200 |
| IT-Tools `:8010` | Down (Docker Desktop unavailable) |
| Playwright Chromium | **Missing at audit start** → installed mid-audit |
| Docker validation isolation | Unavailable |

---

## 2. Root cause — “Understand and Reconstruct not working”

Three stacked causes (not one):

### A. Critical UX (fixed)

Investigation goal radios lived **only inside “Use application URL” mode**. Choosing a sample card (TaskBoard/MiniCalc/…) hid the goal controls. Users selecting samples never saw **Understand and reconstruct**, so the product appeared to lack the feature.

### B. Critical runtime (environment; remediated)

Guided Demo / scripted launches failed at browser startup:

`BrowserType.launch: Executable doesn't exist … chromium_headless_shell-…`

So even when the goal mapped correctly (`investigation_goal=understand_and_reconstruct`, `pipeline=full`), reconstruction never ran because investigation aborted before actions. Fixed by `python -m playwright install chromium`.

### C. Honest limitation (not a false disable)

ContactPad / IT-Tools have **no independent validation oracle**. Reconstruction may still be requested; scoring is unavailable. UI previously under-explained this when the goal was hidden.

**After fixes:** TaskBoard Guided Demo with Understand and reconstruct succeeded through reconstruction (`ad67eaf32517432792e933bd815403e0`: investigation completed, reconstruction **reused**, validation **blocked** by Docker — status `incomplete`, not a silent Understand-only run).

---

## 3. Fixes implemented

1. **`SetupPage.tsx`** — Investigation goal always visible (URL + sample modes); selecting reconstruct forces `pipeline=full`; selecting Understand forces investigate-only messaging; ContactPad/IT-Tools get an honest “no fixture oracle” callout.
2. **`WorkspacePage.tsx`** — Progress empty-state copy updated (saved jobs / history).
3. **`meta.py`** — Clearer `startup_error` humanization (Playwright install hint).
4. **Environment** — Installed Playwright Chromium for this machine/sandbox.

No security weakenings. No paid Muse. No git push.

---

## 4. Control test matrix

Status legend: Working · Broken · Partially working · Correctly disabled · Misleading · Not testable

| Screen | Control | Expected | Actual | Status | Evidence |
|--------|---------|----------|--------|--------|----------|
| Home | Start Investigation | Open New setup | Opens setup | Working | Browser click |
| Home | Explore Completed Example | Open completed job reports | Loads completed TaskBoard example when candidates exist | Working | Job `69f0a484…` results UI |
| Home | Home / New / Current / Results nav | Switch views | Works | Working | Browser |
| Home | Diagnostics | Expand system status | Shows Backend online | Working | Browser |
| Home | Capability cards (Investigate/Reconstruct/Verify/Repair) | Informational | Not buttons | Working (non-interactive) | Snapshot — headings only |
| Home | Sample app text cards | Informational | Not clickable CTAs | Working (non-interactive) | Prefer New samples |
| New | Use application URL / sample toggle | Switch entry mode | Works | Working | Browser |
| New | URL + feature fields | Accept input | Works | Working | Browser |
| New | Check if URL is approved | Resolve allowlist | Works (approved/rejected) | Working | API + UI |
| New | Understand radio | Select understand-only | Works; forces investigate-only | Working | Browser + API |
| New | Understand and reconstruct | Select full pipeline goal | **Was hidden in sample mode → Fixed**; maps to `understand_and_reconstruct` + `full` | Working (after fix) | Before/after UI; job `ad67…` / `4c338…` |
| New | TaskBoard/MiniCalc/ContactPad/IT-Tools samples | Select target | Works; goal remains visible after fix | Working | Browser |
| New | Guided Demo | Scripted mode | Works when Chromium present | Working | Jobs above |
| New | Fresh AI Investigation | Muse mode | Selectable; **not launched** (no paid calls) | Not testable (live Muse) | UI only |
| New | Advanced Show/Hide | Reveal budget/pipeline/reuse | Works | Working | Browser |
| New | Action budget | Set max actions | Works | Working | Browser |
| New | Pipeline dropdown | Full vs investigate_only | Syncs with goal; disabled on Understand | Working | Browser |
| New | Reuse reconstruction checkbox | TaskBoard Guided Demo only | Correctly disabled for custom URL / live / non-reuse targets | Correctly disabled | Browser |
| New | Launch investigation | Create job with correct payload | Works after Chromium install | Working | API payloads |
| Current | Progress stages | Show exploring/etc. | Works for open job | Working | Job progress UI |
| Current | Technical event details | Expand | Works | Working | Browser |
| Current | Developer tools Show | Reveal live/recon/validation/graph/repair | Works | Working | Browser |
| Results | Simple / Developer tabs | Switch reports | Works | Working | Browser |
| Results | Download Simple/Developer | Fetch markdown for job | Links hit correct API (`200`) | Working | href + HTTP |
| Results | Technical event details / Supporting evidence expanders | Expand | Works | Working | Browser |
| Results | EvidenceGraph Zoom In/Out/Fit | Pan/zoom | Present and clickable | Working | Browser |
| Results | Saved investigations Open | Reopen job | Works; lists disk artifacts | Working | Browser list |
| Results | Controlled Repair Example | Isolated demo | Loads MiniCalc controlled repair; Back restores job | Working | Browser |
| Results | Back to investigation results / Close example | Exit demo | Works; job `69f0…` preserved | Working | Browser |
| Global | Deep link `?job=` | Open job | Works (after load settles) | Working | Browser |
| IT-Tools live | Any investigate | Requires :8010 | Not available this session | Not testable | Docker down |

---

## 5. End-to-end journeys

### Journey A — Understand (non-paid)

| App | Result |
|-----|--------|
| MiniCalc scripted Understand | Job `c6f251…`: `investigation_goal=understand`, reconstruction **skipped** with note; investigation `incomplete` because not all scripted objectives (subtraction/negatives) supported — honest incomplete, not silent reconstruct |
| ContactPad scripted Understand | Job `880ccd…`: recon skipped |

### Journey B — Understand and Reconstruct (non-paid)

| App | Result |
|-----|--------|
| TaskBoard Guided + reuse | Job `ad67eaf…`: goal/pipeline correct; investigation completed; reconstruction **reused**; validation **blocked** (no Docker); status `incomplete` |
| Pre-Chromium attempts | `4c338…`, `3d5b5…` failed startup_error (missing browser) |

### Journey C — Custom URL

URL check + goal selection verified in UI. Approved local origins only. Public URLs rejected by API (`400`).

### Journey D — Returning user

Deep link + Saved investigations Open + Simple/Developer switch + downloads verified for `69f0a484…`.

### Journey E — Controlled repair

Controlled Repair Example opens isolated MiniCalc fault-injection results (60%→100%). Back restores TaskBoard investigation results. Job id unchanged.

---

## 6. API contract checks

| Check | Result |
|-------|--------|
| `investigation_goal=understand` → pipeline investigate_only | Confirmed (`c6f251…`) |
| `investigation_goal=understand_and_reconstruct` → pipeline full | Confirmed (`ad67…`, `4c338…`) |
| Target resolve allowlist | Confirmed |
| Report markdown endpoints | `200` for simple + developer |
| History `GET /api/investigations` | Returns disk + memory jobs |
| No silent Understand when reconstruct selected | Confirmed on successful TaskBoard run |

---

## 7. Console / responsive

- No blocking console failures observed during successful Results/setup flows (a11y tree sometimes lagged behind paint; visual/DOM verified).
- Mobile viewport (390×844): New Investigation goal + ContactPad limitation callout remain readable (`mobile-setup-goal.png`).

---

## 8. Automated tests

| Suite | Result |
|-------|--------|
| Full `pytest` | **148 passed, 3 skipped** |
| Frontend `tsc -b` + Vite build | **Pass** |
| Live Muse | Not run (by design) |
| IT-Tools browser observation | Skipped (:8010 down) |

---

## 9. Remaining limitations / attention

1. Docker Desktop required for validation preview of reconstructions (otherwise validation blocked → job `incomplete`).
2. Playwright Chromium must be installed in each runtime environment.
3. Fresh AI / Muse reconstruct not re-proven live in this audit (no paid calls).
4. MiniCalc scripted Understand marks incomplete when optional objectives unsupported — expected, but Progress copy could be clearer.
5. IT-Tools not exercised live this session.
6. Capability cards on Home are not CTAs — acceptable if intentional; New Investigation remains the action path.
7. Download links open `.md` in-tab (no `download` attribute) — functional, could improve UX later.

---

## 10. Screenshots

| File | What it shows |
|------|----------------|
| `goal-selected-url-mode.png` | Understand and reconstruct selected |
| `results-taskboard-completed.png` | Completed example reports + downloads |
| `mobile-setup-goal.png` | Mobile goal + ContactPad limitation |
| `ad67-recon-job.json` | Successful reconstruct pipeline stages |

---

## 11. Product alignment verdict

ReverseX’s intended flow (authorized local apps → investigate → optional reconstruct → verify with evidence → reports) is **aligned after these fixes**, with honest limits for apps without validation oracles and for missing Docker/Playwright. The main user-facing “Understand and Reconstruct broken” report was primarily **goal UI hidden on sample path** plus **browser engine missing**, not a wrong backend mapping when the goal was actually selected.

---

*No GitHub push or merge. No secrets exposed. No paid Meta evaluation in this audit.*
