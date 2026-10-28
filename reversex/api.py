"""Local-only development API. Not authenticated / not safe to expose publicly."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from reversex.evidence_graph import EvidenceGraph, build_evidence_graph, export_evidence_graph
from reversex.orchestrate import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts'
JOB_ID_RE = re.compile(r'^[a-f0-9]{32}$')
SCREENSHOT_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,120}\.png$')
ALLOWED_SCREENSHOT_DIRS = (
    ('validation', 'screenshots'),
    ('investigation',),
)

app = FastAPI(
    title='ReverseX Engineer local development API',
    version='0.4.0',
    description='Phase 4A orchestration API for authorized local demos only.',
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    allow_credentials=False,
    allow_methods=['GET', 'POST'],
    allow_headers=['Content-Type'],
)

pool = ThreadPoolExecutor(max_workers=1)
_jobs: dict[str, dict[str, Any]] = {}
_lock = Lock()

ACTIVE = {
    'queued', 'investigating', 'specifying', 'reconstructing', 'validating',
}


class CreateInvestigation(BaseModel):
    model_config = ConfigDict(extra='forbid')

    mode: Literal['scripted', 'muse'] = 'scripted'
    pipeline: Literal['investigate_only', 'full'] = 'full'
    reuse_reconstruction: bool = True
    max_actions: int = Field(default=10, ge=1, le=20)

    @field_validator('mode')
    @classmethod
    def mode_ok(cls, value: str) -> str:
        if value not in ('scripted', 'muse'):
            raise ValueError('mode must be scripted or muse')
        return value


class InvestigationSummary(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    status: str
    mode: str | None = None
    pipeline: str | None = None
    queued_at: str | None = None
    updated_at: str | None = None
    stages: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    meta_api_requests_total: int | None = None
    error: str | None = None


def _require_job_id(job_id: str) -> str:
    if not JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=400, detail='Invalid investigation id')
    return job_id


def _get_job(job_id: str) -> dict[str, Any]:
    _require_job_id(job_id)
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            # Allow reading finalized jobs from disk after process restart.
            disk = ARTIFACTS / job_id / 'final_report.json'
            if disk.is_file():
                data = json.loads(disk.read_text(encoding='utf-8'))
                return data
            raise HTTPException(status_code=404, detail='Investigation not found')
        return dict(job)


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    """Strip non-serializable / sensitive fields for API responses."""
    allowed = {
        'id', 'status', 'mode', 'pipeline', 'updated_at', 'stages', 'errors',
        'artifacts', 'meta_api_requests_total', 'error', 'queued_at',
    }
    return {k: job[k] for k in allowed if k in job}


def _read_json_artifact(job_id: str, *parts: str) -> Any:
    _require_job_id(job_id)
    root = (ARTIFACTS / job_id).resolve()
    path = root.joinpath(*parts).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Invalid artifact path') from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail='Artifact not found')
    return json.loads(path.read_text(encoding='utf-8'))


@app.get('/health')
def health():
    recon = (ARTIFACTS / 'phase2' / 'reconstructed-app' / 'index.html').is_file()
    return {
        'status': 'ok',
        'phase': '4a',
        'reconstruction_available': recon,
        'validation_available': (ARTIFACTS / 'phase3' / 'validation_results.json').is_file(),
        'docker_required_for_validation_preview': True,
        'public': False,
        'note': 'Local-only API. Not authenticated.',
    }


@app.post('/api/investigations', response_model=InvestigationSummary)
def create_investigation(payload: CreateInvestigation):
    with _lock:
        if any(job.get('status') in ACTIVE for job in _jobs.values()):
            raise HTTPException(status_code=409, detail='Only one investigation may run at a time')
        job_id = uuid4().hex
        job = {
            'id': job_id,
            'status': 'queued',
            'mode': payload.mode,
            'pipeline': payload.pipeline,
            'queued_at': None,
            'stages': {},
            'errors': [],
            'artifacts': {'root': f'artifacts/{job_id}/'},
        }
        from datetime import datetime, timezone
        job['queued_at'] = datetime.now(timezone.utc).isoformat()
        job['updated_at'] = job['queued_at']
        _jobs[job_id] = job

    def work():
        def status_cb(status, payload):
            with _lock:
                current = _jobs.get(job_id)
                if not current:
                    return
                current['status'] = status
                current['updated_at'] = payload.get('updated_at')
                if 'stages' in payload:
                    current['stages'] = payload['stages']
                if 'errors' in payload:
                    current['errors'] = payload['errors']

        try:
            summary = run_pipeline(
                job_id=job_id,
                mode=payload.mode,
                pipeline=payload.pipeline,
                reuse_reconstruction=payload.reuse_reconstruction,
                max_actions=payload.max_actions,
                artifacts_root=ARTIFACTS,
                status_cb=status_cb,
            )
            with _lock:
                _jobs[job_id].update(summary)
        except Exception as exc:
            with _lock:
                _jobs[job_id].update({
                    'status': 'failed',
                    'error': str(exc)[:300],
                    'errors': [str(exc)[:300]],
                })

    pool.submit(work)
    return InvestigationSummary.model_validate(_public_job(_jobs[job_id]))


@app.get('/api/investigations/{job_id}', response_model=InvestigationSummary)
def get_investigation(job_id: str):
    return InvestigationSummary.model_validate(_public_job(_get_job(job_id)))


@app.get('/api/investigations/{job_id}/events')
def get_events(job_id: str):
    job = _get_job(job_id)
    try:
        report = _read_json_artifact(job_id, 'investigation', 'report.json')
    except HTTPException:
        return {
            'id': job_id,
            'status': job.get('status'),
            'events': [],
            'note': 'Investigation events not available yet',
        }
    return {
        'id': job_id,
        'status': job.get('status'),
        'investigation_status': report.get('status'),
        'events': report.get('events') or [],
        'objectives': report.get('objectives') or {},
    }


@app.get('/api/investigations/{job_id}/results')
def get_results(job_id: str):
    job = _get_job(job_id)
    validation = None
    specification = None
    try:
        validation = _read_json_artifact(job_id, 'validation', 'validation_results.json')
    except HTTPException:
        pass
    try:
        specification = _read_json_artifact(job_id, 'specification', 'behavior_spec.frozen.json')
    except HTTPException:
        pass
    return {
        'id': job_id,
        'status': job.get('status'),
        'stages': job.get('stages') or {},
        'errors': job.get('errors') or [],
        'specification_present': specification is not None,
        'validation': {
            'present': validation is not None,
            'passed': (validation or {}).get('passed'),
            'failed': (validation or {}).get('failed'),
            'invalid': (validation or {}).get('invalid'),
            'total_valid': (validation or {}).get('total_valid'),
            'behavioral_match_rate_percent': (validation or {}).get('behavioral_match_rate_percent'),
            'isolation_status': ((validation or {}).get('isolation') or {}).get('status'),
        } if validation else {'present': False},
        'reconstruction_reused_or_generated': (job.get('stages') or {}).get('reconstruction'),
    }


@app.get('/api/investigations/{job_id}/validation')
def get_validation(job_id: str):
    """Return the machine-readable validation_results.json when present."""
    _get_job(job_id)
    try:
        return _read_json_artifact(job_id, 'validation', 'validation_results.json')
    except HTTPException:
        raise HTTPException(status_code=404, detail='Validation results not available yet')


@app.get('/api/investigations/{job_id}/evidence-graph', response_model=EvidenceGraph)
def get_evidence_graph(job_id: str):
    _require_job_id(job_id)
    path = ARTIFACTS / job_id / 'evidence_graph.json'
    if path.is_file():
        return EvidenceGraph.model_validate_json(path.read_text(encoding='utf-8'))
    # Build on demand from available job artifacts only (no invented nodes).
    graph = build_evidence_graph(
        root=ROOT,
        investigation_report=ARTIFACTS / job_id / 'investigation' / 'report.json',
        behavior_spec=ARTIFACTS / job_id / 'specification' / 'behavior_spec.frozen.json',
        reconstruction_dir=ARTIFACTS / job_id / 'reconstructed-app',
        validation_results=ARTIFACTS / job_id / 'validation' / 'validation_results.json',
    )
    if not graph.nodes:
        raise HTTPException(status_code=404, detail='Evidence graph not available yet')
    export_evidence_graph(graph, path)
    return graph


@app.get('/api/investigations/{job_id}/report')
def get_report(job_id: str):
    job = _get_job(job_id)
    try:
        final = _read_json_artifact(job_id, 'final_report.json')
        return final
    except HTTPException:
        return {
            'id': job_id,
            'status': job.get('status'),
            'stages': job.get('stages') or {},
            'errors': job.get('errors') or job.get('error') and [job.get('error')] or [],
            'note': 'Final report not written yet; returning live job summary',
        }


@app.get('/api/demo/evidence-graph', response_model=EvidenceGraph)
def demo_evidence_graph():
    """Read-only graph from preserved Phase 1B–3 artifacts (no new model calls)."""
    graph = build_evidence_graph(root=ROOT)
    out = ARTIFACTS / 'phase4a' / 'evidence_graph.json'
    export_evidence_graph(graph, out)
    return graph


def _iter_job_screenshots(job_id: str) -> list[dict[str, str]]:
    _require_job_id(job_id)
    root = (ARTIFACTS / job_id).resolve()
    items: list[dict[str, str]] = []
    for parts in ALLOWED_SCREENSHOT_DIRS:
        folder = root.joinpath(*parts)
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob('*.png')):
            if not SCREENSHOT_NAME_RE.match(path.name):
                continue
            try:
                path.resolve().relative_to(root)
            except ValueError:
                continue
            rel = '/'.join((*parts, path.name))
            items.append({
                'id': path.stem,
                'filename': path.name,
                'relative_path': rel,
                'url': f'/api/investigations/{job_id}/screenshots/{path.name}',
            })
    return items


@app.get('/api/investigations/{job_id}/screenshots')
def list_screenshots(job_id: str):
    """List allowlisted PNG screenshots for a job (no arbitrary path browsing)."""
    _get_job(job_id)  # ensures id exists in memory or on disk
    return {'id': job_id, 'screenshots': _iter_job_screenshots(job_id)}


@app.get('/api/investigations/{job_id}/screenshots/{filename}')
def get_screenshot(job_id: str, filename: str):
    """Serve one allowlisted PNG under the job artifact tree only."""
    _require_job_id(job_id)
    if not SCREENSHOT_NAME_RE.match(filename):
        raise HTTPException(status_code=400, detail='Invalid screenshot filename')
    root = (ARTIFACTS / job_id).resolve()
    candidates = [
        root.joinpath(*parts, filename) for parts in ALLOWED_SCREENSHOT_DIRS
    ]
    for path in candidates:
        try:
            resolved = path.resolve()
            resolved.relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail='Invalid artifact path') from exc
        if resolved.is_file():
            return FileResponse(resolved, media_type='image/png', filename=filename)
    raise HTTPException(status_code=404, detail='Screenshot not found')
