# IT-Tools Compatibility Report — ReverseX Engineer

**Date:** 2026-11-04  
**Branch:** `ui/hackathon-redesign`  
**Phase:** Infrastructure + compatibility only  
**Meta Muse Spark calls:** **None**  
**Reconstruction generated:** **No**  
**IT-Tools source modified:** **No**

Related: `docs/IT_TOOLS_HOLDOUT_PLAN.md`, `docs/audit-evidence-it-tools/`

---

## 1. Third-party application details

| Field | Value |
|-------|-------|
| Application | IT-Tools |
| Upstream | https://github.com/CorentinTh/it-tools |
| Image | `ghcr.io/corentinth/it-tools:2024.10.22-7ca5933` |
| Image digest | `sha256:8b8128748339583ca951af03dfe02a9a4d7363f61a216226fc28030731a5a61f` |
| Feature of interest | Base64 text encoding and decoding |
| Tool route observed | `/base64-string-converter` |
| Nature | Unmodified third-party SPA (Vue), not a ReverseX synthetic fixture |

---

## 2. Docker setup

| Field | Value |
|-------|-------|
| Container name | `reversex-it-tools` |
| Container ID | `5b17b640f1ae8a889d9b007e7c38eb03d0e7ea54ad0af88790bc407cd4fc5213` |
| Publish | `127.0.0.1:8010->80/tcp` only |
| Privileged | `false` |
| Host binds / ReverseX mount | **none** (`Binds=null`) |
| Caps | dropped ALL; added `CHOWN`, `SETUID`, `SETGID`, `NET_BIND_SERVICE` |
| `no-new-privileges` | enabled |
| Startup | HTTP **200** on `http://127.0.0.1:8010/` |

Restart policy: `unless-stopped`.

---

## 3. Exact local URL

**Origin approved for ReverseX:** `http://127.0.0.1:8010/`

**Recommended start URL for a future Base64 investigation** (same allowlisted origin, deep path):

`http://127.0.0.1:8010/base64-string-converter`

Reason: SafeBrowser cannot click `<a>` router links on the home page; starting at `/` likely cannot reach the Base64 tool with current actions.

---

## 4. Target approval status

Registered in ReverseX via existing mechanism (`reversex/targets.py`):

- Added port **8010** to `INVESTIGATION_PORTS` and `ALLOWED_LOCAL_PORTS`
- Added `AppTarget` id `it-tools`, origin `http://127.0.0.1:8010`, `kind=allowlisted_custom`
- `validation_suite=None`, `supports_independent_validation=False`, `supports_reconstruction_reuse=False`
- Placeholder `fixtures/it-tools-placeholder/` contains **only a README** — not IT-Tools source

Live API checks:

| URL | Result |
|-----|--------|
| `http://127.0.0.1:8010/` + feature | **Approved** → `it-tools` |
| `http://127.0.0.1:8010/base64-string-converter` | **Approved** |
| `https://example.com/` | Rejected |
| `http://127.0.0.1:9999/` | Rejected |
| `http://localhost:8010/` | Rejected |
| `https://it-tools.tech/` | Rejected |

Security restrictions were **not** weakened (no public sites, no `localhost` alias, no open LAN).

---

## 5. Browser compatibility findings

Evaluator-controlled Playwright probe (`scripts/it_tools_compatibility_probe.py`) + SafeBrowser session:

| Check | Result |
|-------|--------|
| Application loads | **Yes** (title: IT Tools - Handy online tools for developers) |
| Console/page errors on probe | None recorded |
| Base64 feature reachable by evaluator | **Yes** at `/base64-string-converter` |
| Home navigation via SafeBrowser clicks | **Poor** — tools are mostly `<a>` links; SafeBrowser only clicks `button` / submit inputs |
| Search on home | Exposed as a **button** (“Search Ctrl+K”), not a fillable search `input` in the closed state |
| Base64 controls when on tool page | **Yes** — textareas + Copy buttons discoverable |
| Encode works (evaluator) | **Yes** — textarea `input_value` updates reactively |
| Decode invalid input | Decode textarea stayed empty for `!!!!` (no error string observed there) |

Screenshots: `docs/audit-evidence-it-tools/01-home.png`, `03-base64-feature.png`, `04-base64-after-fill.png`.

---

## 6. Feature navigation findings

- Home visible text **mentions** “Base64 string encoder/decoder”.
- Reaching the tool from home requires link navigation or search UX that ReverseX’s executor does not currently support as first-class actions.
- Deep-linking within the approved origin **is** allowed by `resolve_authorized_application` (path preserved after origin auth).

---

## 7. Supported browser actions (ReverseX)

From `SafeBrowser` / contracts (unchanged):

- `observe`, `click`, `fill`, `reload`, `stop`
- Discoverable: `button`, `input`, `textarea`, `select` (max 40)
- Fillable: text-like inputs/textareas only (not password/file/checkbox/…)
- Clickable: visible buttons / submit inputs only

---

## 8. Unsupported / limited interactions

| Limitation | Impact on IT-Tools Base64 |
|------------|---------------------------|
| Cannot click `<a>` | Hard to navigate from home to the tool |
| Search often behind a button / modal | May not expose a fillable search field immediately |
| `visible_text` = `body.inner_text()[:2000]` | **Does not include textarea values** after encode/decode |
| Toggle switches (e.g. “Encode URL safe”) | Not reliably represented as button/input |
| No select of “read output textarea value” action | Muse cannot reliably “see” Base64 output via snapshots |
| Screenshots exist but verification predicates use text/events | Confirmation of encoding may remain unverified even if UI shows it |

