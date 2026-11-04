# ReverseX Engineer — Demo Narration Script

**Target length:** ~3:00  
**Evidence basis:** Release E2E job `8307f8d9aa304926b57f91de7171bc9a` (TaskBoard Guided Demo, reused reconstruction, validation 5/5); Controlled Repair Example API.  
**Honesty:** No live Muse / paid Meta calls. Guided Demo and verified artifacts only.  
**TTS voice:** `en-US-JennyNeural` (Microsoft Edge neural TTS via `edge-tts`)

---

## Scene 1 — Introduction

**Visual:** ReverseX homepage / product overview.

**Narration:**

ReverseX Engineer is an AI-powered software investigation platform that explores how application features behave, reconstructs them, and independently verifies the results. It works against authorized local demo applications—not arbitrary websites on the open internet. This short walkthrough uses verified local results from a completed Guided Demo.

---

## Scene 2 — AI Investigation

**Visual:** New Investigation setup (TaskBoard + Guided Demo), then reopen completed job Progress view.

**Narration:**

A user selects an allowlisted application—here, TaskBoard—and chooses Understand and Reconstruct. For this demonstration we open a Guided Demo investigation that was already completed and verified, rather than starting a new live Meta Muse run during recording. In Muse mode, the agent can choose browser interactions such as fill, click, and reload, while ReverseX records observations into an evidence-backed behavioral specification. The job on screen ran in Guided Demo mode with zero Meta API requests in that release pass, so you can trust the stages without paying for a fresh Muse investigation.

---

## Scene 3 — Feature Reconstruction

**Visual:** Progress / reconstruction reused status and reconstructed-app evidence.

**Narration:**

From the frozen behavior specification, ReverseX produces an independent implementation as static files—HTML, JavaScript, and CSS. The original TaskBoard source never enters the model context. In this verified run, reconstruction was reused from an existing Phase Two artifact. We are therefore showing prior reconstruction evidence and status labels from that completed job, not implying that new reconstruction files were generated live during this video recording.

---

## Scene 4 — Independent Validation

**Visual:** Validation results — 5 passed / 100% on tested scenarios.

**Narration:**

ReverseX then compares the original application with the reconstruction using independent behavioral tests. Playwright exercises holdout scenarios against both sides so the model does not grade itself. For TaskBoard, five of five scenarios passed—a one hundred percent match on the tested cases. That score applies to those scenarios, not every possible behavior of the application.

---

## Scene 5 — Simple and Developer Reports

**Visual:** Results → Simple Report → Developer Report.

**Narration:**

The Simple Report explains the investigation in plain language for nontechnical readers—what was tested, what matched, and key limits. Switching to the Developer Report keeps the same verified findings, and adds technical observations, stage details, and testing evidence. Both reports draw from one completed investigation record, so the story stays consistent.

---

## Scene 6 — Controlled AI Repair

**Visual:** Controlled Repair Example panel (fault-injection evaluation).

**Narration:**

Next is the Controlled Repair Example—a labeled fault-injection evaluation. A deliberate defect was introduced into a reconstruction copy, detected by the oracle, then corrected through a bounded repair attempt and revalidated. This is separate from the TaskBoard investigation you just reviewed, and it is not an organic AI failure from that completed job.

---

## Scene 7 — Conclusion

**Visual:** Home branding / ReverseX Engineer name.

**Narration:**

ReverseX demonstrates investigate, reconstruct, independently validate, and controlled repair—with evidence you can audit. ReverseX Engineer.

---

## Production notes

- Job deep link: `http://127.0.0.1:5173/?job=8307f8d9aa304926b57f91de7171bc9a`
- Scene videos are timed to measured TTS durations in `demo/audio/timeline.json`
- Subtitles: `demo/demo_subtitles.srt` (also burned into the MP4)
