# IT-Tools Muse Baseline Evaluation

**Date:** 2026-11-04  
**Branch:** `ui/hackathon-redesign`  
**Evaluator role:** Independent AI systems evaluation  
**Engine modifications during baseline:** **None** (SafeBrowser / Muse / investigation loop unchanged)  
**Reconstruction:** **Not requested / not generated**  
**Automatic retry of paid investigation:** **Not performed**  
**Prior compatibility context:** `docs/IT_TOOLS_COMPATIBILITY_REPORT.md`

Evidence: `docs/audit-evidence-it-tools-muse/`, `artifacts/c8a559ebbe9543bbaf8eca532dec50f1/`

---

## Prerequisites (Part 1)

| Check | Result |
|-------|--------|
| IT-Tools `http://127.0.0.1:8010/base64-string-converter` | HTTP 200; container `reversex-it-tools` up |
| FastAPI `:8000` health | `ok`; targets include `it-tools` |
| React `:5173` | HTTP 200 |
| Target resolve for Base64 URL | Approved → `it-tools` |
| Public URL rejection | `https://example.com/` rejected |
| Muse credentials via existing `.env` | Present (`MODEL_API_KEY` / model config); **not printed** |

No prerequisite blocker.

---

## 1. Exact investigation configuration

| Field | Value |
|-------|-------|
| Target id | `it-tools` |
| Starting URL | `http://127.0.0.1:8010/base64-string-converter` |
| Feature | Base64 text encoding and decoding |
| Goal | `understand` |
| Mode | `muse` (Fresh AI / Meta Muse Spark) |
| Pipeline | `investigate_only` |
| Max actions | 12 |
| Guided Demo / scripted | **Not used** |
| Hardcoded selectors / app scripts | **Not used** |

---

## 2. Investigation ID

**`c8a559ebbe9543bbaf8eca532dec50f1`**

- Queued: `2026-11-04T06:12:52.775933+00:00`
- Updated: `2026-11-04T06:13:14.481016+00:00`
- Duration (investigation stage): **21.4 s**
- Final job status: **`failed`**
- Stage investigation status: **`error`**

---

## 3. Actual Muse API calls

**`meta_api_requests_total` / `api_request_count` = 2**

| Call | Outcome |
|------|---------|
| 1 | Returned a valid decision → fill executed |
| 2 | Investigation recorded `error`: `Expecting value: line 1 column 1 (char 0)` (empty/non-JSON content path in Meta response parsing) |

No further Meta calls. No full-job retry.

---

## 4–6. Recorded browser actions / success / failure

### Step 1 — **ok**

```json
{
  "action": "fill",
  "element_id": "s1_e4",
  "value": "Hello World",
  "reason": "Test Base64 encoding by entering sample text into string-to-encode field"
}
```

- Control labels available to Muse included:  
  `Put your string here...`, `The base64 encoding of your string will be here`, `Your base64 string...`, `The decoded string will be here`, Copy buttons.
- Fill targeted the encode **input** textarea (`Put your string here...`) — correct control for encoding intent.
- `before.visible_text` length 2000; `after.visible_text` length 2000; **`before == after`**.
- Neither `Hello World` nor Base64 `SGVsbG8…` appears in recorded `visible_text`.
- Objectives: `feature_controls_observed` supported; `feature_interaction_attempted` supported; **`page_response_observed` unsupported**.

### Step 2 — **error** (no Decision executed)

- No action/element_id/value.
- Error string: JSON parse failure on Meta decision content (`Expecting value: line 1 column 1 (char 0)`).
- Investigation aborted (`status: error` / job `failed`).

### Screenshot evidence (not in visible_text)

`investigation/final.png` (copied to `docs/audit-evidence-it-tools-muse/final.png`) shows:

- Input textarea: **Hello World**
- Output textarea: **`SGVsbG8gV29ybGQ=`** (correct Base64 for `Hello World`)

Evaluator-controlled Playwright (post-investigation, not fed to Muse) confirmed the same: textarea values update; **`body.inner_text()` still does not contain the Base64 string**.

---

## 7. Observed behavior (what Muse / ReverseX could establish from artifacts)

**From recorded snapshots + decisions (evidence-backed):**

- Started on the Base64 string converter route (configured URL).
- Muse identified encode/decode-related textareas by placeholder labels.
- Muse chose to fill the encode input with `Hello World`.
- Interactive controls for the feature were present.
- Reconstruction was not requested (Understand).

**From screenshots / evaluator browser (not available to Muse as structured observation):**

- Encoding occurred reactively after the fill.
- Output Base64 was visible in the UI.

**Muse did not (in this run):**

- Observe encoded output in `visible_text`.
- Attempt decode / invalid Base64 / empty input / URL-safe toggle.
- Stop deliberately with a completion reason (aborted on API parse error).
- Record a second successful browser action.

---

## 8. Missing browser evidence

| Needed for Base64 understanding | Present in Muse observations? |
|---------------------------------|-------------------------------|
| Input textarea **value** after fill | **No** (not in `visible_text`; only in decision `value` for the filled field) |
| Output textarea **value** after encode | **No** |
| Visible-text delta proving encode | **No** (`before == after`) |
| Decode path exercise | **No** |
| Error messaging for invalid Base64 | **No** |
| Structured element values in snapshot schema | **No** (labels/placeholders only) |

Known pre-baseline limitations **confirmed in vivo**:

