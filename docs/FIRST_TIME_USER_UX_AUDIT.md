# ReverseX Engineer — First-Time User UX Audit

**Date:** 2026-11-03 (local)  
**Branch observed:** `ui/hackathon-redesign`  
**App under test:** `http://127.0.0.1:5173` (Vite) against API `http://127.0.0.1:8000`  
**Auditor stance:** Independent first-time user / usability tester — not the implementing engineer  
**Constraint:** No product code changes; Demo Mode / existing jobs only; no paid Meta calls; no arbitrary public URLs  

---

## 1. Executive Summary

ReverseX currently feels like a **polished developer / hackathon prototype**, not a finished product a small-business owner could trust without guidance.

The home page communicates a high-level purpose within about ten seconds (“understand / reconstruct / verify”), and the primary CTA **Start Investigation** is visible. After that, the experience frays:

- Users cannot investigate their own website (no URL field; backend only allows `taskboard` | `calculator`).
- **Investigations** and **Results** do not list past work; both open the same Engineering Workspace with different default tabs.
- **Explore a Verified Demo** landed on an empty EvidenceGraph (“No evidence graph loaded yet”), which is a broken first-time path.
- Workspace chrome is dense with jargon (**FastAPI**, **`?job=`**, **EvidenceGraph**, **Muse Spark**, filesystem paths).
- The Simple Report is the strongest nontechnical surface once a completed job is loaded, but it is long, dumps raw page text into “What happened,” and sits under engineering chrome that nontechnical users should never need.

**Verdict:** Usable as a **local demo for engineers who already know the pipeline**. Not yet usable as a product for first-time nontechnical users, and only partially usable for evaluating developers who expect history, custom targets, and reliable demo entry points.

---

## 2. Testing Method

1. Opened the live UI in Cursor’s browser automation (real Chromium session against `127.0.0.1:5173`).
2. Completed journeys as three personas **before** deep code reading.
3. Clicked real controls: Home CTAs, New setup, Demo/Live modes, Advanced options, Investigations/Results, workspace tabs, downloads, Load demo graph, Controlled repair demo, Diagnostics.
4. Used an existing completed job deep link `?job=69f0a4845ee347c8831d691aac18951a` (scripted TaskBoard, 0 Meta requests, 100% match) — no new Live AI run.
5. Checked viewports via CDP `Emulation.setDeviceMetricsOverride` at ~1440, 768, and 390 widths (tooling had no dedicated `browser_resize`; 1366 inferred from desktop layout behavior).
6. After journeys, verified capabilities against OpenAPI / API responses and selected frontend files (`App.tsx`, `ui.tsx`, `SetupPage.tsx`, `OverviewPage.tsx`, `api.py`).

**Not claimed:** Formal WCAG audit, multi-user moderated study, or exhaustive keyboard matrix.

---

## 3. Browser Environment

| Item | Value |
|------|--------|
| Frontend | Vite app at `http://127.0.0.1:5173` |
| Backend health | `status: ok`, `phase: 5c`, authorized targets `calculator`, `taskboard` |
| Automation | Cursor IDE browser MCP (navigate, snapshot, click, screenshot, CDP) |
| Jobs used | Existing completed TaskBoard job `69f0a484…`; demo GET endpoints for graph/repair |
| Screenshots | `docs/ux-audit-screenshots/` |

---

## 4. Nontechnical User Journey

Persona: small business owner, little programming knowledge.

