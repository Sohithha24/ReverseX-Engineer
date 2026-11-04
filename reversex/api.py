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
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from reversex.evidence_graph import EvidenceGraph, build_evidence_graph, export_evidence_graph
from reversex.orchestrate import run_pipeline
from reversex.reporting import STATUS_HELP, STATUS_LABELS, build_report_package
from reversex.targets import (
    TARGETS,
    TargetAuthorizationError,
    list_authorized_origins,
    list_target_ids,
    resolve_authorized_application,
)
from reversex.verification import VerifiedResults, build_verified_results

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
    target_id: str | None = None
    application_url: str | None = Field(default=None, max_length=300)
    feature: str | None = Field(default=None, max_length=240)
    investigation_goal: Literal['understand', 'understand_and_reconstruct'] = 'understand_and_reconstruct'

    @field_validator('mode')
    @classmethod
    def mode_ok(cls, value: str) -> str:
        if value not in ('scripted', 'muse'):
            raise ValueError('mode must be scripted or muse')
        return value

    @field_validator('feature')
    @classmethod
    def feature_ok(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator('application_url')
    @classmethod
    def application_url_ok(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ResolveTargetRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')

    application_url: str = Field(min_length=1, max_length=300)
    feature: str | None = Field(default=None, max_length=240)


class InvestigationSummary(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    status: str
    mode: str | None = None
    pipeline: str | None = None
    target_id: str | None = None
    feature: str | None = None
    application_url: str | None = None
    investigation_goal: str | None = None
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
        'id', 'status', 'mode', 'pipeline', 'target_id', 'feature', 'application_url',
        'investigation_goal', 'updated_at', 'stages', 'errors',
        'artifacts', 'meta_api_requests_total', 'error', 'queued_at',
    }
    return {k: job[k] for k in allowed if k in job}


def _disk_job_summary(job_id: str) -> dict[str, Any] | None:
    """Load a finalized investigation summary from artifacts (survives API restart)."""
    if not JOB_ID_RE.match(job_id):
        return None
    disk = ARTIFACTS / job_id / 'final_report.json'
    if not disk.is_file():
        return None
    try:
        data = json.loads(disk.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    summary = _public_job({**data, 'id': job_id})
    summary.setdefault('id', job_id)
    return summary


def _list_investigation_summaries(*, limit: int = 40) -> list[dict[str, Any]]:
    """Merge in-memory jobs with on-disk final reports for durable history."""
    limit = max(1, min(int(limit), 100))
    by_id: dict[str, dict[str, Any]] = {}
    with _lock:
        for job_id, job in _jobs.items():
            by_id[job_id] = _public_job(job)
    if ARTIFACTS.is_dir():
        for child in ARTIFACTS.iterdir():
            if not child.is_dir() or not JOB_ID_RE.match(child.name):
                continue
            if child.name in by_id:
                continue
            summary = _disk_job_summary(child.name)
            if summary:
                by_id[child.name] = summary

    def sort_key(item: dict[str, Any]) -> str:
        return str(item.get('updated_at') or item.get('queued_at') or '')

    ordered = sorted(by_id.values(), key=sort_key, reverse=True)
    return ordered[:limit]


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
        'phase': '5c',
        'reconstruction_available': recon,
        'validation_available': (ARTIFACTS / 'phase3' / 'validation_results.json').is_file(),
        'docker_required_for_validation_preview': True,
        'public': False,
        'authorized_targets': list_target_ids(),
        'authorized_origins': [o['origin'] for o in list_authorized_origins()],
        'note': 'Local-only API. Not authenticated. Custom URLs must match the origin allowlist.',
    }


@app.get('/api/targets')
def get_targets():
    """List explicitly authorized local investigation targets only."""
    items = []
    for tid in list_target_ids():
        t = TARGETS[tid]
        items.append({
            'id': t.id,
            'label': t.label or t.id,
            'origin': t.origin,
            'description': t.feature_label,
            'validation_suite': t.validation_suite,
            'reuse_reconstruction_allowed': bool(t.supports_reconstruction_reuse),
            'kind': t.kind,
            'independent_validation_available': bool(
                t.supports_independent_validation and t.validation_suite
            ),
        })
    return {'targets': items, 'authorized_origins': list_authorized_origins()}


@app.post('/api/targets/resolve')
def resolve_target(payload: ResolveTargetRequest):
    """Check whether a user-entered URL is an approved local application."""
    try:
        target, start_url = resolve_authorized_application(
            application_url=payload.application_url,
            feature=payload.feature,
        )
    except TargetAuthorizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        'approved': True,
        'target_id': target.id,
        'label': target.label or target.id,
        'origin': target.origin,
        'application_url': start_url,
        'feature': target.feature_label,
        'kind': target.kind,
        'independent_validation_available': bool(
            target.supports_independent_validation and target.validation_suite
        ),
        'message': 'Application URL is approved for local investigation.',
    }


@app.get('/api/investigations')
def list_investigations(limit: int = 40):
    """List recent investigations from memory and durable artifact folders."""
    items = _list_investigation_summaries(limit=limit)
    return {
        'investigations': items,
        'count': len(items),
        'note': (
            'Completed jobs are listed from local artifacts/ and survive API restarts. '
            'In-progress jobs appear only while this API process is running.'
        ),
    }


@app.post('/api/investigations', response_model=InvestigationSummary)
def create_investigation(payload: CreateInvestigation):
    if not payload.application_url and not payload.target_id:
        raise HTTPException(
            status_code=400,
            detail='Provide an approved application_url or a sample target_id.',
        )
    try:
        target, start_url = resolve_authorized_application(
            application_url=payload.application_url,
            target_id=payload.target_id,
            feature=payload.feature,
        )
    except TargetAuthorizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    effective_pipeline = (
        'investigate_only'
        if payload.investigation_goal == 'understand'
        else payload.pipeline
    )

    with _lock:
        if any(job.get('status') in ACTIVE for job in _jobs.values()):
            raise HTTPException(status_code=409, detail='Only one investigation may run at a time')
        job_id = uuid4().hex
        job = {
            'id': job_id,
            'status': 'queued',
            'mode': payload.mode,
            'pipeline': effective_pipeline,
            'target_id': target.id,
            'feature': target.feature_label,
            'application_url': start_url,
            'investigation_goal': payload.investigation_goal,
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
        def status_cb(status, payload_status):
            with _lock:
                current = _jobs.get(job_id)
                if not current:
                    return
                current['status'] = status
                current['updated_at'] = payload_status.get('updated_at')
                if 'stages' in payload_status:
                    current['stages'] = payload_status['stages']
                if 'errors' in payload_status:
                    current['errors'] = payload_status['errors']

        try:
            summary = run_pipeline(
                job_id=job_id,
                mode=payload.mode,
                pipeline=effective_pipeline,
                reuse_reconstruction=payload.reuse_reconstruction,
                max_actions=payload.max_actions,
                artifacts_root=ARTIFACTS,
                status_cb=status_cb,
                target_id=target.id,
                application_url=start_url,
                feature=payload.feature or target.feature_label,
                investigation_goal=payload.investigation_goal,
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


@app.get('/api/investigations/{job_id}/repair')
def get_repair(job_id: str):
    """Return repair_report.json when a bounded repair stage actually ran."""
    _get_job(job_id)
    try:
        return _read_json_artifact(job_id, 'repair', 'repair_report.json')
    except HTTPException:
        raise HTTPException(status_code=404, detail='Repair results not available')


@app.get('/api/investigations/{job_id}/evidence-graph', response_model=EvidenceGraph)
def get_evidence_graph(job_id: str):
    _require_job_id(job_id)
    path = ARTIFACTS / job_id / 'evidence_graph.json'
    if path.is_file():
        return EvidenceGraph.model_validate_json(path.read_text(encoding='utf-8'))
    # Build on demand from available job artifacts only (no invented nodes).
    repair_path = ARTIFACTS / job_id / 'repair' / 'repair_report.json'
    graph = build_evidence_graph(
        root=ROOT,
        investigation_report=ARTIFACTS / job_id / 'investigation' / 'report.json',
        behavior_spec=ARTIFACTS / job_id / 'specification' / 'behavior_spec.frozen.json',
        reconstruction_dir=ARTIFACTS / job_id / 'reconstructed-app',
        validation_results=ARTIFACTS / job_id / 'validation' / 'validation_results.json',
        repair_report=repair_path if repair_path.is_file() else None,
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


@app.get('/api/investigations/{job_id}/verified-findings', response_model=VerifiedResults)
def get_verified_findings(job_id: str):
    """Read-only evidence verification over recorded artifacts (no Meta/Muse calls)."""
    _get_job(job_id)
    results = build_verified_results(ARTIFACTS, job_id)
    if results.availability == 'unavailable':
        raise HTTPException(
            status_code=404,
            detail=results.notes[0] if results.notes else 'Verified findings unavailable',
        )
    return results


@app.get('/api/investigations/{job_id}/human-report')
def get_human_report(job_id: str):
    """Shared narrative package for Simple/Developer UI (same VerifiedResults)."""
    _get_job(job_id)
    try:
        package = build_report_package(ARTIFACTS, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    verified: VerifiedResults = package['verified']
    if verified.availability == 'unavailable':
        raise HTTPException(
            status_code=404,
            detail=verified.notes[0] if verified.notes else 'Report unavailable',
        )
    return {
        'verified': verified.model_dump(mode='json'),
        'timeline': package['timeline'],
        'failures': package['failures'],
        'how_we_know': package['how_we_know'],
        'status_labels': STATUS_LABELS,
        'status_help': STATUS_HELP,
        'investigation_note': (package.get('investigation_report') or {}).get('note'),
        'api_request_count': (package.get('investigation_report') or {}).get('api_request_count'),
        'specification_present': package.get('behavior_spec') is not None,
        'requirements': [
            {
                'id': r.get('id'),
                'kind': r.get('kind'),
                'observed_result': r.get('observed_result'),
                'action_performed': r.get('action_performed'),
            }
            for r in ((package.get('behavior_spec') or {}).get('requirements') or [])
        ],
    }


@app.get('/api/investigations/{job_id}/reports/simple.md')
def download_simple_report(job_id: str):
    _get_job(job_id)
    package = build_report_package(ARTIFACTS, job_id)
    verified: VerifiedResults = package['verified']
    if verified.availability == 'unavailable':
        raise HTTPException(status_code=404, detail='Simple report unavailable')
    body = package['simple_markdown']
    return Response(
        content=body,
        media_type='text/markdown; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="reversex-{job_id}-simple.md"',
        },
    )


@app.get('/api/investigations/{job_id}/reports/developer.md')
def download_developer_report(job_id: str):
    _get_job(job_id)
    package = build_report_package(ARTIFACTS, job_id)
    verified: VerifiedResults = package['verified']
    if verified.availability == 'unavailable':
        raise HTTPException(status_code=404, detail='Developer report unavailable')
    body = package['developer_markdown']
    return Response(
        content=body,
        media_type='text/markdown; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="reversex-{job_id}-developer.md"',
        },
    )


@app.get('/api/demo/evidence-graph', response_model=EvidenceGraph)
def demo_evidence_graph():
    """Read-only graph from preserved Phase 1B–3 artifacts (no new model calls)."""
    graph = build_evidence_graph(root=ROOT)
    out = ARTIFACTS / 'phase4a' / 'evidence_graph.json'
    export_evidence_graph(graph, out)
    return graph


@app.get('/api/demo/controlled-repair')
def demo_controlled_repair():
    """Serve the labeled Controlled Repair Evaluation report (read-only; no new Muse calls)."""
    path = ARTIFACTS / 'phase5c' / 'controlled_repair_eval' / 'repair' / 'repair_report.json'
    if not path.is_file():
        raise HTTPException(status_code=404, detail='Controlled repair evaluation not available')
    return json.loads(path.read_text(encoding='utf-8'))


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
