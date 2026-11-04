# Second Real-User UX Audit — ReverseX Engineer

**Date:** 2026-11-04  
**Branch:** `ui/hackathon-redesign`  
**App under test:** http://127.0.0.1:5173 (backend http://127.0.0.1:8000)  
**Primary investigation under audit:** `fe8ef0266f9247638f69a23654d0ad5c` (ContactPad, Muse, Understand)  
**Method:** Real browser interaction (Cursor browser tools) + live API/artifact inspection. No application code was modified before this document.

**Classification key:** Confirmed bug · Verified usability issue · Missing capability · Hypothesis

---

## Stage 1 — Persona journey notes

### Persona A — Nontechnical small-business owner

| Step | Expected | Actual | Next action obvious? | Confusion / blockers | Completed? |
|------|----------|--------|----------------------|----------------------|------------|
| 1. Open ReverseX | Clear product home | Home loads; warm theme; backend eventually “online · phase 5c” | Yes | “phase 5c” is developer jargon on the landing page | Yes |
| 2. Understand platform | Plain explanation of what it does | Headline + Investigate/Reconstruct/Verify/Repair cards; allowlist warning present | Mostly | Pipeline marketed first; value for “my app’s feature” is secondary | Partial |
| 3. Supported apps | Clear list | TaskBoard, MiniCalc, ContactPad (+ allowlisted local URLs) | Yes | ContactPad card wording differs between Home and New Investigation | Yes |
| 4. Where to enter URL | Obvious URL field | On **New Investigation**, “Investigate your application” with URL box and samples | Yes after clicking New / Start Investigation | Home does not have a URL field; must leave Home | Yes |
| 5. Why public sites rejected | Clear rejection reason | Entering `https://example.com` → “Only http://127.0.0.1 URLs on approved ports are allowed” | Yes | Successful approval of `8005` is quieter than rejection (easy to miss) | Yes |
| 6. Purpose of samples | Know what each demo is for | Short blurbs on Home and sample cards | Yes | ContactPad “validation unavailable” is unexplained jargon | Partial |
| 7. Guided Demo vs Fresh AI | Know cost / behavior difference | Labels explain credits vs predefined path | Mostly | “Fresh AI Investigation” vs Results label “Fresh AI” / mode `muse` inconsistency | Partial |
| 8. Select application | Pick ContactPad or URL | Sample card or URL path works | Yes | — | Yes |
| 9. Describe feature | Clear feature box | Prefilled example for ContactPad; editable | Yes | — | Yes |
| 10. Start investigation | Clear launch | Launch investigation present; Muse path uses credits (not re-run this audit) | Yes | Advanced settings “Show” is cryptic | Yes (config); start not re-executed (no Meta spend) |
| 11. What ReverseX is doing | Plain progress | Progress: Exploring / Discovering / Preparing results | No | “Discovering” = skipped for Understand; sounds like failure | Partial |
| 12. Find results | Obvious Results | Results tab + View results | Yes once job loaded via `?job=` | Empty Results if no session job; deep link eventually hydrates | Partial |
| 13. Simple Report | Readable story of the feature | Timeline of fills/click/stop exists | Partial | Verified section only says mode=muse | Partial |
| 14. What AI discovered | Behavioral discoveries | Agent stop reason claims confirmation; verified list does not | No | User cannot tell observation vs verified fact | No (as verified discoveries) |
| 15. Succeeded vs failed | Clear outcome | Status Completed + Availability partial + empty test metrics | No | “partial” reads like incomplete success | No |
| 16. What was not tested | Feature-relevant unknowns | Task editing/deletion/PostgreSQL/TaskBoard unknowns | Misleading | Wrong app’s uncertainty list | No |
| 17. Supporting evidence | See screenshots / DOM | Timeline + How We Know + Developer tools | Partial | Evidence chain only for mode claim; confirmation not elevated | Partial |
| 18. Download report | Download buttons work | Download Simple / Developer Report buttons present | Yes | Content quality issue, not download wiring (not re-downloaded in this pass) | Assumed wired |

### Persona B — Software developer

