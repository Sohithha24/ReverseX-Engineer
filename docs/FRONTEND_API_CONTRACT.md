# ReverseX Engineer — Frontend API Contract (Phase 4A)

Local-only FastAPI backend for Lovable / Vite frontends. **Not authenticated. Do not expose publicly.**

## API base URL

```
http://127.0.0.1:8000
```

Start backend:

```powershell
cd reversex-engineer-starter
.\.venv\Scripts\Activate.ps1
python -m uvicorn reversex.api:app --host 127.0.0.1 --port 8000
```

CORS allowlist: `http://localhost:5173`, `http://127.0.0.1:5173`.

---

## Investigation status values

| Status | Meaning |
|--------|---------|
| `queued` | Accepted; worker not started |
| `investigating` | Browser investigation running |
| `specifying` | Behavioral specification generation |
| `reconstructing` | Reconstruction reuse or Meta generation |
| `validating` | Docker-isolated differential validation |
| `completed` | Pipeline finished successfully for executed stages |
| `incomplete` | Finished with incomplete/blocked validation or partial coverage |
| `failed` | Stage exception; partial artifacts preserved |

Statuses are written only when the corresponding backend stage actually runs.

---

## Error format

FastAPI default:

```json
{ "detail": "Investigation not found" }
```

Validation / conflict examples:

* `400` — invalid investigation id
* `404` — unknown investigation / missing artifact
* `409` — another investigation is already active
* `422` — request body failed Pydantic validation

---

## Endpoints

### `GET /health`

Response fields:

* `status` — `"ok"`
* `phase` — `"4a"`
* `reconstruction_available` — whether Phase 2 reconstruction files exist
* `validation_available` — whether Phase 3 validation artifact exists
* `docker_required_for_validation_preview` — `true`
* `public` — `false`

### `POST /api/investigations`

Request (`extra` fields forbidden):

```json
{
  "mode": "scripted",
  "pipeline": "full",
  "reuse_reconstruction": true,
  "max_actions": 10,
  "target_id": "taskboard"
}
```

`target_id` (optional, default `taskboard`): authorized local fixture to investigate.

| Value | Origin | Notes |
|-------|--------|-------|
| `taskboard` | `http://127.0.0.1:8001` | Original Phase 1–5A TaskBoard fixture (`sample_app/`) |
| `calculator` | `http://127.0.0.1:8003` | Phase 5B MiniCalc fixture (`fixtures/calculator/`) |

Calculator runs must set `reuse_reconstruction: false`. TaskBoard Phase 2 reuse is never applied to calculator.

### `GET /api/targets`

Returns the allowlisted applications (`taskboard`, `calculator`) with origin and description. Arbitrary public URLs are not accepted.

### `GET /api/investigations/{id}/repair`

Returns `repair/repair_report.json` when bounded repair actually ran after validation failures.

### `GET /api/demo/controlled-repair`

Read-only Controlled Repair Evaluation artifact (fault-injected copy). Not an organic reconstruction failure.

| Field | Type | Notes |
|-------|------|-------|
| `mode` | `"scripted"` \| `"muse"` | Required semantics; default `scripted` |
| `pipeline` | `"investigate_only"` \| `"full"` | Default `full` |
| `reuse_reconstruction` | bool | Default `true` (does not overwrite Phase 2 originals) |
| `max_actions` | int 1–20 | Browser action budget |

Response (`InvestigationSummary`):

```json
{
  "id": "c5321c039d1b4e46914fe2873fccad19",
  "status": "queued",
  "mode": "scripted",
  "pipeline": "investigate_only",
  "queued_at": "2026-10-28T04:02:20.138638+00:00",
  "updated_at": "2026-10-28T04:02:20.138638+00:00",
  "stages": {},
  "errors": [],
  "artifacts": { "root": "artifacts/c5321c039d1b4e46914fe2873fccad19/" },
  "meta_api_requests_total": null,
  "error": null
}
```

> Example above is from a real local create call (ids/timestamps will differ).

### `GET /api/investigations/{id}`

Returns live or disk-backed `InvestigationSummary`.

