"""Phase 3 CLI: isolated reconstruction preview + independent behavioral oracle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reversex.validate import run_phase3_validation

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECON = ROOT / 'artifacts' / 'phase2' / 'reconstructed-app'
DEFAULT_OUT = ROOT / 'artifacts' / 'phase3'


def main():
    parser = argparse.ArgumentParser(description='ReverseX Engineer Phase 3 behavioral validation')
    parser.add_argument('--reconstructed-dir', type=Path, default=DEFAULT_RECON)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--original-origin', default='http://127.0.0.1:8001')
    args = parser.parse_args()

    report = run_phase3_validation(
        reconstructed_dir=args.reconstructed_dir,
        output_dir=args.output_dir,
        original_origin=args.original_origin,
    )
    summary = {
        'phase': report.phase,
        'isolation_status': (report.isolation or {}).get('status'),
        'isolation_mode': (report.isolation or {}).get('isolation'),
        'total_valid': report.total_valid,
        'passed': report.passed,
        'failed': report.failed,
        'invalid': report.invalid,
        'behavioral_match_rate_percent': report.behavioral_match_rate_percent,
        'meta_api_requests': report.meta_api_requests,
        'tests': [{'test_id': t.test_id, 'status': t.status, 'differences': t.differences} for t in report.tests],
        'notes': report.notes,
        'results_path': str(args.output_dir / 'validation_results.json'),
    }
    print(json.dumps(summary, indent=2))
    if report.behavioral_match_rate_percent is None:
        raise SystemExit(2)
    if report.failed or report.invalid:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