| Step | Expected | Actual | Notes |
|------|----------|--------|-------|
| 1. Investigation configuration | Mode, goal, URL, feature | Progress shows App/Feature/Mode Fresh AI/URL; final_report has `investigate_only`, `understand` | Goal “Understand” less prominent on Results than mode |
| 2. Actual mode | muse vs guided | `mode=muse`, 5 API requests | OK |
| 3. AI actions | Decision log | 5 events: fill×3, click, stop with reasons | OK in timeline / events API |
| 4. Browser observations | before/after visible_text | Present in `investigation/report.json`; after click includes `Message sent: Test User` | Independent evidence exists |
| 5. Behavioral discoveries | VerifiedFindings from observations | Only mode finding verified | **Critical gap** |
| 6. Reconstruction status | Skipped because Understand | `skipped` + note in final_report; UI still frames as “partial” missing artifacts | Misleading framing |
| 7. Validation results | N/A / not requested | Dashes for passed/failed/match; listed as missing artifact | Looks like absent results rather than skipped |
| 8. Verified findings | Evidence-backed claims | Mode only | Insufficient |
| 9. Evidence references | Traceable refs | Mode refs valid; behavioral observations not claimed | Partial |
| 10. EvidenceGraph | Action/observation graph | 13 nodes / 12 edges from investigation report | Usable for developers who open it |
| 11. Repair | None for this job | “No repair recorded” | OK |
| 12. Developer Report | Technical reproducibility | Same thin verified set + TaskBoard unsupported claims | Same root cause as Simple |
| 13. Download technical findings | Markdown downloads | Buttons present | Same content quality issue |

**Reproducibility:** A developer reading `investigation/report.json` **can** reproduce that confirmation text appeared after click. The **reports do not** surface that as a verified finding. Terminology: “Discovering”, “Availability: partial”, “validation unavailable”, “Fresh AI” vs `muse`.

### Persona C — Authorized ContactPad user

| Check | Result |
|-------|--------|
| URL approval | Rejection for public URL clear; allowlisted `8005` accepted by product rules |
| Approval vs investigation success | Distinguishable conceptually; Results “Completed” + “partial” blurs “investigation finished” vs “fully verified pipeline” |
| Feature description reaches engine | Yes — feature string matches in final_report and report.json |
| Choose Understand | Yes — radio on New Investigation; stages skipped with Understand-only notes in artifacts |
| Why reconstruction skipped | Artifact notes correct; Simple Report / availability messaging still treat missing recon as incompleteness |
| Results accessible | Yes via `?job=fe8ef026…` after hydrate |
| Report describes selected feature accurately | Feature string correct; **verified discoveries and unknowns do not match ContactPad feature** |

**Constraint honored:** No new paid Meta API calls; used saved investigation `fe8ef026…`.

---

## Stage 2 — ContactPad AI report root-cause analysis

### Recorded investigation facts (artifacts)

- **ID:** `fe8ef0266f9247638f69a23654d0ad5c`
- **App:** ContactPad (`contactpad`), URL `http://127.0.0.1:8005/`
- **Feature:** Submit a contact message and view confirmation
- **Mode:** muse · **Goal:** understand · **Pipeline:** investigate_only
- **API requests:** 5 · **Status:** completed · **Report availability (API):** partial
- **Events:** fill “Test User”, fill email, fill message, click “Send message”, stop
- **Independent browser observation (step 4 after):** visible text includes  
  `Message sent: Test User` and  
  `Test User <test@example.com>: Hello, this is a test message for confirmation.`
- **Screenshot:** `investigation/final.png` shows the same confirmation UI (saved under `docs/audit-evidence-second/contactpad-final-screenshot.png`)
- **Objectives (generic):** `feature_controls_observed`, `feature_interaction_attempted`, `page_response_observed` all `supported: true`
- **VerifiedFindings via API:** exactly one verified claim — *Investigation mode was recorded as muse.*
- **Unsupported / unknown leakage:** task reload persistence, PostgreSQL permanence, TaskBoard-style untested behaviors (editing/deletion/reordering)

### Did confirmation actually appear?

**Yes, independently of Muse’s stop narrative.**  
Evidence: `events[3].after.visible_text` (click step) and `final.png`. Muse’s stop reason is consistent with observations but is **not** what verification used.

### Root cause (confirmed)

