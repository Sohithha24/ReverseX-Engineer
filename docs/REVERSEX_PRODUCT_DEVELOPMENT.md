# ReverseX Product Development (Living Document)

**Branch:** `ui/hackathon-redesign`  
**Updated:** 2026-11-04 (release readiness)  
**Owner role:** Full-stack product engineering (local development)  
**Release doc:** `docs/FINAL_RELEASE_READINESS.md` — TaskBoard E2E with Docker validation **completed** (`8307f8d9…`, 5/5)

---

## Product vision

ReverseX Engineer is an AI software investigation and engineering platform that helps authorized users:

1. Understand how software features behave from browser observations.
2. Reconstruct selected features from observable behavior (when requested).
3. Independently verify reconstructions.
4. Explain differences with evidence-backed reports.
5. Diagnose defects only when an independent correctness oracle exists.
6. Repair generated implementations under bounded rules.
7. (Future) Propose reviewable patches for authorized original source.

It must remain approachable for nontechnical users and trustworthy for developers: no fabricated scores, no silent guesswork, no unauthorized public-web investigation.

---

## Existing capabilities (implemented & tested)

| Area | Status | Notes |
|------|--------|-------|
| Allowlisted local targets (TaskBoard, MiniCalc, ContactPad, IT-Tools) | **Implemented / tested** | Origin + port restrictions; public URLs rejected |
| Muse Spark investigation loop | **Implemented / partially reliable** | Structured `response_format` + recovery hardened 2026-11-04 |
| Scripted / Guided Demo | **Implemented / tested** | Offline browser smoke without Meta |
| Browser observation (values, control_changes, privacy redaction, same-origin links) | **Implemented / tested** | Lab + IT-Tools local tests; live Muse proof still pending |
| Understand-only pipeline | **Implemented / tested** | ContactPad Muse evidence + reporting |
| Reconstruction + fixture validation (TaskBoard/MiniCalc) | **Implemented / tested** | Suite-specific oracles |
| Bounded reconstruction repair | **Implemented / tested** | Controlled fault-injection path |
| Simple + Developer reports + VerifiedResults | **Implemented / tested** | Shared findings; failure problems now surfaced |
| EvidenceGraph | **Implemented / tested** | Demo + job artifacts |
| Durable job reopen by id | **Implemented / tested** | `final_report.json` survives API restart |
| Investigation history list | **Implemented / tested (API + UI)** | `GET /api/investigations` + Saved investigations panel |
| Generic validation for arbitrary apps | **Not implemented** | Still fixture-suite oriented |
| Original-application defect diagnosis | **Not implemented** | Requires independent oracle |
| Original-source repair | **Not implemented** | Explicitly future / authorization-gated |
| Unlimited public website investigation | **Intentionally disallowed** | Security boundary |

---

## Known limitations

1. Live Muse can still return empty or non-schema content; structured output is requested but ReverseX must defend parsers (embedded-JSON recovery + one bounded retry).
2. Observation hardening for textarea values is proven in local tests; the latest paid IT-Tools Muse run failed *before* actions, so live end-to-end proof is still pending authorization for another Muse eval.
3. Independent validation does not yet generalize beyond TaskBoard/MiniCalc suites.
4. In-progress jobs (no `final_report.json` yet) remain process-memory only.
5. Download/export packaging for entire investigation bundles is incomplete as a first-class UX.
6. Custom widgets outside standard controls remain hard to observe.

---

## Prioritized engineering backlog

### P0 — Reliability (current focus)

1. ~~Robust Muse decision parsing (prose+JSON, fences, retries, schema)~~ **Done 2026-11-04**
2. ~~Surface investigation failures in Simple/Developer reports~~ **Done 2026-11-04**
3. Bounded paid Muse re-evaluation of IT-Tools (needs approval; mocks first) — **Pending authorization**
4. Persist in-flight job state across API restart — open

### P1 — Real-world compatibility

1. Live Muse verification that control_changes / encoded outputs reach VerifiedResults
2. Improve exploration of dense SPAs without app-specific shortcuts
3. Clearer progress UX while Muse is deciding

### P2 — Reconstruction & verification

1. Generic behavioral comparison harness for allowlisted custom apps
2. Honest incomplete-evidence handling in reconstruction packaging
3. Separate mismatch vs original defect in product language (already started in reports)

### P3 — Product completeness

1. ~~Saved investigations list from disk~~ **Done 2026-11-04**
2. Bundle download (reports + screenshots + evidence)
3. Stronger first-run onboarding copy for unavailable capabilities

---

## Interaction audit (2026-11-04 later)

Full UI audit: `docs/FULL_PRODUCT_INTERACTION_AUDIT.md`.

- **Understand and Reconstruct** failed for users mainly because goal radios were hidden in sample-entry mode, and because Playwright Chromium was missing (startup_error).
- Fixed goal visibility + pipeline sync + ContactPad/IT-Tools validation honesty in `SetupPage.tsx`.
- Verified TaskBoard Guided reconstruct path (`ad67eaf…`) after Chromium install; validation still needs Docker.

---

## Changes implemented (this execution)

### Muse decision reliability (`reversex/meta.py`)

- Keep Meta Chat Completions `response_format: json_schema` (official structured output).
- Recover first balanced JSON object when Muse prepends prose (exact IT-Tools failure shape).
- Improve fence stripping; add `temperature: 0`.
- Append strict JSON output contract to system prompts.
- On bounded retry, send an explicit format-correction user message.
- `humanize_muse_error()` for nontechnical explanations.

### Reporting / verification

- `classify_problems` records Muse/startup investigation errors.
- Timeline includes error events.
- Simple Report adds **Why the investigation had problems**.

### Targets

- All Muse briefs include the JSON output contract.

### Investigation history

- `GET /api/investigations` merges memory + `artifacts/*/final_report.json`.
- Workspace **Saved investigations** panel opens durable jobs.

### Tests

- Prose-prefixed JSON recovery (IT-Tools shape)
- Format-correction retry payload
- Failed IT-Tools job report surfacing
- List investigations API
- Full suite: **148 passed, 3 skipped** (IT-Tools live browser check skips when Docker/:8010 is down)

---

## Tests performed

| Suite | Result |
|-------|--------|
| `pytest` (full) | Pass (148 / 3 skipped) |
| Frontend `tsc -b` + Vite build | Pass |
| Focused Muse/reporting | Pass |
| Live paid Muse | **Not run in this execution** (awaiting approval after mocks) |

---

## Actual results

- Root cause of IT-Tools second Muse abort class: model returned prose + JSON; parser rejected entire content → zero browser actions → reports hid the failure.
- Parser recovery + report surfacing + history listing are implemented and unit/integration tested with mocks and saved artifacts.
- Observation layer remains ready; still needs a successful live Muse action sequence to prove end-to-end.

---

## Remaining blockers

1. **Authorization for another bounded paid Muse evaluation** on IT-Tools (or another allowlisted app) to prove live reliability after parser fixes.
2. Generic independent validation design for non-fixture apps.
3. Optional: durable persistence for *in-progress* jobs.

---

## Next development priorities

1. Request/run one bounded paid Muse Understand on IT-Tools max 12 actions after approval.
2. If live succeeds, evaluate VerifiedResults for encode/decode control_changes.
3. Design generic validation scenarios for allowlisted custom apps (no IT-Tools hardcoding).
4. Add investigation bundle download.
5. Persist queued/running job metadata across API restart.

---

*No GitHub push or merge. No production deploy. Secrets not exposed.*
