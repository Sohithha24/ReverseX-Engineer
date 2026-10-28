"""Phase 2 CLI: freeze behavior spec from Phase 1B, reconstruct via Muse, validate outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from reversex.preview import prepare_preview, write_preview_status
from reversex.reconstruct import run_reconstruction
from reversex.spec import generate_and_freeze_spec, load_frozen_spec


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / 'artifacts' / 'phase1b' / 'report.json'
DEFAULT_OUT = ROOT / 'artifacts' / 'phase2'
SAMPLE_APP = ROOT / 'sample_app'


def run_phase2(
    *,
    report_path: Path = DEFAULT_REPORT,
    output_dir: Path = DEFAULT_OUT,
    skip_reconstruction: bool = False,
) -> dict:
    load_dotenv(ROOT / '.env')
    output_dir.mkdir(parents=True, exist_ok=True)
    reconstructed_dir = output_dir / 'reconstructed-app'

    spec = generate_and_freeze_spec(report_path, output_dir=output_dir)
    sha_path = output_dir / 'behavior_spec.sha256'
    expected = sha_path.read_text(encoding='utf-8').strip()
    frozen = load_frozen_spec(output_dir / 'behavior_spec.frozen.json', expected_sha256=expected)

    result = {
        'phase': 2,
        'spec_status': frozen.status,
        'spec_sha256': expected,
        'observation_requirements': [
            r.id for r in frozen.requirements if r.kind.value == 'observation'
        ],
        'hypothesis_items': [
            r.id for r in frozen.requirements if r.kind.value == 'hypothesis'
        ],
        'reconstruction': None,
        'preview': None,
    }

    if skip_reconstruction:
        result['reconstruction'] = {'status': 'skipped'}
        (output_dir / 'phase2_result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result

    recon = run_reconstruction(
        frozen,
        output_dir=reconstructed_dir,
        sample_app_dir=SAMPLE_APP,
        preview_fn=prepare_preview,
    )
    write_preview_status(output_dir, recon.preview)
    result['reconstruction'] = recon.model_dump(mode='json')
    result['preview'] = recon.preview
    (output_dir / 'phase2_result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description='ReverseX Engineer Phase 2 reconstruction')
    parser.add_argument('--report', type=Path, default=DEFAULT_REPORT)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--skip-reconstruction', action='store_true')
    args = parser.parse_args()
    result = run_phase2(
        report_path=args.report,
        output_dir=args.output_dir,
        skip_reconstruction=args.skip_reconstruction,
    )
    # Never print secrets; summarize only.
    summary = {
        'phase': result['phase'],
        'spec_status': result['spec_status'],
        'spec_sha256': result['spec_sha256'],
        'observation_requirements': result['observation_requirements'],
        'reconstruction_status': (result.get('reconstruction') or {}).get('status'),
        'api_request_count': (result.get('reconstruction') or {}).get('api_request_count'),
        'files_written': (result.get('reconstruction') or {}).get('files_written'),
        'preview_status': (result.get('preview') or {}).get('status'),
        'original_app_untouched': (result.get('reconstruction') or {}).get('original_app_untouched'),
    }
    print(json.dumps(summary, indent=2))
    if result.get('reconstruction') and result['reconstruction'].get('status') != 'generated':
        if not args.skip_reconstruction:
            raise SystemExit(1)


if __name__ == '__main__':
    main()
