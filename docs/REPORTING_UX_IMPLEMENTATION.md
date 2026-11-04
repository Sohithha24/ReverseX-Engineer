# Reporting UX Implementation

**Branch:** `ui/hackathon-redesign`  
**Date:** 2026-11-03  
**Depends on:** Evidence Verification Engine (`reversex/verification.py`)

---

## 1. Overview of changes

Added dual investigation reports that both consume the **same** `VerifiedResults` object:

| Layer | Addition |
|-------|----------|
| Backend | `reversex/reporting.py` — timeline narration, failure explanations, Markdown builders |
| API | `GET /human-report`, `GET /reports/simple.md`, `GET /reports/developer.md` |
| Frontend | Workspace **Reports** tab with Simple (default) / Developer views |
| Tests | `tests/test_reporting.py` |

Did **not** modify Muse, Playwright, reconstruction, validation, repair engines, or the verification rules themselves.

---

## 2. Simple Report

Default tab. Everyday language covering:

- Application / feature / status / outcome blurb  
- Timeline: What ReverseX did / What happened / What that shows  
- Verified discoveries only as established findings  
- Partially verified with limitations  
- Unverified/uncertain (unsupported, contradicted, needs review) — never as facts  
- How we know (readable evidence chain)  
- Recreation + test counts from recomputed validation summary  
- Failure cards when tests fail/invalid  
- Repair status (including Controlled Fault-Injection labeling)  
- Remaining uncertainties  

---

## 3. Developer Report

Same header + downloads. Expandable technical sections:

- Investigation metadata (id, mode, API request count, note)  
- Verification status legend  
- Same verified findings + other buckets  
- Contradictions & problems  
- Requirements / hypotheses  
- Reconstruction metadata  
- Validation original vs reconstruction states  
- Repair summary  
- Interactive React Flow EvidenceGraph  
- Optional raw `VerifiedResults` JSON (collapsed)  

---

## 4. Evidence verification integration

```
artifacts → build_verified_results() → VerifiedResults
                ↓
        build_report_package()
                ↓
     human-report JSON  +  simple.md  +  developer.md
                ↓
        ReportResultsView (both tabs)
```

Pass/fail counts and claim statuses come from verification — reports do not invent discoveries.

---

## 5. Plain-English investigation timeline

Built from recorded `investigation/report.json` events (`status=ok` only).

- Uses recorded `decision.reason` when present; never invents intent  
- Empty-submit detection uses observed validation text  
- Expandable technical dump per event  

---

## 6. Failure explanations

For each `fail` / `invalid` validation test:

| Field | Content |
|-------|---------|
| What we tested | Test description |
| Original | Summarized observed state |
| Reconstruction | Summarized observed state |
| Difference | Recorded `differences[]` |
| Why it matters | Reconstruction mismatch disclaimer — **not** “original is defective” |
| Repair | Attempted? / recorded outcome |

Invalid tests are explicitly “could not execute,” not behavioral fails.

---

## 7. Verification status presentation

| Backend status | UI label |
|----------------|----------|
| `verified` | Verified for tested behavior |
| `partially_verified` | Partially verified |
| `not_verified` | Not verified |
| `contradicted` | Conflicting evidence |
| `requires_review` | Needs review |

Short help text shown beside each badge. No confidence percentages.

---

## 8. EvidenceGraph changes

- Nontechnical: **How we know** chain on Simple Report  
- Developer: existing React Flow graph preserved under Reports → Developer and Workspace → EvidenceGraph  

No fabricated edges.

---

## 9. Downloadable reports

| Action | Endpoint |
|--------|----------|
| Download Simple Report | `GET /api/investigations/{id}/reports/simple.md` |
| Download Developer Report | `GET /api/investigations/{id}/reports/developer.md` |

Markdown, `Content-Disposition: attachment`, generated from the live job’s VerifiedResults + artifacts. No hardcoded TaskBoard/MiniCalc prose beyond display names derived from `target_id`.

---

## 10. Actual test results

```text
pytest: 104 passed, 2 skipped
frontend: tsc -b && vite build — success
```

Reporting tests cover: shared findings across MD exports, pass-count integrity, MiniCalc package when present, failure/invalid narration, timeline from recorded events, incomplete jobs, API human-report + downloads, invalid ids.

Manual UI check: deep link  
`http://127.0.0.1:5173/?job=69f0a4845ee347c8831d691aac18951a`  
→ Reports → Simple shows TaskBoard, 5/0/0, verified reload persistence, PostgreSQL claim as Not verified.

---

## 11. Screenshots

| File | Content |
|------|---------|
| `docs/ui-redesign-screenshots/08-simple-report.png` | Reports / Simple |
| `docs/ui-redesign-screenshots/09-developer-report.png` | Reports / Developer |

---

## 12. Remaining limitations

- Historical jobs without `final_report.json` still 404 after API restart (in-memory + disk final report convention unchanged)  
- Failed Muse investigation `9fb4d0b8…` has no validation suite — failure UI validated via unit fixtures + any job that has fail/invalid tests  
- Screenshots are matched loosely to timeline steps when filenames allow  
- Simple/Developer UIs are not separate routes; they are tabs inside Workspace → Reports  
- No push/merge performed  

---

## How to open

1. Ensure API is restarted after pulling these changes (`uvicorn reversex.api:app --host 127.0.0.1 --port 8000`).  
2. Frontend: `npm run dev -- --host 127.0.0.1 --port 5173`  
3. Open a completed job: `http://127.0.0.1:5173/?job=<32-hex-id>`  
4. Use **Reports** → Simple Report (default) or Developer Report; download via the header actions.  