| Factor | Role |
|--------|------|
| **Insufficient verification predicates** | `build_default_findings()` never turns fill/click/`visible_text` deltas or generic objectives into verified behavioral findings |
| **Generic TaskBoard template leakage** | For any non-`calculator` target (including `contactpad`), default findings still assert reload-persistence / permanent-task / PostgreSQL rejection claims; `default_untested_behaviors()` returns TaskBoard list |
| **Report-generation consumes VerifiedResults** | Simple/Developer reports correctly avoid inventing discoveries — so they honestly show only mode + irrelevant unknowns |
| **Misleading agent summaries (secondary)** | Stop reason is vivid; UI timeline “Recorded purpose” repeats Muse prose, while “Verified” section under-delivers — users may over-trust the stop text |
| **Availability = partial always without validation** | `build_verified_results()` sets `availability='partial'` if validation missing — even when Understand intentionally skipped validation |

**Not the primary cause:** missing browser evidence, incomplete investigation artifacts for the explore stage, or broken Muse run. Evidence exists; verification and uncertainty templates do not use it appropriately for ContactPad/generic apps.

**Classification:** Confirmed bug (reporting/verification logic) + Confirmed bug (TaskBoard template leakage).

---

## Stage 3 — Report quality assessment

### Simple Report (as shown in UI for `fe8ef026…`)

1. **Explain what happened?** Partially — timeline narrates fills/click; verified section does not.
2. **Meaningful feature behavior?** No as verified discoveries; yes buried in timeline / Muse purpose text.
3. **Observation vs inference?** Weak — Muse stop reason looks like fact; verified list ignores confirmation.
4. **What remains unknown?** Present but **wrong app** (tasks/PostgreSQL).
5. **Unrelated app statements?** **Yes** — TaskBoard claims.
6. **Repetitive?** Timeline “What happened” repeats chrome text every step; truncates before confirmation on early steps.
7. **Technical details too early?** Mode/job IDs and empty test metric strip appear before a clear story.
8. **Skipped stages?** Reconstruction “skipped” shown, but “partially available” + missing artifact list read as errors.
9. **Investigation succeeded?** Ambiguous (Completed vs partial).
10. **Completion vs verification?** Not clearly distinguished.

### Developer Report / shared VerifiedResults

1. Browser evidence inspectable in artifacts/API — **yes** if developer knows where.
2. Evidence refs for verified claims — valid for mode only.
3. Inputs/outputs — in events; not elevated as findings.
4. Uncertain claims — present but wrong domain.
5. Verification scopes — accurate for the claims that exist; wrong claims shouldn’t exist.
6. Investigation errors — none for this job.
7. Technical conclusions reproducible from JSON — **yes**; from report alone — **no**.
8. Unsupported root-cause claims — product correctly refuses “original is defective”; incorrectly surfaces irrelevant TaskBoard storage claims.

---

## Stage 4 — Product surface audit (screens)

### HOME
- Clear allowlist messaging — good.
- “phase 5c” status — jargon (Verified usability issue).
- Hackathon branding: **not observed** in user-facing copy during this pass (good).
- Mobile: nav compresses to Home/New/Current/Results — usable; hero text wraps tightly in narrow widths.

### NEW INVESTIGATION
- URL field, feature, Understand vs Understand+reconstruct, Guided vs Fresh AI — findable.
- Public URL rejection message — clear.
- “validation unavailable” on ContactPad card — unexplained (Verified usability issue).
- Successful URL check less salient than failure (Verified usability issue).

### CURRENT INVESTIGATION / Progress
- “Discovering / Skipped” for Understand-only — sounds broken (Verified usability issue).
- Stage labels Exploring/Discovering/Preparing are opaque vs Investigate/Reconstruct/Verify.

### RESULTS / SIMPLE / DEVELOPER
- Empty state without session job — honest, but deep-link race can flash empty (Hypothesis / minor).
- Verified discoveries thin; TaskBoard leakage — **Critical**.
- Empty PASSED/FAILED/MATCH RATE for Understand — looks like zero tests rather than not requested (High).

### HOW WE KNOW / EvidenceGraph
- Only chains the mode finding in the readable report path.
- Graph JSON exists with action nodes — under-surfaced for non-developers.

### RECONSTRUCTION / VALIDATION / REPAIR
- Correctly absent for Understand; messaging still frames absence as incompleteness (High).

---

## Findings register

### FINDING-01 — ContactPad verified discoveries omit independently observed behavior