| Step | Expected | Observed | Next action obvious? | Stuck? | Completed? |
|------|----------|----------|----------------------|--------|------------|
| Open app | Clear product home | Warm light marketing hero; brand + headline readable | Yes | No | Yes |
| Understand product | What it does for *me* | High-level AI investigate/reconstruct/verify; no mention that only two local demos are allowed | Partial | No | Partial |
| Begin investigation | Clear start | **Start Investigation** works → setup | Yes | No | Yes |
| Enter my website URL | Text field for my site | Only TaskBoard / MiniCalc cards; no URL field | No | Mentally stuck | **No** |
| Understand TaskBoard / MiniCalc | Sample apps I can try | Labeled “Authorized local test application”; still abstract (“Kanban demo”) | Partial | Mild | Partial |
| Demo vs Live | Which to pick safely | Demo recommended; Live warns Meta credits — relatively clear | Mostly | No | Yes |
| Start safe demo | One guided path | Can launch Demo Mode (not required for this audit); **Explore a Verified Demo** went to empty graph | No | **Yes** on explore path | Partial |
| Understand what ReverseX is doing | Plain progress | Engineering Workspace + FastAPI copy; Live tab uses `scripted` / job hashes | No | Mild | Partial |
| Find results | Obvious Results area | Nav **Results** with no job → empty reports + `?job=` hint | No | Yes without deep link | Partial |
| Understand discovery | Plain findings | Simple Report (after deep link) explains verified vs unknown well | After finding it | No | Yes |
| Reconstruction success | Clear yes/no | 5/5 match, 100% — clear in report header | Yes once in report | No | Yes |
| Problems | Clear failures | None on this job; repair empty with technical note | N/A | No | Yes |
| Evidence | Support for claims | “How We Know” + Supporting evidence expanders | Partial | No | Yes |
| Download readable report | Simple PDF/MD | **Download Simple Report** link present | Yes | No | Yes (control found; download not force-tested) |

### Persona 1 answers

| Question | Answer |
|----------|--------|
| Understand ReverseX in 10 seconds? | **Partially** — purpose yes; real capability limits no |
| Primary action obvious? | **Yes** — Start Investigation |
| Know where to enter URL? | **No** — nowhere; product cannot take a custom URL |
| TaskBoard / MiniCalc as samples? | **Mostly** — “authorized demo” language helps; still abstract |
| Why two modes? | **Mostly clear** on setup |
| When to use each? | **Demo for walkthrough / Live costs credits** — OK |
| Distinguish AI vs scripted? | **If they reach Live/Reports** — mode `scripted` / Meta request count; Easy to miss that Demo is not “real AI” |
| Understand timeline? | **Weak** — technical action labels (“Offline scripted…”) |
| Find final results without tech knowledge? | **Hard** without deep link or successful launch |
| Understand Simple Report? | **Best surface in the product** once reached |
| Verified vs uncertain? | **Yes** — Simple Report does this well |
| Understand failed tests? | **Not exercised** on this job; Validation uses snake_case scenario IDs |
| Mismatch vs original defect? | **Explained** in “What Remains Unknown” (good) |

---

## 5. Developer User Journey

Persona: engineer evaluating reliability of investigate → reconstruct → validate.

| Goal | Finding |
|------|---------|
| Entry point | Clear: New / Start Investigation |
| Supported app types | Only two local demos — **honest in health/API**, under-communicated on Home |
| Fresh AI investigation | Live AI Mode → Muse; credit warning present |
| Feature scope selection | **Missing** — target implies a fixed feature string; no scope picker |
| Investigation events | Live tab timeline present (`fill` / `click` / …) |
| Observed browser behavior | Reconstruction tab shows screenshot counts; Live “Browser evidence” felt sparse vs 12 screenshots elsewhere |
| Generated reconstruction | Reconstruction tab: files `index.html`, `script.js`, `style.css`, status `reused` |
| Validation | Pass/fail counts + per-scenario Original vs Reconstructed |
| Pass/fail scenarios | Named with technical IDs (`empty_input_validation`, etc.) |
| Compare behaviors | Present per scenario |
| Evidence references | Expandable supporting evidence; artifact paths |
| EvidenceGraph | Interactive React Flow; useful for experts; opaque name |
| Repair attempts | Empty for successful job; Controlled repair demo works **only when not conflicting with job repair state** |
| Developer Report | Dense, legend, expandable sections, embedded graph, raw VerifiedResults |
| Download technical findings | Developer Report download link present |

**Technical quality of information (once a job is loaded):** Easy enough for a developer who knows the domain; clearly labeled in places; evidence-linked; limitations called out honestly in verification copy. **History / discovery of jobs is not productized.** Reproducibility depends on local artifacts and knowing the job UUID.

---

## 6. Returning User Journey

| Goal | Finding |
|------|---------|
| Find previous investigations | **Failed** — no history list UI |
| Identify which investigation | Only via remembered `?job=` UUID or leftover browser tabs |
| Open results | Deep link works after load; brief empty-state flash observed |
| Status / completed / failed | Visible in Reports header and Live configuration |
| Simple / Developer reports | Toggle works |
| Evidence | EvidenceGraph + How We Know |
| Download correct report | Two download links — clear |

