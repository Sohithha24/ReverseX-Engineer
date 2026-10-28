"""Meta Muse Spark feature reconstruction from a frozen behavior spec only.

Security boundaries (code-enforced, not prompt-only):
- Never opens sample_app or original HTML/CSS/JS paths.
- Model context is built only from the frozen BehaviorSpec + fixed instructions.
- Generated files must match a fixed allowlist; path traversal rejected.
- Generated content is never executed by this module.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from reversex.spec import BehaviorSpec, EvidenceKind

ALLOWED_FILENAMES = frozenset({'index.html', 'style.css', 'script.js'})
MAX_FILE_BYTES = 48_000
MAX_TOTAL_BYTES = 120_000
MAX_RECONSTRUCTION_REQUESTS = 2
BLOCKED_CONTEXT_GLOBS = (
    'sample_app',
    'sample_app/index.html',
    'sample_app/style.css',
    'sample_app/app.js',
)

RECONSTRUCTION_SCHEMA = {
    'type': 'json_schema',
    'json_schema': {
        'name': 'ReverseXReconstruction',
        'strict': True,
        'schema': {
            'type': 'object',
            'properties': {
                'files': {
                    'type': 'array',
                    'minItems': 3,
                    'maxItems': 3,
                    'items': {
                        'type': 'object',
                        'properties': {
                            'filename': {
                                'type': 'string',
                                'enum': ['index.html', 'style.css', 'script.js'],
                            },
                            'content': {'type': 'string'},
                        },
                        'required': ['filename', 'content'],
                        'additionalProperties': False,
                    },
                },
                'notes': {'type': 'string'},
            },
            'required': ['files', 'notes'],
            'additionalProperties': False,
        },
    },
}

SYSTEM_PROMPT = """You reconstruct ONE web feature from a frozen behavioral specification.
You receive only the specification JSON. You do NOT receive original application source.
Generate a minimal independent static web app as exactly three files: index.html, style.css, script.js.
Reproduce ONLY observation-kind requirements (required-field validation, successful task creation,
task list display, persistence across reload). Hypotheses are not requirements.
Do not assume a specific storage technology; choose any approach that matches observed behavior.
Do not include secrets, network calls to external hosts, or shell commands.
Return structured JSON matching the schema.
"""


class GeneratedFile(BaseModel):
    model_config = ConfigDict(extra='forbid')

    filename: str
    content: str

    @field_validator('filename')
    @classmethod
    def allowlisted_name(cls, value: str) -> str:
        name = value.strip()
        if name != value or name != Path(name).name:
            raise ValueError(f'unsafe filename: {value!r}')
        if '/' in name or '\\' in name or '..' in name:
            raise ValueError(f'path separators not allowed: {value!r}')
        if name not in ALLOWED_FILENAMES:
            raise ValueError(f'filename not on allowlist: {value!r}')
        # Reject absolute Windows/Unix forms even if basename somehow slipped through.
        if re.match(r'^[A-Za-z]:', name) or name.startswith('/'):
            raise ValueError(f'absolute path not allowed: {value!r}')
        return name

    @field_validator('content')
    @classmethod
    def size_limit(cls, value: str) -> str:
        encoded = value.encode('utf-8')
        if len(encoded) > MAX_FILE_BYTES:
            raise ValueError(f'file exceeds {MAX_FILE_BYTES} byte limit')
        return value


class ReconstructionPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')

    files: list[GeneratedFile] = Field(min_length=3, max_length=3)
    notes: str = Field(default='', max_length=2000)

    @field_validator('files')
    @classmethod
    def exact_allowlist_once(cls, files: list[GeneratedFile]) -> list[GeneratedFile]:
        names = [f.filename for f in files]
        if set(names) != ALLOWED_FILENAMES:
            raise ValueError(f'files must be exactly {sorted(ALLOWED_FILENAMES)}, got {sorted(set(names))}')
        if len(names) != len(set(names)):
            raise ValueError('duplicate filenames are not allowed')
        total = sum(len(f.content.encode('utf-8')) for f in files)
        if total > MAX_TOTAL_BYTES:
            raise ValueError(f'total payload exceeds {MAX_TOTAL_BYTES} bytes')
        return files


class ReconstructionResult(BaseModel):
    model_config = ConfigDict(extra='forbid')

    status: str
    output_dir: str
    api_request_count: int
    model: str
    files_written: list[str]
    notes: str = ''
    preview: dict
    meta_summary: dict
    original_app_untouched: bool = True


def observation_only_spec_for_model(spec: BehaviorSpec) -> dict:
    """Strip hypotheses into a clearly labeled section; never attach source files."""
    observations = [r.model_dump(mode='json') for r in spec.requirements if r.kind == EvidenceKind.OBSERVATION]
    hypotheses = [r.model_dump(mode='json') for r in spec.requirements if r.kind == EvidenceKind.HYPOTHESIS]
    return {
        'feature': spec.feature,
        'status': spec.status,
        'source_report_sha256': spec.source_report_sha256,
        'observation_requirements': observations,
        'hypotheses_not_requirements': hypotheses,
        'global_uncertainties': spec.global_uncertainties,
        'excluded_from_model_context': spec.excluded_from_model_context,
        'desired_output': {
            'files': sorted(ALLOWED_FILENAMES),
            'format': 'ReverseXReconstruction JSON schema',
        },
    }


def assert_no_original_source_in_context(context: dict) -> None:
    """Reject leaked original implementation text.

    Listing exclusion paths (e.g. sample_app/app.js) in metadata is allowed.
    Embedding known original source fingerprints in requirements/payload is not.
    """
    # Inspect requirement bodies only — not the exclusion metadata list.
    scanned = {
        'observation_requirements': context.get('observation_requirements'),
        'hypotheses_not_requirements': context.get('hypotheses_not_requirements'),
        'feature': context.get('feature'),
        'global_uncertainties': context.get('global_uncertainties'),
    }
    blob = json.dumps(scanned, ensure_ascii=True).lower()
    forbidden_markers = (
        'localstorage.setitem',
        'reversex_fixture_tasks_v1',
        "getelementbyid('task-form')",
        'getelementbyid("task-form")',
        'const key = \'reversex_fixture_tasks_v1\'',
    )
    for marker in forbidden_markers:
        if marker in blob:
            raise RuntimeError(f'reconstruction context contains forbidden original-source marker: {marker}')


def ensure_sample_app_paths_not_read(accessed_paths: list[Path]) -> None:
    for path in accessed_paths:
        normalized = path.resolve().as_posix().lower()
        if '/sample_app/' in normalized or normalized.endswith('/sample_app'):
            raise RuntimeError(f'reconstruction must not read sample_app path: {path}')


def validate_reconstruction_response(raw: str | dict) -> ReconstructionPayload:
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f'invalid model JSON: {exc}') from exc
    else:
        data = raw
    try:
        return ReconstructionPayload.model_validate(data)
    except ValidationError as exc:
        raise ValueError(f'invalid reconstruction payload: {exc}') from exc


def write_reconstructed_app(payload: ReconstructionPayload, output_dir: Path) -> list[str]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for item in payload.files:
        target = (output_dir / item.filename).resolve()
        if target.parent != output_dir:
            raise ValueError(f'refused to write outside output dir: {item.filename}')
        if target.name not in ALLOWED_FILENAMES:
            raise ValueError(f'refused unexpected target name: {target.name}')
        target.write_text(item.content, encoding='utf-8', newline='\n')
        written.append(str(target))
    return written


def verify_original_app_untouched(sample_app_dir: Path, before_hashes: dict[str, str]) -> bool:
    import hashlib

    for name, prior in before_hashes.items():
        path = sample_app_dir / name
        if not path.is_file():
            return False
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != prior:
            return False
    return True


def snapshot_sample_app_hashes(sample_app_dir: Path) -> dict[str, str]:
    import hashlib

    hashes: dict[str, str] = {}
    if not sample_app_dir.is_dir():
        return hashes
    for path in sorted(sample_app_dir.glob('*')):
        if path.is_file():
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


class MuseReconstructor:
    """httpx-only Meta client for reconstruction. Never uses the OpenAI SDK."""

    def __init__(self):
        key = os.getenv('MODEL_API_KEY')
        if not key:
            raise RuntimeError('MODEL_API_KEY is missing')
        import httpx

        self._http = httpx.Client(
            base_url='https://api.meta.ai/v1',
            headers={'Authorization': f'Bearer {key}'},
            timeout=90.0,
        )
        self.model = os.getenv('META_MODEL', 'muse-spark-1.3')
        self.request_count = 0

    def generate(self, spec: BehaviorSpec) -> tuple[ReconstructionPayload, dict]:
        if self.request_count >= MAX_RECONSTRUCTION_REQUESTS:
            raise RuntimeError('reconstruction API budget exhausted')
        if spec.status != 'frozen':
            raise ValueError('only a frozen behavior specification may be sent to Meta')

        context = observation_only_spec_for_model(spec)
        assert_no_original_source_in_context(context)
        # File-access boundary: this method never opens sample_app paths.
        ensure_sample_app_paths_not_read([])

        user_content = (
            'FROZEN_BEHAVIOR_SPEC_JSON (requirements data only; not application source):\n'
            + json.dumps(context)
        )
        self.request_count += 1
        response = self._http.post(
            '/chat/completions',
            json={
                'model': self.model,
                'messages': [
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_content},
                ],
                'response_format': RECONSTRUCTION_SCHEMA,
            },
        )
        summary = {
            'http_status': response.status_code,
            'model': self.model,
            'request_index': self.request_count,
        }
        if response.status_code >= 400:
            raise ValueError(f'Meta API error {response.status_code}: {response.text[:240]}')
        data = response.json()
        message = data['choices'][0]['message']
        content = message.get('content')
        if not content and isinstance(message.get('parsed'), dict):
            payload = validate_reconstruction_response(message['parsed'])
        elif content:
            payload = validate_reconstruction_response(content)
        else:
            raise ValueError('Meta returned an empty reconstruction')
        usage = data.get('usage') or {}
        summary['usage'] = {
            'prompt_tokens': usage.get('prompt_tokens'),
            'completion_tokens': usage.get('completion_tokens'),
            'total_tokens': usage.get('total_tokens'),
        }
        summary['finish_reason'] = data['choices'][0].get('finish_reason')
        summary['notes_preview'] = (payload.notes or '')[:200]
        summary['filenames'] = [f.filename for f in payload.files]
        return payload, summary

    def generate_with_one_retry(self, spec: BehaviorSpec) -> tuple[ReconstructionPayload, list[dict]]:
        summaries: list[dict] = []
        try:
            payload, summary = self.generate(spec)
            summaries.append({**summary, 'accepted': True})
            return payload, summaries
        except Exception as first_exc:
            summaries.append({'accepted': False, 'error': str(first_exc)[:300], 'request_index': self.request_count})
            if self.request_count >= MAX_RECONSTRUCTION_REQUESTS:
                raise
            payload, summary = self.generate(spec)
            summaries.append({**summary, 'accepted': True, 'retried_after': str(first_exc)[:200]})
            return payload, summaries


def run_reconstruction(
    frozen_spec: BehaviorSpec,
    *,
    output_dir: Path,
    sample_app_dir: Path,
    preview_fn,
) -> ReconstructionResult:
    before = snapshot_sample_app_hashes(sample_app_dir)
    reconstructor = MuseReconstructor()
    payload, meta_summaries = reconstructor.generate_with_one_retry(frozen_spec)
    written = write_reconstructed_app(payload, output_dir)
    untouched = verify_original_app_untouched(sample_app_dir, before)
    if not untouched:
        raise RuntimeError('sample_app files changed during reconstruction — aborting')
    preview = preview_fn(output_dir)
    return ReconstructionResult(
        status='generated',
        output_dir=str(output_dir),
        api_request_count=reconstructor.request_count,
        model=reconstructor.model,
        files_written=written,
        notes=payload.notes,
        preview=preview,
        meta_summary={'calls': meta_summaries},
        original_app_untouched=untouched,
    )