1. Anchor-link navigation not required here (deep URL start) — limitation dormant for this run.
2. **`visible_text` omits textarea values** — **actively blocked output observation**.

---

## 9. Verified findings (shared VerifiedResults)

1. Investigation mode was recorded as muse.  
2. A form field (“Put your string here...”) was filled with “Hello World”.  
3. Interactive controls for the investigated feature were visible.  
4. An interaction with a visible control was recorded.  
5. Reconstruction was not requested.

**No verified finding** that Base64 output appeared or that encoding semantics were observed.

---

## 10. Unsupported conclusions

- Reports did **not** claim a verified Base64 output string.
- No TaskBoard / MiniCalc / ContactPad template leakage observed in verified/unsupported buckets.
- Untested list was generic (appropriate for non-fixture custom target).
- Muse’s fill **reason** implies encoding intent; that prose is **not** treated as proof of observed encoding.

---

## 11. Simple Report accuracy

**Generally accurate and appropriately cautious.**

- Correct app/feature/status (`failed`).
- Describes the fill action and Muse’s recorded purpose.
- Verified discoveries match evidence (fill + controls + mode + recon skip).
- Does **not** invent that encoding output was observed.
- Outcome states investigation did not complete successfully.
- Timeline only includes the successful step (step 2 error is thin in narrative — Developer/final_report carry the failure more clearly).
- “What happened” excerpt is sidebar chrome (truncation), not the encode result — honest relative to `visible_text`, but unhelpful for Base64.

---

## 12. Developer Report accuracy

**Accurate and evidence-aligned with Simple Report (shared VerifiedResults).**

- Mode muse, 2 API requests, failed status.
- Same verified claims with artifact locations.
- Timeline notes fill; does not fabricate decode/encode results.
- Notes specification/validation unavailable.
- Does not leak unrelated sample-app findings.

Gap: step-2 Meta parse error is easy to miss if readers only skim verified findings (status=failed is the signal).

---

## 13. Overall outcome — classification

### **B. Partially successful**

**Rationale (evidence-based):**

- **Successes:** Muse opened the correct feature URL context; identified Base64-related textareas; selected a sensible encode-input fill; browser actually performed encoding (screenshot).
- **Gaps:** Structured observations never captured output values; `page_response_observed` unsupported; investigation **failed** on the second Meta call before further exploration or a deliberate stop; encoding behavior was **not** independently established in VerifiedResults.

Not **A**: meaningful encode/decode behavior was not independently observed in recorded browser text.  
Not pure **C**: the feature was located and interacted with; a real fill occurred on the right control.

---

## 14. General-purpose engine limitations (not IT-Tools-only)

| Limitation | Generality |
|------------|------------|
| `visible_text` from `body.inner_text` omits many controlled **textarea/input values** | Affects reactive forms, calculators-in-textareas, chat boxes, converters |
| No snapshot fields for element **current values** | Generic observation gap |
| Cannot click ordinary `<a>` / router links | Affects multi-page SPAs and tool catalogs (mitigated here by deep URL) |
| Search/modals often need click-then-fill sequences with unlabeled buttons | Common SPA pattern |
| Toggle switches / custom widgets outside button/input/textarea/select | Generic |
| Muse loop aborts on empty/non-JSON Meta `content` without recovery | Integration robustness (paid call already consumed) |
| Max 40 discoverable controls; many empty-label buttons can crowd snapshots | Generic dense UIs |
| Independent validation only for configured fixture suites | Custom third-party apps |

IT-Tools-specific: Base64 happens to put critical results in textarea values with little duplication into surrounding text — so the generic textarea-value gap is **especially damaging** here.

---

## 15. Recommended improvements (do not implement in this baseline)

1. **Record input/textarea current values** in snapshots (or a safe value excerpt), so encode/decode outputs are observable without trusting Muse prose.  
2. Optionally include **value deltas** in event observations after fill/click.  
3. Support **link/role-based navigation** carefully under origin allowlist (or document deep URLs as required).  
4. Harden Muse response handling for empty `content` / missing `parsed` (fail soft, retry once, or stop with explicit “model returned empty decision”).  
5. Surface **failed decision steps** clearly in Simple Report timeline.  
6. Only after observation quality improves: attempt Understand→Reconstruct evaluations with private holdouts (`docs/IT_TOOLS_HOLDOUT_PLAN.md`).

---

## Answers to evaluation questions (concise)

1. **Did Muse successfully investigate IT-Tools?** Partially — one good fill, then aborted; encoding not verified in observations.  
2. **Did it find the Base64 feature?** Yes (started on tool page; identified encode/decode textareas).  
3. **Did it enter inputs?** Yes — `Hello World` into “Put your string here...”.  
4. **Could it observe outputs?** **No** via `visible_text`; screenshot shows output existed.  
5. **What did it genuinely learn?** That Base64 UI exposes labeled textareas and accepted a fill on the encode input; mode muse; Understand skipped recon.  
6. **What could it not determine?** The encoded result, decode behavior, empty/invalid cases, URL-safe mode, or that the page changed after fill.  
7. **Were reports accurate?** Yes — they match recorded evidence and do not invent outputs; failure status correct.  
8. **What needs fixing before reconstruction is meaningful?** Structured capture of textarea/input values (and preferably navigation beyond buttons); reliable multi-step Muse decisions; then observation-backed specs. Without seeing outputs, a reconstruction would be guessing.

---

*Baseline complete. One paid Muse investigation. No engine changes. No reconstruction. No push.*