**API check:** `GET /api/investigations` → **405 Method Not Allowed**. Create-by-POST only; **no list endpoint**. Persistence of job artifacts on disk exists for known IDs, but the product does not expose a browsable history. Treat missing history as a **product limitation**, not user error.

**Navigation overlap:** Home / New / Investigations / Results / Reports / Live / Reconstruction / Validation / EvidenceGraph / Repair — Investigations ≈ Live workspace, Results ≈ Reports tab. Confirmed in `frontend/src/components/ui.tsx`.

---

## 7. Navigation Assessment

**Observed:**

- Desktop (≥900px): beige sidebar with Home, New Investigation, Investigations, Results.
- Below 900px: sidebar hidden; compact top pills with truncated labels (`New Investigation` → **New**).
- Workspace secondary tabs: Reports, Live, Reconstruction, Validation, EvidenceGraph, Repair.
- Persistent demo buttons: Load demo graph, Controlled repair demo — compete with primary investigation results.

**Problems:**

1. Investigations ≠ a list of investigations.
2. Results without a job shows engineering empty state + deep-link instructions meant for developers.
3. Too many overlapping “places to look at outcomes.”
4. Hackathon footer + “Warm light workspace” subtitle weaken product identity on mobile header.

---

## 8. Investigation Setup Assessment

**Strengths:**

- Demo vs Live cards are comparatively clear; Live warns about Meta credits.
- Targets labeled as authorized local demos.
- Demo Mode defaults reuse where allowed.

**Problems:**

- No path for “my application URL” — and backend **cannot** accept one (`target_id: Literal['taskboard','calculator']` in `reversex/api.py`).
- “Kanban,” “Muse Spark,” “scripted,” “pipeline,” “action budget” arrive too early for nontechnical users.
- Advanced options expose FastAPI field names in plain sight.
- Feature scope is not choosable; users may think they are investigating “the whole app.”
- MiniCalc does not allow reconstruction reuse — easy to miss until Advanced is opened.

---

## 9. Simple Report Assessment

**Strengths (observed on completed TaskBoard job):**

- Plain summary sentence with match outcome.
- Passed / failed / invalid / match rate.
- “What It Discovered” vs “What Remains Unknown” is unusually honest and helpful.
- Explicitly separates reconstruction mismatch from “original is defective.”
- Download Simple Report control present.

**Problems:**

- Nested under **Engineering workspace** + FastAPI subtitle.
- “What ReverseX Tested” dumps large raw page text into “What happened.”
- Very long page; nontechnical users may abandon before “Unknown.”
- “Technical event details” expanders still feel engineer-oriented.

---

## 10. Developer Report Assessment

**Strengths:** Verification legend; same VerifiedResults; expandable contradictions / requirements / validation / repair; EvidenceGraph; raw JSON escape hatch; download.

**Problems:** Heavy; appears inside the same chrome as Simple Report; artifact filesystem paths; assumes familiarity with verification ontology.

---

## 11. EvidenceGraph Assessment

**First-time nontechnical user:** Name is not meaningful; graph of “Investigation / action” nodes is overwhelming; copy wisely steers to Reports for plain English.

**Developer:** Useful interactive map with supporting-evidence panel; sources list artifact paths.

**Value:** High for debugging; low as a default first destination. **Explore a Verified Demo** wrongly prioritizes this tab.

---

## 12. Repair Experience Assessment

- Successful TaskBoard job: Repair tab correctly empty with explanation.
- **Controlled repair demo** (empty workspace): Works; labeled **Controlled Fault-Injection Evaluation** — honest.
- **Bug / UX failure:** With a completed job loaded, clicking Controlled repair demo stayed on “No repair results for this job…” even though `GET /api/demo/controlled-repair` returns data. Job repair state appears to win over demo payload.
- Evidence paths show absolute Windows filesystem paths — intimidating and non-portable for sharing.

---

## 13. Branding Assessment

| Signal | Observation |
|--------|-------------|
| Independent product? | Partially — visual polish yes |
| Hackathon references? | **Yes** — sidebar footer “Meta Global AI Developer Hackathon” |
| Consistency | Light theme coherent; mobile subtitle “Warm light workspace” reads like a theme note, not a product tagline |
| Trust | Undermined by empty demo path, `?job=` instructions, FastAPI talk, JSON diagnostics as “Completed” |

---

## 14. Responsive and Accessibility Findings

