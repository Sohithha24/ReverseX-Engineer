# Custom Application URL Investigation — Implementation Report

**Branch:** `ui/hackathon-redesign`  
**Date:** 2026-11-03  
**Scope:** Backend allowlist + feature-focused investigation + frontend URL workflow + ContactPad fixture  

---

## 1. Does URL entry work?

**Yes — for allowlisted local origins only.**

Users can enter an application URL and feature on **New Investigation → Investigate your application**. The backend:

1. Normalizes and validates the URL (http, `127.0.0.1`, approved investigation ports, no credentials).
2. Resolves it through `ORIGIN_ALLOWLIST` (not trusting the string alone).
3. Starts a real Playwright investigation against that origin.
4. Writes the selected **feature** into the investigation report and Muse system prompt.
5. Produces EvidenceGraph / Simple / Developer report artifacts from recorded observations.

**Verified end-to-end (no Meta calls):** ContactPad job `73f52386506044559a3fb99711629903`

- URL: `http://127.0.0.1:8005/`
- Feature: `Submit a contact message and view confirmation`
- Goal: `understand`
- Status: `completed`
- Investigation stage executed with browser events; reconstruction/validation correctly **skipped** (not fabricated)

---

## 2. Exactly which URLs are supported?

| Origin | App | Investigation | Independent validation oracle |
|--------|-----|---------------|-------------------------------|
| `http://127.0.0.1:8001` | TaskBoard | Yes | Yes (`taskboard` suite) |
| `http://127.0.0.1:8003` | MiniCalc | Yes | Yes (`calculator` suite) |
| `http://127.0.0.1:8005` | ContactPad | Yes | **No** (honestly unavailable) |

Also:

- Browser executor may touch reconstruction preview `http://127.0.0.1:8002` during **validation of fixtures only** (not user investigation entry).
- Paths/queries on an approved origin are allowed after origin authorization (e.g. `http://127.0.0.1:8005/`).
- **Not supported:** `localhost`, LAN IPs, `https://`, public sites, credential URLs, unlisted ports, fragments.

---

## 3. How targets are approved

Authorization is **backend-managed**:

1. `INVESTIGATION_PORTS` / `ORIGIN_ALLOWLIST` in `reversex/targets.py`
2. `resolve_authorized_application()` maps URL → registered `AppTarget`
3. API `POST /api/targets/resolve` and `POST /api/investigations` both call that resolver
4. Playwright `SafeBrowser` enforces the approved origin on navigation **and** every subsequent request via route filtering

User-supplied URL strings never become allowlist entries by themselves.

---

## 4. Does feature-specific investigation work?

**Yes (scripted path verified; Muse path wired but unpaid/unverified in this run).**

- `feature` is required for meaningful custom investigation (UI prompts for it).
- Stored on the job (`feature`, `application_url`) and investigation report.
- For ContactPad / custom allowlisted apps, Muse system prompt is built with `generic_muse_system(feature)`.
- For TaskBoard/MiniCalc, the fixture Muse brief is retained and an **ADDITIONAL FOCUS** line is appended.
- Guided Demo for ContactPad uses `scripted_generic_decision` focused on visible form controls (not TaskBoard/MiniCalc oracles).

If controls related to the feature cannot be exercised, objectives may remain unsupported and the job status becomes `incomplete` rather than inventing success.

---

## 5. Are unfamiliar applications supported?

**Partially — yes for allowlisted unfamiliar local apps.**

ContactPad is intentionally **not** a TaskBoard/MiniCalc copy. ReverseX uses:

- Generic visible control discovery (`button`, `input`, `textarea`, submit inputs)
- Generic scripted exploration
- Generic observation objectives (`feature_controls_observed`, `feature_interaction_attempted`, `page_response_observed`)

Limitations:

- Only allowlisted ports/apps
- Interaction policy still limited (no arbitrary DOM actions, no file/password inputs)
- Apps using unsupported widgets may yield incomplete investigations with explicit notes

---

## 6. Does reconstruction work for custom apps?

**Partial.**

| Goal | Behavior |
|------|----------|
| `understand` | Reconstruction **skipped** (honest) |
| `understand_and_reconstruct` | Spec + reconstruction stages run; **no TaskBoard recon reuse** for custom apps |

Reconstruction quality for ContactPad depends on Muse reconstruction (paid) or local reconstruct path — not claimed fully proven here without Meta spend.

---

## 7. Does independent validation work for custom applications?

**No fabricated scores.**

ContactPad / allowlisted custom targets set:

- `validation_suite = None`
- `supports_independent_validation = False`