- **ISSUE:** Only verified claim is investigation mode; fills, submit click, and confirmation text are not verified findings despite browser evidence.
- **LOCATION:** Results → Simple Report → “What It Discovered”; `GET /api/investigations/{id}/verified-findings`; `reversex/verification.py` `build_default_findings`
- **OBSERVED:** `verified_findings` length 1 (mode). Step-4 `after.visible_text` contains confirmation.
- **EXPECTED:** Evidence-grounded verified findings such as field filled, button clicked, visible content changed, confirmation text appeared (when predicates pass).
- **USER IMPACT:** Nontechnical users conclude ReverseX discovered almost nothing; developers cannot trust the report as a summary of evidence.
- **ROOT CAUSE:** No generic observation predicates in default findings; objectives not mapped to VerifiedFindings.
- **SEVERITY:** Critical  
- **TYPE:** Confirmed bug  
- **RECOMMENDED FIX:** Add deterministic observation-based findings from investigation events/objectives; do not trust Muse prose alone.  
- **EVIDENCE:** API verified-findings; `artifacts/.../investigation/report.json` step 4; UI body text dump; `final.png`.

### FINDING-02 — TaskBoard uncertainty / claims leak into ContactPad reports

- **ISSUE:** Unsupported claims and untested behaviors mention tasks, reload persistence, PostgreSQL, task editing/deletion.
- **LOCATION:** Simple Report “What Remains Unknown”; `default_untested_behaviors`; reload/postgres defaults in `build_default_findings` for `target != calculator`
- **OBSERVED:** ContactPad job shows those exact strings.
- **EXPECTED:** Uncertainty scoped to ContactPad / generic feature investigation (or omitted if irrelevant).
- **USER IMPACT:** Destroys trust; looks like wrong report template.
- **ROOT CAUSE:** TaskBoard-centric defaults applied to all non-calculator targets.
- **SEVERITY:** Critical  
- **TYPE:** Confirmed bug  
- **RECOMMENDED FIX:** Gate TaskBoard-specific rules on `taskboard` (or equivalent); provide contactpad/generic untested lists.  
- **EVIDENCE:** UI unknown section; human-report unsupported_findings.

### FINDING-03 — Understand-only runs labeled “partially available” / incomplete

- **ISSUE:** Availability `partial` because validation/spec/recon artifacts missing even when intentionally skipped.
- **LOCATION:** Results header; `outcome_blurb`; `build_verified_results` availability logic
- **OBSERVED:** “Results for contactpad are only partially available.” Missing artifacts listed as coverage limitations.
- **EXPECTED:** Completed Understand investigation presented as complete for its requested scope; skipped stages explained as “not requested.”
- **USER IMPACT:** Users think the run failed or is unfinished.
- **ROOT CAUSE:** Availability conflates missing-optional-pipeline with incomplete investigation.
- **SEVERITY:** High  
- **TYPE:** Confirmed bug  
- **RECOMMENDED FIX:** If pipeline/goal is investigate_only / understand, treat skipped recon/validation as expected; don’t mark partial solely for those.  
- **EVIDENCE:** final_report stages skipped notes; verified availability field; UI summary.

### FINDING-04 — Empty validation metrics shown when validation was not requested

- **ISSUE:** PASSED/FAILED/INVALID/MATCH RATE show “—” as if tests exist but empty.
- **LOCATION:** Results Simple Report metric strip
- **OBSERVED:** All dashes for ContactPad Understand job.
- **EXPECTED:** Hide metrics or label “Validation was not requested (Understand).”
- **USER IMPACT:** Implies failed or missing verification of recreation.
- **ROOT CAUSE:** UI always renders validation summary slots.
- **SEVERITY:** High  
- **TYPE:** Verified usability issue  
- **RECOMMENDED FIX:** Conditional UI + report copy for investigate_only.  
- **EVIDENCE:** Results page text dump.

### FINDING-05 — Progress “Discovering / Skipped” reads as failure

- **ISSUE:** Specification stage labeled “Discovering” shows Skipped without explaining Understand.
- **LOCATION:** Current Investigation progress steps (`WorkspacePage` STAGE_STEPS)
- **OBSERVED:** Exploring Completed · Discovering Skipped · Preparing results Ready
- **EXPECTED:** “Reconstruction / specification not requested” or hide skipped optional stages for Understand.
- **USER IMPACT:** Anxiety that discovery failed.
- **SEVERITY:** Medium  
- **TYPE:** Verified usability issue  
- **RECOMMENDED FIX:** Relabel stages; annotate skipped-with-reason for understand.  
- **EVIDENCE:** Progress page body text.