| Width | Observation |
|-------|-------------|
| ~1440 desktop | Sidebar + content readable; workspace tabs wrap to two rows |
| ~1366 laptop | Same pattern as desktop (sidebar if ≥900) |
| 768 tablet | Sidebar hidden; top nav pills; hero still usable |
| 390 mobile | Nav wraps (Results can drop to second line); workspace tabs dense; content stacks OK |

**Accessibility (visual / light instrumentation only — not WCAG certification):**

- Focused button computed style showed **`outline: none`** and no compensatory `boxShadow` — weak/missing focus indicator (**observed**).
- Status often uses color + text (pills with labels) — better than color-only, but System status uses a **Completed** pill for “backend healthy,” which is misleading.
- EvidenceGraph and dense reports are difficult on small screens.
- Contrast generally acceptable for body text on white cards (subjective visual check only).

---

## 15. Actual Bugs or Broken Interactions

| ID | Observation | Classification |
|----|-------------|----------------|
| B1 | **Explore a Verified Demo** → EvidenceGraph shows “No evidence graph loaded yet” | **Broken / unreliable first-time path** (UI). Code intends `loadDemoGraph()` + repair demo (`App.tsx`), but user saw empty graph. |
| B2 | **Controlled repair demo** while a job is loaded does not show demo repair results | **Broken interaction / state conflict** (UI). API GET works. |
| B3 | Deep-linked job briefly/alternatively shows empty “start investigation or `?job=`” before/while content exists | **Loading / empty-state race** (UI). Content eventually present in DOM. |
| B4 | **Investigations** nav implies a list but opens Live workspace | **Misleading IA** (design). |
| B5 | Focus outline none on tested button | **A11y defect** (UI). |

---

## 16. Missing Product Capabilities

| Expectation | Status | Evidence |
|-------------|--------|----------|
| Enter custom website URL | **Not implemented** (backend + UI) | Setup has no field; API `target_id` only `taskboard`\|`calculator`; health `authorized_targets` |
| Browse past investigations | **Not implemented** (API list + UI) | `GET /api/investigations` → 405; no history UI |
| Choose arbitrary feature scope | **Not implemented** | Fixed target descriptions / suites |
| Self-serve “verified demo” without knowing tabs | **Partially implemented / unreliable** | Button exists; observed empty graph |
| Persist jobs across API restarts in UI | **Partial** — artifacts may remain on disk; UI has no discovery | Deep link works for known ID; no catalog |
| Investigate arbitrary public sites | **Not implemented** (intentional safety) | Do not imply via UI that it works |

---

## 17. Prioritized Usability Issues

### ISSUE 1 — Cannot investigate “my website”
- **LOCATION:** Home promise vs New Investigation  
- **USER EXPECTATION:** Paste a URL and start  
- **ACTUAL EXPERIENCE:** Only TaskBoard / MiniCalc  
- **WHY CONFUSING:** Marketing language sounds general-purpose  
- **IMPACT:** Core first-time goal fails  
- **SEVERITY:** Critical  
- **RECOMMENDATION:** Explicitly state “demo apps only” on Home and Setup; do not imply custom URLs until backend exists  
- **EVIDENCE:** Setup screenshots `02`, `03`; API schema  

### ISSUE 2 — Explore a Verified Demo dead-ends on empty EvidenceGraph
- **LOCATION:** Home → Explore a Verified Demo  
- **USER EXPECTATION:** See a finished, readable demo result  
- **ACTUAL EXPERIENCE:** Empty graph; must discover Load demo graph / Reports separately  
- **WHY CONFUSING:** Primary secondary CTA fails its promise  
- **IMPACT:** Blocks safest no-Meta path  
- **SEVERITY:** Critical  
- **RECOMMENDATION:** Land on Simple Report for a known completed demo job (or auto-load graph + switch to Reports with summary)  
- **EVIDENCE:** Screenshot `11-explore-verified-demo-empty.png`; browser observation  

### ISSUE 3 — No investigation history; Investigations/Results overlap
- **LOCATION:** Primary nav  
- **USER EXPECTATION:** Investigations = past jobs; Results = outcomes list  
- **ACTUAL EXPERIENCE:** Same workspace, different default tabs; empty without `?job=`  
- **WHY CONFUSING:** Labels don’t match mental model  
- **IMPACT:** Returning users cannot resume work  
- **SEVERITY:** Critical (returning) / High (first-time)  
- **RECOMMENDATION:** Rename or merge nav; add job list only if API supports it — otherwise remove “Investigations” list implication  
- **EVIDENCE:** Screenshot `04-results-empty-workspace.png`; `GET /api/investigations` 405; `ui.tsx`  

