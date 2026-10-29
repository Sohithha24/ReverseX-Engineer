# ReverseX Engineer — 3-Minute Demo Script

**Audience:** Meta Global AI Developer Hackathon judges  
**Mode:** Spoken naturally ≈ 3:00. Prefer **prerecorded pipeline footage** for Muse investigation/reconstruction/repair to avoid live Meta spend and Docker variance. UI deep-links and saved jobs are live-safe.

**Prerecorded footage used for:** Muse investigation steps, reconstruction generation, Docker validation runs, controlled repair Meta call.  
**Live-safe:** React workspace, target selector, deep-linked completed jobs, EvidenceGraph, Controlled Repair Evaluation panel (read-only API).

---

## Spoken script

### 0:00–0:20 — Problem and product

“ReverseX Engineer asks: can an AI *investigate* an authorized app through the browser, rebuild the observed behavior **without source**, and prove it with an independent oracle—not by trusting the model’s own score?

It’s a controlled hackathon prototype for Meta Muse Spark—not a claim that we reverse-engineer the open web.”

### 0:20–1:15 — Investigation and reconstruction workflow

*[Show prerecorded clip, or deep-link a completed Muse job.]*

“Muse selects browser actions—fill, click, reload, stop—against an allowlisted local target. We freeze an evidence-backed behavioral specification: observations versus hypotheses.

Then Muse reconstructs only from that frozen spec into three static files. The original TaskBoard or MiniCalc source never enters the model context.

*[Cut to validation summary.]* Playwright compares original versus reconstruction with fresh holdout inputs. The model does not grade itself.”

### 1:15–1:45 — TaskBoard and MiniCalc validation

*[Live UI: Application selector → TaskBoard / MiniCalc; or `?job=` deep links.]*

“Two structurally different fixtures. TaskBoard: tasks and persistence—**five of five** oracle tests. MiniCalc: arithmetic, empty input, reset—also **five of five**.

Same pipeline. Explicit targets only—no arbitrary internet URLs.”

### 1:45–2:20 — Controlled repair evaluation

*[Overview → Load Controlled Repair Evaluation.]*

“Both real reconstructions already passed. So for repair, we ran a **Controlled Repair Evaluation**: we intentionally broke a *copy* of the MiniCalc reconstruction with a documented off-by-one on Add. That defect was **not** an organic Muse failure.

Oracle dropped to **sixty percent**—three of five. One bounded Muse repair attempt—then revalidation with fresh holdouts—back to **one hundred percent**, with no regressions on the accepted candidate.”

### 2:20–2:45 — EvidenceGraph and traceability

*[EvidenceGraph panel.]*

“Every claim ties to artifacts: investigation events, frozen requirements, generated files, validation outcomes, and—when repair ran—mismatch to attempt to revalidation. No invented edges.”

### 2:45–3:00 — Contribution and limits

“Contribution: Muse-driven investigate → specify → reconstruct → oracle-validate → bounded repair, with evidence you can audit.

Limits: local allowlisted demos, Docker bridge is not a perfect sandbox, API is unauthenticated and local-only, and two fixtures plus one controlled repair do not prove general-purpose reverse engineering.

Thank you.”

---

## Screen-recording shot list

| # | Shot | Duration | Live / Prerecorded |
|---|------|----------|--------------------|
| 1 | Title + one-line problem | 0:00–0:15 | Live or still |
| 2 | Muse investigation timeline / events | 0:20–0:45 | **Prerecorded** preferred |
| 3 | Frozen spec snippet (observation IDs) | 0:45–0:55 | Live or still |
| 4 | Reconstruction files / preview | 0:55–1:10 | Prerecorded or artifact |
| 5 | TaskBoard validation 5/5 (`?job=` Phase 5A) | 1:15–1:30 | **Live** deep-link OK |
| 6 | MiniCalc selector + validation 5/5 | 1:30–1:45 | **Live** deep-link OK |
| 7 | Controlled Repair panel: labeled 60%→100% | 1:45–2:20 | **Live** demo button OK |
| 8 | EvidenceGraph nodes/edges | 2:20–2:45 | Live |
| 9 | Closing slide: limits + contribution | 2:45–3:00 | Still |

## Suggested deep links (local)

- MiniCalc completed job: `http://127.0.0.1:5173/?job=5b4a5d5ccd2c41a5b16e33fefd6bdcac`  
- TaskBoard completed job: `http://127.0.0.1:5173/?job=7f8300d82fbb4a03b44d525c676a98cd`  
- Controlled repair: Overview → **Load Controlled Repair Evaluation**

## Honesty checklist for the video

- [ ] Say “controlled / authorized fixtures,” not “any website.”  
- [ ] Label repair as **fault injection on a copy**.  
- [ ] Do not claim full Docker sandbox isolation.  
- [ ] Do not invent live Muse results during the talk.  