### FINDING-06 — Timeline buries confirmation; repeats chrome text

- **ISSUE:** “What happened” dumps page chrome; confirmation truncated; meaningful delta not highlighted.
- **LOCATION:** Simple Report timeline / `narrate_event` in `reporting.py`
- **OBSERVED:** Steps 1–3 end with “No me…”; step 4 “Messa…” without clear “confirmation appeared.”
- **EXPECTED:** Prefer visible-text **change** excerpt; call out newly appeared confirmation strings when present.
- **USER IMPACT:** Hard to see the one important outcome in the timeline.
- **SEVERITY:** Medium  
- **TYPE:** Verified usability issue  
- **RECOMMENDED FIX:** Narrate diffs / new phrases from before→after.  
- **EVIDENCE:** Timeline API + UI.

### FINDING-07 — ContactPad “validation unavailable” unexplained

- **ISSUE:** Sample card shows jargon without saying independent oracle isn’t implemented for ContactPad.
- **LOCATION:** New Investigation sample cards
- **SEVERITY:** Medium · Verified usability issue  
- **RECOMMENDED FIX:** Plain language: “Understand works; automated original-vs-recreation scoring isn’t available for this sample yet.”

### FINDING-08 — Landing status “phase 5c”

- **ISSUE:** Internal phase label on System status.
- **LOCATION:** Home footer  
- **SEVERITY:** Low · Verified usability issue  
- **RECOMMENDED FIX:** “Backend online” only for nontechnical users.

### FINDING-09 — Mode naming inconsistency (muse / Fresh AI / Fresh AI Investigation)

- **ISSUE:** Three labels for one mode.
- **SEVERITY:** Low · Verified usability issue  
- **RECOMMENDED FIX:** Consistent user-facing name with technical `muse` only in Developer Report.

### FINDING-10 — Hackathon branding

- **ISSUE:** Check for leftover hackathon chrome.
- **OBSERVED:** Not seen in Home / New / Results during this browser pass.
- **SEVERITY:** n/a · Not observed (positive)

### FINDING-11 — Deep link `?job=` empty flash / session dependence

- **ISSUE:** Initial snapshot showed empty Results before job hydrated.
- **SEVERITY:** Low · Hypothesis / minor race  
- **RECOMMENDED FIX:** Loading state while `watchExisting` resolves.

### FINDING-12 — Sidebar label truncation on constrained widths

- **ISSUE:** “New Invest.” / “Current Inv.” cut off in some captures.
- **SEVERITY:** Low · Verified usability issue (narrow layouts)

---

## Priority for Stage 6 fixes

1. FINDING-01 — behavioral verified findings from observations  
2. FINDING-02 — stop TaskBoard template leakage  
3. FINDING-03 — Understand / investigate_only availability & skip messaging  
4. FINDING-04 — hide or relabel validation metrics when not requested  
5. FINDING-05 / FINDING-06 — progress + timeline clarity  
6. FINDING-07 / FINDING-08 / FINDING-09 — copy polish  

**Out of scope for Stage 6 (preserve):** Muse Spark, Playwright engine, reconstruction generation, validation oracle, Docker boundaries, controlled repair algorithms — unless a narrowly scoped hook is required for findings above.

---

## Evidence index

| Artifact | Path / source |
|----------|----------------|
| ContactPad final UI screenshot | `docs/audit-evidence-second/contactpad-final-screenshot.png` |
| Investigation report | `artifacts/fe8ef026…/investigation/report.json` |
| Final report (stages skipped) | `artifacts/fe8ef026…/final_report.json` |
| Evidence graph | `artifacts/fe8ef026…/evidence_graph.json` |
| Verified findings API | `GET /api/investigations/fe8ef026…/verified-findings` |
| Human report / timeline | `GET /api/investigations/fe8ef026…/human-report` |
| Browser UI dumps | Cursor browser Runtime.evaluate on Results/Progress/New Investigation |

---

*End of Stage 5 audit. Application code changes begin only after this document.*