### ISSUE 4 — Engineering Workspace jargon as the results shell
- **LOCATION:** Workspace header and empty states  
- **USER EXPECTATION:** “Your results” in plain language  
- **ACTUAL EXPERIENCE:** “FastAPI investigation pipeline,” deep-link query instructions  
- **WHY CONFUSING:** Exposes implementation  
- **IMPACT:** Users feel the tool isn’t for them  
- **SEVERITY:** High  
- **RECOMMENDATION:** Soften copy; hide deep-link syntax behind a developer disclosure  
- **EVIDENCE:** Screenshots `04`, `06`  

### ISSUE 5 — Controlled repair demo fails when a job is active
- **LOCATION:** Workspace → Controlled repair demo  
- **USER EXPECTATION:** Always show labeled demo  
- **ACTUAL EXPERIENCE:** Job’s empty repair message wins  
- **WHY CONFUSING:** Button appears clickable but ineffective  
- **IMPACT:** Demo of repair capability looks broken  
- **SEVERITY:** High  
- **RECOMMENDATION:** Demo mode should overlay/replace job repair view or warn that a job is suppressing the demo  
- **EVIDENCE:** Browser observation with job `69f0a484…` vs empty-workspace success (`12`)  

### ISSUE 6 — Too many workspace tabs for first-time users
- **LOCATION:** Reports / Live / Reconstruction / Validation / EvidenceGraph / Repair  
- **USER EXPECTATION:** One results place + optional details  
- **ACTUAL EXPERIENCE:** Six tabs before reading anything  
- **SEVERITY:** High  
- **RECOMMENDATION:** Default to Reports only; progressive disclosure for engineering tabs  
- **EVIDENCE:** Screenshots `06`–`10`  

### ISSUE 7 — Demo vs Live still uses opaque terms (Muse, scripted, reuse)
- **LOCATION:** Setup Investigation mode / Live configuration  
- **SEVERITY:** Medium  
- **RECOMMENDATION:** Plain labels: “Guided demo (no AI charges)” vs “Live AI (uses Meta credits)” and show scripted/muse only under Advanced  
- **EVIDENCE:** Screenshot `03`  

### ISSUE 8 — Simple Report “What happened” raw page dumps
- **LOCATION:** Simple Report steps  
- **SEVERITY:** Medium  
- **RECOMMENDATION:** Summarize visible outcome; keep raw DOM/page text in Developer view  
- **EVIDENCE:** Accessibility snapshot of report steps  

### ISSUE 9 — Advanced options show FastAPI request field names
- **LOCATION:** Setup → Advanced  
- **SEVERITY:** Medium  
- **RECOMMENDATION:** Remove API schema sentence from user UI  
- **EVIDENCE:** Setup advanced expanded snapshot  

### ISSUE 10 — Branding / trust: hackathon + theme subtitle + Completed health pill
- **LOCATION:** Shell footer, mobile header, System status  
- **SEVERITY:** Medium / Low  
- **RECOMMENDATION:** Replace “Warm light workspace”; use Online/Offline not Completed; optional hackathon badge less prominent  
- **EVIDENCE:** Screenshots `01`, `14`, `15`  

### ISSUE 11 — Mobile nav truncation and wrap
- **LOCATION:** <900px header  
- **SEVERITY:** Medium  
- **RECOMMENDATION:** Icon+label menu or overflow “More”  
- **EVIDENCE:** Screenshot `13`  

### ISSUE 12 — Missing keyboard focus indicators
- **LOCATION:** Global buttons  
- **SEVERITY:** Medium (a11y)  
- **RECOMMENDATION:** Visible `:focus-visible` rings  
- **EVIDENCE:** CDP computed style `outline: none`  

---

### Priority table

| Priority | Problem | User impact | Recommended fix |
|----------|---------|-------------|-----------------|
| 1 | No custom URL / oversold generality | Cannot investigate own site | Honest “demo apps only” framing everywhere |
| 2 | Explore Verified Demo empty graph | Safest path fails | Open completed Simple Report demo by default |
| 3 | No history; Investigations/Results overlap | Cannot return to past work | Rename nav; add list only with API support |
| 4 | Engineering jargon shell | Nontechnical users bounce | Plain “Results” chrome; hide FastAPI/`?job=` |
| 5 | Repair demo vs job state conflict | Repair capability looks broken | Isolate demo state from job repair |
| 6 | Six workspace tabs up front | Cognitive overload | Progressive disclosure |
| 7 | Raw page text in Simple Report | Hard to read findings | Summarize outcomes |
| 8 | Weak focus / mobile nav | Access / small-screen friction | Focus rings + better mobile nav |