Id format: **32 hex characters** only.

### `GET /api/investigations/{id}/events`

Returns investigation browser events from `investigation/report.json` when present.

```json
{
  "id": "...",
  "status": "completed",
  "investigation_status": "completed",
  "events": [ { "step": 1, "decision": { "action": "fill" }, "status": "ok" } ],
  "objectives": {}
}
```

> Truncated example structure — not a full dump.

### `GET /api/investigations/{id}/results`

Aggregated stage outcomes + validation summary (no absolute host paths).

```json
{
  "id": "cccccccccccccccccccccccccccccccc",
  "status": "completed",
  "stages": {
    "investigation": { "executed": true, "status": "completed" },
    "specification": { "executed": true, "status": "frozen" },
    "reconstruction": { "executed": true, "status": "reused" },
    "validation": {
      "executed": true,
      "status": "completed",
      "passed": 5,
      "failed": 0,
      "behavioral_match_rate_percent": 100.0
    }
  },
  "validation": {
    "present": true,
    "passed": 5,
    "failed": 0,
    "invalid": 0,
    "total_valid": 5,
    "behavioral_match_rate_percent": 100.0,
    "isolation_status": "running"
  }
}
```

> Example adapted from a verified local full-pipeline run (`reuse_reconstruction=true`, `mode=scripted`).

### `GET /api/investigations/{id}/evidence-graph`

Returns `EvidenceGraph`:

```json
{
  "project": "ReverseX Engineer",
  "version": "1",
  "generated_at": "2026-10-28T04:00:00+00:00",
  "source_artifacts": ["artifacts/.../report.json"],
  "nodes": [
    {
      "id": "investigation:phase1b",
      "type": "investigation",
      "description": "Investigation mode=muse status=completed",
      "evidence_ref": "artifacts/phase1b/report.json",
      "status": "completed",
      "timestamp": null,
      "metadata": {}
    }
  ],
  "edges": [
    {
      "id": "e1",
      "type": "observed_during",
      "source": "action:step-1",
      "target": "investigation:phase1b",
      "description": "Action recorded during investigation"
    }
  ]
}
```

Node types: `investigation`, `action`, `observation`, `requirement`, `hypothesis`, `reconstruction`, `artifact`, `validation_test`, `validation_outcome`.

Edge types: `observed_during`, `supports`, `implemented_by`, `validated_by`, `derived_from`, `produced`.

### `GET /api/investigations/{id}/report`

Returns `final_report.json` when written; otherwise a live partial summary.

### `GET /api/investigations/{id}/validation`

Returns `validation_results.json` for the job (404 if not produced yet).

### `GET /api/investigations/{id}/screenshots`

Lists allowlisted PNG screenshots for the job.

### `GET /api/investigations/{id}/screenshots/{filename}`

Serves one PNG. Filename must match `^[a-zA-Z0-9][a-zA-Z0-9_-]{0,120}\.png$` and exist under `validation/screenshots/` or `investigation/`.

### `GET /api/demo/evidence-graph`

Read-only graph built from preserved Phase 1B–3 artifacts (no new model calls). Useful for Lovable UI scaffolding before a live job finishes.

---

## Artifact references

API responses use **safe relative artifact keys**, never host absolute paths, for example:

* `artifacts/{id}/`
* `{id}/investigation/report.json`
* `{id}/specification/behavior_spec.frozen.json`
* `{id}/reconstructed-app/`
* `{id}/validation/validation_results.json`
* `{id}/evidence_graph.json`
* `{id}/final_report.json`

Screenshots remain under `{id}/validation/screenshots/` on disk; frontend should request report/results JSON rather than arbitrary filesystem browsing.

---

## Lovable connection notes

1. Point the frontend base URL to `http://127.0.0.1:8000`.
2. Poll `GET /api/investigations/{id}` every 1–2s while status is active.
3. Render EvidenceGraph from `/evidence-graph` or `/api/demo/evidence-graph`.
4. Do not embed `MODEL_API_KEY` in the frontend.
5. Hosted Lovable sites cannot reach localhost until the backend is securely deployed.
