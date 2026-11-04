# ReverseX Engineer — Video Production Report

**Date:** 2026-11-04  
**Output:** `demo/reversex_demo.mp4`  
**Duration:** **00:02:55** (~175.4 s)  
**Resolution / codecs:** 1920×1080, H.264 (High) + AAC stereo 48 kHz  
**Status:** Complete local demo video ready for human review (not uploaded)

---

## 1. Was the video successfully generated?

**Yes.** Final MP4 exists at:

`C:\Users\sohit\Downloads\ReverseX_Engineer_Phase1a_Starter\reversex-engineer-starter\demo\reversex_demo.mp4`

(~13.6 MB). FFmpeg probe confirms playable H.264/AAC streams.

---

## 2. AI narration?

**Yes.** Full English voice-over is muxed into the MP4 (AAC). Measured loudness: mean ≈ −24.5 dB, max ≈ −4.4 dB (audible, not clipped).

---

## 3. Voice / TTS method

| Item | Value |
|------|--------|
| Tool | `edge-tts` (local Python package) |
| Voice | **`en-US-JennyNeural`** (Microsoft neural English US female) |
| Rate | `+0%` |
| Alternatives checked | Windows System.Speech David/Zira available; edge-tts preferred for naturalness |
| Cost | No purchased TTS service; no credentials entered |

Narration assets: `demo/audio/*.wav`, `demo/audio/narration_full.wav`, timeline in `demo/audio/timeline.json`.

---

## 4. Subtitles?

**Yes.**

- Side-car file: `demo/demo_subtitles.srt` (23 cues, timed to narration)
- Burned into the MP4 (Segoe UI, white on dark bars, bottom-centered)

---

## 5. Total duration

**2 minutes 55 seconds** (target ≈ 3 minutes).

---

## 6. Features demonstrated (by scene)

| Scene | Content shown |
|-------|----------------|
| 1 Intro | Homepage hero, product framing, allowlisted demos |
| 2 Investigation | New Investigation navigation + **completed Guided Demo** job Progress (`taskboard`, Mode: Guided Demo) |
| 3 Reconstruction | Progress stages including **Reconstructing: Reused** (honest reuse label) |
| 4 Validation | Simple Report metrics: **5 passed / 0 failed / 100% match** |
| 5 Reports | Simple Report → Developer Report (verified findings / observations) |
| 6 Controlled repair | **Controlled Repair Example**: Initial 60% → Final 100%, labeled controlled evaluation |
| 7 Conclusion | Homepage branding / product name |

**Evidence job:** `8307f8d9aa304926b57f91de7171bc9a` (release E2E TaskBoard Guided Demo; meta API requests = 0; reconstruction status = reused; validation 5/5).

---

## 7. Were all claims supported by actual results?

**Yes — no fabricated Muse/live success.**

| Claim | Support |
|-------|---------|
| Product investigates / reconstructs / verifies | UI + completed job stages |
| Guided Demo, not live Muse in this recording | Narration + on-screen **Mode: Guided Demo**; release docs |
| Reconstruction reused (not live-generated in video) | On-screen **Reused** + narration |
| 5/5 / 100% on tested scenarios | Simple Report metrics; score scoped to tested cases in narration |
| Controlled repair is fault injection | Controlled Repair Example panel + narration; separate from open job |
| No paid Meta calls during recording | Recording only navigates UI; no investigation launch / Muse start |

Sources: `docs/FINAL_RELEASE_READINESS.md`, `docs/DEMO_SCRIPT.md`, live API job `8307f8d9…`, `/api/demo/controlled-repair`.

---

## 8. Final MP4 location

`demo/reversex_demo.mp4`  
Absolute: `C:\Users\sohit\Downloads\ReverseX_Engineer_Phase1a_Starter\reversex-engineer-starter\demo\reversex_demo.mp4`

---

## 9. Ready for review?

**Yes**, for local review. Not uploaded, not pushed, not merged.

### Deliverables checklist

| File | Present |
|------|---------|
| `demo/reversex_demo.mp4` | Yes |
| `demo/demo_narration_script.md` | Yes |
| `demo/demo_subtitles.srt` | Yes |
| `demo/VIDEO_PRODUCTION_REPORT.md` | Yes |

### Production pipeline (reproducible)

1. `python demo/scripts/generate_narration.py` — TTS + SRT + timeline  
2. `python demo/scripts/record_demo.py` — Playwright 1080p WebM scenes  
3. `python demo/scripts/assemble_video.py` — FFmpeg scene mux, concat, burn-in subs  

FFmpeg binary used: imageio-ffmpeg bundle (`ffmpeg-win-x86_64-v9.0.2.exe`). Winget also installed Gyan.FFmpeg system-wide.

### QA performed

- FFmpeg stream probe (1920×1080 H.264 + AAC)
- Duration check (~2:55)
- Volume detect (audible)
- Frame sampling across all seven scenes (homepage, Progress Guided Demo/Reused, Simple 5/5, Developer findings, Controlled Repair 60%→100%, close)
- Secret scan on script/SRT (no API keys / bearer tokens)
- Honesty: Guided Demo + reused reconstruction + controlled fault-injection labeled on screen and in narration

### Known limitations (honest)

- Scene 2 shows New Investigation only briefly before opening the verified job (intentional: avoid launching paid/live Muse).
- No copyrighted background music was added.
- Soft-subtitle track is not a separate MP4 subtitle stream; captions are burned in + provided as `.srt`.
- Video bitrate is moderate (~0.6 Mb/s); fine for review; re-encode with lower CRF if a higher visual bitrate is needed for projection.