**Confirmed with SafeBrowser:** after filling “Hello ReverseX”, textarea values were `['Hello ReverseX','SGVsbG8gUmV2ZXJzZVg=',…]` but `visible_text` contained **neither** the plaintext nor the Base64 string.

This is an observation-architecture limitation, **not** fixed in this phase (no engine change to force Muse success).

---

## 9. Feature-description integration

`resolve_authorized_application(..., feature="Base64 text encoding and decoding")`:

- Sets `feature_label` to that string
- Builds Muse system prompt via `generic_muse_system(feature)` containing the PRIMARY OBJECTIVE line with that feature
- Stored on investigation jobs the same way as ContactPad

**Claim limit:** Wiring is verified. **Muse following** that goal is **not** claimed until a live Muse investigation is authorized and run.

---

## 10. Reconstruction feasibility

| Area | Assessment |
|------|------------|
| From observations only | Spec/recon pipeline expects observation-backed requirements; missing textarea values in snapshots **undercuts** high-quality Base64 specs |
| Copying IT-Tools source | **Forbidden / not done** — placeholder fixture has no app source |
| Target-specific shortcut | **Not implemented** |
| Generic recon for SPA Base64 | Possible only as a small generated HTML/JS app from a frozen spec — quality depends on observed evidence quality |
| Preview | Existing preview still bound to allowlisted local ports; IT-Tools itself is not the reconstruction |

**Verdict:** Reconstruction may be *attemptable* later without copying source, but **should not be expected to succeed** given current observation gaps. Do not claim readiness for fair reconstruction evaluation yet.

---

## 11. Validation limitations

- `it-tools` has **no** `validation_suite` and `supports_independent_validation=False`
- TaskBoard/MiniCalc oracles must **not** be treated as applying to IT-Tools
- Independent holdout testing is feasible **outside** ReverseX’s built-in oracle (evaluator Playwright comparing textarea values) — see `docs/IT_TOOLS_HOLDOUT_PLAN.md`
- No passing score assigned

---

## 12. Security test results

| Test | Result |
|------|--------|
| Local origin approval `:8010` | Pass |
| Unapproved port `:8011` / `:9999` | Reject |
| Public HTTPS URLs | Reject |
| `localhost` alias | Reject |
| Cross-origin browser target mismatch | Reject (existing `validate_target`) |
| Container not privileged | Pass |
| Bound to 127.0.0.1 only | Pass |
| No ReverseX source mount into container | Pass |
| Route filter still origin-locked in SafeBrowser | Architecture preserved |

**No unresolved security blocker** for running the allowlisted local container. Restrictions were not weakened for convenience.

---

## 13. Regression results

| Check | Result |
|-------|--------|
| TaskBoard / MiniCalc / ContactPad still registered | Pass |
| IT-Tools added to `/api/targets` | Pass |
| URL resolve flow | Pass |
| ContactPad job `fe8ef026…` report.json untouched | Pass (mtime 2026-11-04 04:04:26Z; hash unchanged in this session’s check) |
| Full pytest | **127 passed, 2 skipped** |
| Frontend `tsc -b` + production build | Pass |
| Paid Meta API | **Not used** |

Skipped tests: browser integration (port/env conditions) — unchanged class of skips.

---

## 14. Screenshots / evidence

| File | Description |
|------|-------------|
| `docs/audit-evidence-it-tools/01-home.png` | IT-Tools home |
| `docs/audit-evidence-it-tools/03-base64-feature.png` | Base64 tool page |
| `docs/audit-evidence-it-tools/04-base64-after-fill.png` | After evaluator fill (encoded output visible in UI) |
| `docs/audit-evidence-it-tools/compatibility_probe.json` | Structured probe record |

---

## 15. Readiness for one live Muse investigation

### Ready (with bounds)

- IT-Tools is running locally and approved.
- Feature string can be passed into the Muse investigation context.
- Starting URL should be **`http://127.0.0.1:8010/base64-string-converter`** (Understand goal recommended).
- Budget should be bounded; no reconstruction/validation expected to be meaningful yet.
- Evaluator must not paste holdout answers into the Muse prompt.

### Not ready / conditional risks

- Starting at `/` is likely a **navigation dead-end** for Muse under current click policy.
- Even on the tool page, Muse may **fill** inputs but **fail to observe** encoded/decoded values via `visible_text`, so Simple/Developer verified behavioral findings about outputs may be weak or missing unless the engine later records textarea values (out of scope here).
- Independent validation oracle: **unavailable**.
- Fair reconstruction evaluation: **not ready**.

### Recommendation

**Conditionally ready for one bounded Understand-only Muse investigation** against the Base64 deep URL, as a **compatibility stress test**, not as a claim of successful Base64 understanding or reconstruction.

Do **not** authorize reconstruction/validation pipeline spend until observation of textarea outputs is addressed or explicitly accepted as a known failure mode.

---

## ReverseX architecture notes (inspection summary)

| Topic | Mechanism |
|-------|-----------|
| Target registration | `TARGETS` + `ORIGIN_ALLOWLIST` in `targets.py` |
| Custom URL validation | `normalize_origin` + allowlist resolve; API `/api/targets/resolve` |
| Browser actions | `SafeBrowser.act` — observe/click/fill/reload/stop |
| Feature → Muse | `resolve_authorized_application` → `generic_muse_system(feature)` for custom targets |
| Navigation restrictions | Origin equality + allowlisted ports + request route abort |
| Observations | Event before/after snapshots (`visible_text`, element labels) |
| Custom recon/validation | Disabled unless suite configured; ContactPad/IT-Tools = no independent validation |
| Reports | Shared `VerifiedResults` → Simple/Developer markdown + UI |

---

*End of compatibility report. No Muse calls performed.*