---

## 18. Five Most Important Improvements

1. **Make the safest path work:** Explore a Verified Demo → readable Simple Report for a known completed demo (no empty EvidenceGraph).
2. **Stop implying custom websites** until supported; say clearly that only TaskBoard and MiniCalc are available.
3. **Fix information architecture:** One “Results” concept; do not label a tabless workspace as “Investigations” without a job list.
4. **Progressive disclosure:** Nontechnical default = Simple Report; engineering tabs secondary.
5. **Repair demo reliability + plain language** on workspace chrome (remove FastAPI / query-string instructions from default UI).

---

## 19. Screenshots

Stored under `docs/ux-audit-screenshots/`:

| File | What it shows |
|------|----------------|
| `01-home-first-impression.png` | Home hero / CTAs |
| `02-setup-targets.png` | TaskBoard / MiniCalc only |
| `03-setup-modes-advanced.png` | Demo vs Live |
| `04-results-empty-workspace.png` | Results with no job + `?job=` copy |
| `06-job-reports-header.png` | Engineering workspace + tabs over results |
| `07-investigation-results-downloads.png` | Completed TaskBoard report header / downloads |
| `08-live-configuration.png` | Live tab technical configuration |
| `09-validation-counts.png` | Validation pass counts |
| `10-evidencegraph.png` | EvidenceGraph developer view |
| `11-explore-verified-demo-empty.png` | Broken Explore Verified Demo empty state |
| `12-controlled-repair-demo.png` | Labeled controlled fault-injection demo (working) |
| `13-mobile-390-workspace.png` | Mobile nav / tabs |
| `14-tablet-768-home.png` | Tablet home |
| `15-diagnostics-json.png` | Diagnostics expands raw health JSON |

---

## 20. Final Assessment

### Direct answers

1. **First impression:** Attractive, calm, “serious SaaS” home — then quickly feels like an internal engineering console.
2. **Understand what it does?** At slogan level, yes. At capability level (only two local demos), no.
3. **First confusion:** Where to put *my* website URL — and why Results talks about FastAPI and `?job=`.
4. **Start an investigation?** Yes, via Start Investigation / New.
5. **Investigate my own website?** No — not in UI, not in API.
6. **TaskBoard / MiniCalc?** Recognizable as demos if you read the cards; still abstract without previews.
7. **Demo vs Live?** Relatively clear on Setup; Live credit warning helps. Easy to still think Demo is “AI.”
8. **Engineering Workspace easy?** No for nontechnical users; acceptable for developers once a job is loaded.
9. **Reports useful?** Simple Report is genuinely useful and carefully scoped; Developer Report useful for engineers.
10. **Understand failures without tech knowledge?** Partially — narrative unknown/mismatch text is good; scenario IDs and repair paths are not.
11. **Unnecessarily complicated?** EvidenceGraph-as-default, six tabs, Advanced FastAPI fields, dual demo buttons always visible.
12. **Failed controls?** Explore Verified Demo (empty graph); Controlled repair with active job; Investigations-as-list expectation.
13. **Five most serious UX problems:** (1) no own-URL / oversold scope, (2) broken verified-demo path, (3) no history + nav overlap, (4) engineering jargon shell, (5) repair demo state conflict / tab overload.
14. **Highest-impact changes:** Fix verified-demo landing → Simple Report; honest capability framing; simplify nav/results IA; progressive disclosure of engineering tools.

### Product vs prototype

**ReverseX currently feels like a developer prototype with a marketing coat of paint**, not a usable end-user product. The verification honesty in the Simple Report is a real product-quality bright spot. Surrounding navigation, empty states, demo entry points, and capability framing still behave like a hackathon control panel.

**Observed vs hypothesis:** Items in §15–17 marked with screenshots/API status are **observed**. Recommendations are **not user-tested** beyond this single-auditor walkthrough.

---

*End of audit. No code was modified for this document beyond adding this report and screenshot assets under `docs/`.*
