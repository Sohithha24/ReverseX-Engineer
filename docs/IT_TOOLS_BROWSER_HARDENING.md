# IT-Tools Browser Hardening Report

**Date:** 2026-11-04  
**Branch:** `ui/hackathon-redesign`  
**Baseline investigation:** `c8a559ebbe9543bbaf8eca532dec50f1`  
**Live Meta calls during this engineering work:** **None**  
**IT-Tools-specific hardcoded behavior:** **None**

Related: `docs/IT_TOOLS_MUSE_BASELINE.md`, `docs/IT_TOOLS_COMPATIBILITY_REPORT.md`

---

## 1. Original baseline failure

Muse started on the Base64 tool page, filled `Hello World` into the encode textarea, and the UI produced `SGVsbG8gV29ybGQ=` (visible in screenshots).

Structured observations did **not** include that output because snapshots only stored `body.inner_text` plus control **labels**, not control **values**.

The second Muse API response was empty/non-JSON (`Expecting value: line 1 column 1`), which aborted the job as `failed` after 2 API calls. Prior step 1 remained in `events`.

---

## 2. Confirmed root causes

| Issue | Root cause |
|-------|------------|
| Missing textarea outputs | `SafeBrowser.snapshot` never called `input_value()`; Vue-controlled values often absent from `inner_text` |
| Missing input values | Same — only labels/placeholders recorded on `VisibleElement` |
| Weak change detection | `page_response_observed` compared only `visible_text` equality |
| Second Muse failure | `json.loads(content)` on empty/`None` content; no typed error kinds; no bounded empty-content retry |
| Link starvation risk (found while fixing) | Adding all `a[href]` without prioritizing form controls can exceed the element cap before textareas appear |

Failure handling already preserved completed steps in `history` before `break`; diagnostics were too opaque.

---

## 3. Browser observation changes

`reversex/browser.py` + `reversex/contracts.py`:

- Extended `VisibleElement` with optional: `value`, `placeholder`, `role`, `input_type`, `disabled`, `readonly`, `checked`, `selected`, `href`, `value_redacted`
- Added `ControlValueChange` and `PageSnapshot.control_changes`
- Snapshot now reads current values for inputs/textareas/selects (with privacy rules)
- Form controls are collected **before** same-origin links so dense nav cannot starve observations
- After actions, snapshots compute structured control diffs vs the prior snapshot
- Short settle wait (150ms) after fill/click for reactive UIs (generic, not app-specific)

---

## 4. New structured observation fields

Per visible supported control (as applicable):

- `kind`, `label`, `placeholder`, `role`, `input_type`
- `value` (text inputs/textareas) or `selected` (select) or `checked` (checkbox/radio)
- `disabled`, `readonly`
- `href` (same-origin allowlisted anchors only)
- `value_redacted` when withheld

Per after-snapshot:

- `control_changes[]` with `field`, `before`, `after`, `label`, `kind`

Limits: max 48 elements, value length 200, visible_text 2000.

---

## 5. State-difference detection

`diff_control_values(before, after)` detects changes in `value` / `checked` / `selected` / `disabled` / `readonly`.

`evaluate_generic_feature_objectives` treats control-value changes as `page_response_observed`.

Evidence Verification emits `rule.observation_control_value_change` when recorded diffs (or derived element value diffs) exist — still requiring browser evidence, not Muse prose.

Reporting timeline prefers control-change summaries when present.

---

## 6. Security and privacy controls

- No capture for `password` / `hidden` / `file` input types
- Name/label/placeholder matching credential-like patterns → redact
- Value regex redaction for Bearer tokens / JWT-like / `sk-` secrets → `[REDACTED]`
- Refuse `fill` on credential-like controls
- Origin allowlist + request routing unchanged
- Link clicks require allowlisted destination origin; off-origin anchors omitted
- Website content remains untrusted data in Muse prompts
- Diagnostics sanitize unknown keys (no Authorization leakage)

**Remaining privacy limitation:** heuristic redaction cannot guarantee detection of all sensitive free-text fields (e.g. a custom “ssn” field with an innocuous name). Operators should keep investigations on approved local demos.

---

## 7. Muse response-handling improvements

`reversex/meta.py`:

- `MuseDecisionError` with `kind`: `empty_content`, `malformed_json`, `unexpected_response_structure`, `schema_invalid`, `http_error`, `transport_error`
- Robust extraction of `parsed` or `content` (including content-part lists)
- Schema validation via existing `Decision` model
- **Bounded retry:** at most **one** extra attempt for `empty_content` / `malformed_json` only (each attempt increments `request_count`)
- No retry for HTTP/transport/schema-invalid
- No fabricated decisions; no silent scripted fallback
- `run.py` records `error_kind` + sanitized `error_diagnostics` while keeping prior successful events

---

## 8. Link-navigation changes

Implemented **generic** same-origin allowlisted `<a href>` click support under existing `validate_target` rules.

Not implemented: SPA-only soft routing without href, role=link divs, or cross-origin navigation.

---

## 9. Actual browser test results (no Meta)

| Test | Result |
|------|--------|
| Observation lab reactive textarea capture | Pass |
| Password redaction / disabled / readonly | Pass |
| Select + checkbox state | Pass |
| Same-origin link click | Pass |
| IT-Tools Hello World → `SGVsbG8gV29ybGQ=` in structured values + control_changes | Pass (requires local :8010) |
| Generic objectives detect control changes | Pass |
| VerifiedFindings include control-value change | Pass |
| Muse mocked: valid / empty+retry / malformed / HTTP / schema / transport | Pass |

---

## 10. Regression results

| Suite | Result |
|-------|--------|
| Full `pytest` | **143 passed, 2 skipped** |
| Frontend `tsc -b` + production build | Pass |
| Skipped | Browser integration when port 8001 occupied / Chromium missing (pre-existing class); not forced green |

TaskBoard / MiniCalc / ContactPad paths remain covered by existing suites; allowlist still rejects public/unapproved URLs.

---

## 11. Remaining limitations

- Live Muse resilience against empty responses is improved but **not proven** until a new paid evaluation.
- Screenshots may still show values that older artifacts lack in JSON.
- Custom widgets without standard input/textarea/select/button/a semantics remain opaque.
- Toggle switches implemented as non-input widgets may still be missed.
- Observation size limits may omit deep-below-fold controls.

---

## 12. Ready for a fresh Muse evaluation?

**Yes — conditionally ready** for a second **Understand-only** live Muse evaluation on  
`http://127.0.0.1:8010/base64-string-converter`, expecting:

1. Structured capture of encode input/output textarea values  
2. Clearer incomplete/failed diagnostics if Meta returns empty content  
3. Prior successful steps preserved  

This document does **not** claim a new autonomous Muse run succeeded.

---

## Before vs after (engineering demonstration)

| Baseline (`c8a559…`) | After local tests |
|----------------------|-------------------|
| Output missing from structured observations | IT-Tools lab test captures `SGVsbG8gV29ybGQ=` in element `value` + `control_changes` |
| `visible_text` before==after after fill | Control diffs still detected when text unchanged |
| Empty Muse JSON crashed parse path | Typed `MuseDecisionError`; bounded retry; preserved history semantics |
| Security allowlist | Unchanged / still enforced |

---

*No GitHub push. No dashboard redesign. No reconstruction algorithm changes.*
