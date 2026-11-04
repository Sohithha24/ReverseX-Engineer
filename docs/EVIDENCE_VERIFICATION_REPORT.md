# Evidence Verification Engine — Report

**Branch:** `ui/hackathon-redesign` (frontend redesign preserved; verification added in-place)  
**Module:** `reversex/verification.py`  
**Endpoint:** `GET /api/investigations/{id}/verified-findings`  
**Date:** 2026-11-03

---

## 1. Existing accuracy risks

Before this engine, ReverseX could present misleading conclusions because:

| Risk | Example |
|------|---------|
| Objective labels without re-checking predicates | `objectives.reload_persistence.supported=true` accepted at face value |
| Summary counts trusted blindly | `passed: 5` without recomputing from per-test `status` |
| Invalid tests confused with passes | `invalid` rows counted toward success narratives |
| Overgeneralization | One reload → “permanent storage”; five passes → “bug-free” / “fully equivalent” |
| Mode confusion | UI “Live AI” language vs recorded `mode: scripted` |
| Mismatch ≠ original defect | Failed reconstruction tests labeled as “app is broken” |
| Reference existence ≠ semantic support | Evidence path strings present while predicates fail |
| Repair success without revalidation | Status `perfect` with no `validation_artifact` / match rates |

There was **no** cross-artifact verification service. Closest pieces were objective evaluators, `assert_observations_have_evidence`, and the behavioral oracle — none produced a shared verified-results object for reporting.

---

## 2. New verification architecture

```
artifacts/{job}/
  investigation/report.json  ─┐
  specification/*.json       ─┤
  validation/*.json          ─┼─► load_artifact_bundle()
  reconstructed-app/*        ─┤         │
  repair/repair_report.json  ─┤         ▼
  final_report.json          ─┘  deterministic rule checks
                                      │
                                      ▼
                              VerifiedResults (shared)
                                      │
                    Simple Report ◄───┴───► Developer Report
                         (future)              (future)
```

- **No Meta / Muse calls** during verification  
- **No second evidence store** — reads existing job artifacts only  
- **No confidence scores** — statuses are discrete  
- **Path-confined** reads under `artifacts/{job_id}/`

---

## 3. Shared claim model

`VerifiedFinding` fields:

- `claim_id`, `investigation_id`, `target_application`, `feature_investigated`
- `claim_category`, `claim_text`
- `supporting_evidence[]`, `contradictory_evidence[]` (`EvidenceReference`)
- `verification_status`: `verified` | `partially_verified` | `not_verified` | `contradicted` | `requires_review`
- `verification_scope`, `limitations[]`
- `related_test_ids[]`, `timestamps[]`
- optional `problem_category`, `rule_id`

`VerifiedResults` partitions the **same** findings into buckets (not two competing conclusion sets) and adds contradictions, problems, untested behaviors, reconstruction/validation/repair summaries, and coverage limitations.

---

## 4. Supported verification rules

| Rule ID | Checks |
|---------|--------|
| `rule.reload_persistence` | Create observed + reload event + same task text visible after reload (via `evaluate_objectives` predicates) |
| `rule.validation_pass_count` | Recompute pass/fail/invalid from tests; invalid never counts as pass; optional asserted count |
| `rule.reconstruction_status` | Stage status vs files under `reconstructed-app/` |
| `rule.repair_outcome` | Success requires attempt status + revalidation metrics/artifact |
| `rule.investigation_mode` | Recorded mode; Muse-fresh claim contradicted by `scripted` / zero investigation API requests |
| `rule.reject_storage_*` / `rule.reject_universal_*` / `rule.reject_bug_free` | Explicitly **not verified** |
| `rule.reject_original_defect_without_oracle` | Original “broken” claims stay **not verified** without an independent oracle |

Typed proposed claims use `StructuredClaim.claim_type` — **not** free-form NLP keyword matching.

---

## 5. Unsupported claim types

Always rejected / not verified (by rule):

- PostgreSQL / storage-technology claims  
- Permanent multi-session persistence from one reload  
- Universal behavioral equivalence  
- “Completely bug-free” reconstruction  
- “Original application is defective” from reconstruction mismatch alone  

Unknown prose without a structured claim type → `requires_review` (not auto-verified).

---