When reconstruction is requested, validation is reported as **`unavailable`** with an explicit note that existing oracles are fixture-specific. Match rate is not invented.

TaskBoard and MiniCalc keep their existing differential validation suites.

---

## 8. Incomplete capabilities

- Arbitrary public / unlisted local URLs
- Permanent investigation history list
- Independent validation oracles for arbitrary features
- Live Muse Spark custom-app path **not exercised with paid Meta calls** in this implementation pass (code path exists; Guided Demo verified)
- Richer interaction surface (drag/drop, canvas, etc.)
- Display name polish still sometimes shows raw `contactpad` id in report header depending on verification payload

---

## 9. Actual security tests

| Test | Result |
|------|--------|
| Reject `https://example.com` resolve/create | Pass (`400`) |
| Reject `http://localhost:8005` | Pass |
| Reject port `8010` / `9999` | Pass |
| Reject credential URLs | Pass |
| Reject cross-origin browser navigation (8005 vs 8003) | Pass |
| Reconstruction preview `:8002` still valid when approved for validation | Pass |
| pytest `tests/test_custom_application.py` | Pass |
| ContactPad browser e2e (`test_scripted_contactpad_investigation_end_to_end`) | Pass |

---

## 10. Regression results

| Check | Result |
|-------|--------|
| `python -m pytest` | **114 passed, 2 skipped** |
| Frontend `tsc -b && vite build` | **Pass** |
| ContactPad scripted browser e2e | **Pass** |
| API ContactPad understand-only job | **Pass** (`73f52386…`) |
| Existing Evidence Verification / reports / controlled repair | Preserved (suite green) |

Live Muse custom investigation: **not verified** (no paid Meta calls).

---

## 11. Screenshots

| File | Content |
|------|---------|
| `docs/custom-app-screenshots/01-home-allowlisted-urls.png` | Home copy mentions allowlisted URLs + ContactPad |
| `docs/custom-app-screenshots/02-contactpad-results-loading-or-partial.png` | Results for ContactPad job |
| `docs/custom-app-screenshots/03-setup-custom-url.png` | URL + feature investigation setup |

---

## 12. How to use the new feature

1. Serve ContactPad (or another allowlisted fixture):

```powershell
.\.venv\Scripts\python.exe -m http.server 8005 --bind 127.0.0.1 --directory fixtures\contactpad
```

2. Ensure API + frontend are running (`8000`, `5173`).
3. Open **http://127.0.0.1:5173** → **New Investigation**.
4. Under **Investigate your application**:
   - Application URL: `http://127.0.0.1:8005/`
   - Feature: e.g. `Submit a contact message and view confirmation`
   - Goal: **Understand** (safest) or **Understand and reconstruct**
5. Optionally click **Check if URL is approved**.
6. Choose **Guided Demo** (no Muse) or **Fresh AI Investigation** (Meta credits).
7. **Launch investigation** → follow **Progress** → open **Results**.

API equivalent:

```http
POST /api/investigations
{
  "mode": "scripted",
  "application_url": "http://127.0.0.1:8005/",
  "feature": "Submit a contact message and view confirmation",
  "investigation_goal": "understand",
  "max_actions": 12,
  "reuse_reconstruction": false,
  "pipeline": "investigate_only"
}
```

---

## Capability matrix (honest)

| Capability | Status |
|------------|--------|
| Allowlisted URL entry reaches real investigation backend | **Fully working** (tested) |
| Feature string passed into investigation artifacts / Muse brief | **Fully working** (tested scripted; Muse wired) |
| Browser observations for ContactPad | **Fully working** (tested) |
| Evidence-grounded Simple/Developer reports | **Working** (partial availability when validation skipped) |
| Independent validation for custom apps | **Unavailable (by design)** |
| Reconstruction for custom apps | **Partial** (pipeline present; not Meta-proven here) |
| Unrestricted public URLs | **Not implemented** |

---

## Key files

- `reversex/targets.py` — allowlist, resolve, ContactPad target, feature Muse briefs  
- `reversex/browser.py` — hardened local origin/port checks  
- `reversex/run.py` — feature-aware explore + generic scripted path  
- `reversex/orchestrate.py` — understand-only skips; validation unavailable for custom  
- `reversex/api.py` — `application_url`, `feature`, `investigation_goal`, `/api/targets/resolve`  
- `fixtures/contactpad/*` — third authorized local app  
- `frontend/src/pages/SetupPage.tsx` — URL-first investigation UI  
- `tests/test_custom_application.py` — security + e2e coverage  