## 6. Contradiction detection

Decidable from structured data:

- `final_report.stages.validation.passed` ≠ recomputed valid passes  
- Validation summary counts disagree with per-test statuses  
- Reconstruction `completed/reused/generated` but files missing  
- Repair success without revalidation evidence  
- Scripted investigation with investigation-level Meta API requests  

Ambiguous natural-language contradictions are **not** heuristically forced.

---

## 7. Scope checking

Every verified finding carries `verification_scope` + `limitations[]`. Defaults include:

- Single reload ≠ durable DB persistence  
- N passing tests ≠ all possible behaviors  
- Reconstruction file presence ≠ behavioral correctness  
- Controlled fault-injection ≠ organic Muse failure  

`untested_behaviors[]` lists known gaps for TaskBoard / MiniCalc.

---

## 8. Problem categories

| Category | When |
|----------|------|
| `reconstruction_mismatch` | Validation `fail` |
| `investigation_limitation` | incomplete / budget_exhausted |
| `validation_execution_failure` | `invalid` tests |
| `reconstruction_generation_failure` | recon stage error |
| `infrastructure_failure` | isolation/preview failure |
| `unverified_hypothesis` | frozen spec `kind=hypothesis` |
| `confirmed_original_defect` | **Never auto-assigned** from mismatch alone |

---

## 9. API integration

```http
GET /api/investigations/{job_id}/verified-findings
```

- Job id must match `^[a-f0-9]{32}$`  
- Job must exist (memory or `final_report.json`)  
- `404` when artifacts cannot produce findings (`availability=unavailable`)  
- Read-only; no secrets; relative evidence locations only  

---

## 10. Test results

```text
tests/test_verification.py  → 23 passed
full suite                   → 94 passed, 1 skipped
frontend npm run build       → success (tsc -b && vite build)
```

Coverage includes: supporting evidence, missing evidence, invalid refs, contradictory outcomes, wrong pass counts, overgeneralization, incomplete jobs, failed recon/validation, successful/unsuccessful repair, storage claims, scope limits, missing timestamps, empty test suites, Muse-vs-scripted contradiction, API happy/error paths.

---

## 11. Remaining limitations

- Does not interpret arbitrary natural-language report prose  
- Does not prove original-app defects without an external oracle  
- Calculator arithmetic correctness is still observational (UI change), not a math oracle  
- Timestamps are sparse when jobs omit them  
- Does not yet wire into Simple/Developer report UIs  

---

## 12. Recommendations for the reporting interface

1. Bind **both** Simple and Developer reports to `VerifiedResults` only.  
2. Simple Report: show `verified_findings` + plain-language `limitations` + avoid unsupported buckets.  
3. Developer Report: expose evidence refs, contradictions, problems, recomputed validation stats.  
4. Never display unsupported findings as green “verified”.  
5. Label controlled repair explicitly using `repair_summary.evaluation_kind`.  
6. Keep Meta out of verification and report assembly.

---

## Consolidated answers

1. **Can every verified claim be traced to actual evidence?**  
   Yes — verified findings require predicate-backed `supporting_evidence` refs into recorded artifacts.

2. **Does the engine verify evidence meaning rather than just reference existence?**  
   Yes — e.g. reload requires create + reload + post-reload visibility; pass counts are recomputed from test statuses.

3. **Can unsupported conclusions be identified?**  
   Yes — storage, universal equivalence, bug-free, and original-defect-without-oracle claims are explicitly `not_verified`.

4. **Can structured contradictions be detected?**  
   Yes — for decidable summary/stage/file/mode/repair mismatches.

5. **Can partially supported conclusions be distinguished?**  
   Yes — `partially_verified` vs `verified` vs `not_verified` / `contradicted` / `requires_review`.

6. **Are verification limitations explicitly reported?**  
   Yes — per-finding `limitations` + bundle `coverage_limitations` + `untested_behaviors`.

7. **Did existing functionality remain intact?**  
   Yes — investigation/reconstruction/repair/API flows unchanged; frontend redesign untouched; full pytest green; frontend build green.

8. **Actual regression results?**  
   **94 passed, 1 skipped**; frontend production build succeeded.

**This is a trustworthy evidence foundation, not a claim of universal factual accuracy.**
