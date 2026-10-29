"""Lightweight EvidenceGraph built only from recorded Phase 1B–3 artifacts.

No invented relationships. No graph database.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


NodeType = Literal[
    'investigation',
    'action',
    'observation',
    'requirement',
    'hypothesis',
    'reconstruction',
    'artifact',
    'validation_test',
    'validation_outcome',
    'repair_attempt',
    'mismatch',
]

EdgeType = Literal[
    'observed_during',
    'supports',
    'implemented_by',
    'validated_by',
    'derived_from',
    'produced',
    'repaired_by',
    'revalidated_by',
]


class EvidenceNode(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    type: NodeType
    description: str
    evidence_ref: str | None = None
    status: str = 'recorded'
    timestamp: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceEdge(BaseModel):
    model_config = ConfigDict(extra='forbid')

    id: str
    type: EdgeType
    source: str
    target: str
    description: str


class EvidenceGraph(BaseModel):
    model_config = ConfigDict(extra='forbid')

    project: str = 'ReverseX Engineer'
    version: str = '1'
    generated_at: str
    source_artifacts: list[str]
    nodes: list[EvidenceNode]
    edges: list[EvidenceEdge]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def build_evidence_graph(
    *,
    root: Path,
    investigation_report: Path | None = None,
    behavior_spec: Path | None = None,
    reconstruction_dir: Path | None = None,
    validation_results: Path | None = None,
    repair_report: Path | None = None,
) -> EvidenceGraph:
    root = root.resolve()
    nodes: list[EvidenceNode] = []
    edges: list[EvidenceEdge] = []
    sources: list[str] = []
    edge_i = 0

    def add_edge(etype: EdgeType, source: str, target: str, description: str) -> None:
        nonlocal edge_i
        edge_i += 1
        edges.append(EvidenceEdge(
            id=f'e{edge_i}',
            type=etype,
            source=source,
            target=target,
            description=description,
        ))

    inv_path = investigation_report or (root / 'artifacts' / 'phase1b' / 'report.json')
    spec_path = behavior_spec or (root / 'artifacts' / 'phase2' / 'behavior_spec.frozen.json')
    recon_dir = reconstruction_dir or (root / 'artifacts' / 'phase2' / 'reconstructed-app')
    val_path = validation_results or (root / 'artifacts' / 'phase3' / 'validation_results.json')

    investigation_id = None
    if inv_path.is_file():
        sources.append(_rel(inv_path, root))
        report = json.loads(inv_path.read_text(encoding='utf-8'))
        investigation_id = 'investigation:phase1b'
        nodes.append(EvidenceNode(
            id=investigation_id,
            type='investigation',
            description=f"Investigation mode={report.get('mode')} status={report.get('status')}",
            evidence_ref=_rel(inv_path, root),
            status=str(report.get('status') or 'recorded'),
            timestamp=None,
            metadata={
                'mode': report.get('mode'),
                'target': report.get('target'),
                'duration_seconds': report.get('duration_seconds'),
                'api_request_count': report.get('api_request_count'),
            },
        ))
        for event in report.get('events') or []:
            if event.get('status') != 'ok' or not event.get('decision'):
                continue
            step = event.get('step')
            action_id = f'action:step-{step}'
            decision = event['decision']
            nodes.append(EvidenceNode(
                id=action_id,
                type='action',
                description=(
                    f"step {step}: {decision.get('action')} "
                    f"element={decision.get('element_id')} value={decision.get('value')!r}"
                ),
                evidence_ref=f'{_rel(inv_path, root)}#step-{step}',
                status='ok',
                metadata={'step': step, 'decision': decision},
            ))
            add_edge('observed_during', action_id, investigation_id, 'Action recorded during investigation')
            after = (event.get('after') or {}).get('visible_text')
            if after:
                obs_id = f'observation:step-{step}'
                nodes.append(EvidenceNode(
                    id=obs_id,
                    type='observation',
                    description=f'Visible text after step {step}',
                    evidence_ref=f'{_rel(inv_path, root)}#step-{step}-after',
                    status='observed',
                    metadata={'visible_text_excerpt': after[:300]},
                ))
                add_edge('observed_during', obs_id, action_id, 'Observation captured after action')

        objectives = report.get('objectives') or {}
        for key, obj in objectives.items():
            if not isinstance(obj, dict) or not obj.get('supported'):
                continue
            # Objective support is linked later when requirements load; keep as observation anchors.
            oid = f'objective:{key}'
            nodes.append(EvidenceNode(
                id=oid,
                type='observation',
                description=obj.get('evidence') or key,
                evidence_ref=_rel(inv_path, root),
                status='supported',
                metadata={'objective_key': key, 'task_name': obj.get('task_name')},
            ))
            add_edge('observed_during', oid, investigation_id, 'Objective marked supported in investigation report')

    req_ids: dict[str, str] = {}
    if spec_path.is_file():
        sources.append(_rel(spec_path, root))
        spec = json.loads(spec_path.read_text(encoding='utf-8'))
        for req in spec.get('requirements') or []:
            rid = req.get('id')
            if not rid:
                continue
            node_id = f'requirement:{rid}'
            kind = req.get('kind') or 'observation'
            nodes.append(EvidenceNode(
                id=node_id,
                type='hypothesis' if kind == 'hypothesis' else 'requirement',
                description=req.get('observed_result') or rid,
                evidence_ref=_rel(spec_path, root),
                status=kind,
                metadata={
                    'feature': req.get('feature'),
                    'action_performed': req.get('action_performed'),
                    'input_values': req.get('input_values'),
                    'uncertainties': req.get('uncertainties'),
                },
            ))
            req_ids[rid] = node_id
            for ev in req.get('evidence') or []:
                step = ev.get('step')
                if step is not None:
                    action_id = f'action:step-{step}'
                    if any(n.id == action_id for n in nodes):
                        add_edge('supports', action_id, node_id, f'Step {step} supports {rid}')
                obj_key = ev.get('objective_key')
                if obj_key:
                    oid = f'objective:{obj_key}'
                    if any(n.id == oid for n in nodes):
                        add_edge('supports', oid, node_id, f'Objective {obj_key} supports {rid}')
            if investigation_id and kind == 'observation':
                add_edge('derived_from', node_id, investigation_id, 'Requirement derived from investigation')

    recon_node = None
    if recon_dir.is_dir() and (recon_dir / 'index.html').is_file():
        sources.append(_rel(recon_dir, root))
        recon_node = 'reconstruction:phase2'
        files = [p.name for p in sorted(recon_dir.glob('*')) if p.is_file()]
        nodes.append(EvidenceNode(
            id=recon_node,
            type='reconstruction',
            description='AI-generated reconstructed app files',
            evidence_ref=_rel(recon_dir, root),
            status='generated',
            metadata={'files': files},
        ))
        for name in files:
            aid = f'artifact:{name}'
            nodes.append(EvidenceNode(
                id=aid,
                type='artifact',
                description=f'Reconstructed file {name}',
                evidence_ref=f'{_rel(recon_dir, root)}/{name}',
                status='generated',
            ))
            add_edge('produced', recon_node, aid, 'Reconstruction produced artifact')
        for rid, node_id in req_ids.items():
            if rid.startswith('HYP-'):
                continue
            add_edge('implemented_by', node_id, recon_node, f'{rid} implemented by reconstruction (claimed by Phase 2 generation)')

    if val_path.is_file():
        sources.append(_rel(val_path, root))
        validation = json.loads(val_path.read_text(encoding='utf-8'))
        for test in validation.get('tests') or []:
            tid = test.get('test_id')
            if not tid:
                continue
            test_node = f'validation_test:{tid}'
            outcome_node = f'validation_outcome:{tid}'
            nodes.append(EvidenceNode(
                id=test_node,
                type='validation_test',
                description=test.get('description') or tid,
                evidence_ref=_rel(val_path, root),
                status='defined',
                metadata={'input_values': test.get('input_values'), 'evidence_refs': test.get('evidence_refs')},
            ))
            nodes.append(EvidenceNode(
                id=outcome_node,
                type='validation_outcome',
                description=f"status={test.get('status')}",
                evidence_ref=_rel(val_path, root),
                status=str(test.get('status') or 'unknown'),
                metadata={
                    'differences': test.get('differences'),
                    'original_screenshot': (test.get('original') or {}).get('screenshot'),
                    'reconstruction_screenshot': (test.get('reconstruction') or {}).get('screenshot'),
                },
            ))
            add_edge('validated_by', test_node, outcome_node, 'Test produced outcome')
            if recon_node:
                add_edge('validated_by', recon_node, test_node, 'Reconstruction evaluated by test')
            for ref in test.get('evidence_refs') or []:
                if not isinstance(ref, str):
                    continue
                if ref.startswith('REQ-'):
                    node_id = f'requirement:{ref}'
                    if any(n.id == node_id for n in nodes):
                        add_edge('supports', node_id, test_node, 'Requirement referenced by validation test')
                elif ref.startswith('phase1b:'):
                    obj = ref.split(':', 1)[1]
                    oid = f'objective:{obj}'
                    if any(n.id == oid for n in nodes):
                        add_edge('supports', oid, test_node, 'Investigation objective referenced by validation test')

    # Repair chain — only when a real repair_report.json exists with attempts.
    if repair_report is not None and repair_report.is_file():
        sources.append(_rel(repair_report, root))
        repair = json.loads(repair_report.read_text(encoding='utf-8'))
        for attempt in repair.get('attempts') or []:
            n = attempt.get('attempt')
            if n is None:
                continue
            rid = f'repair_attempt:{n}'
            nodes.append(EvidenceNode(
                id=rid,
                type='repair_attempt',
                description=(
                    f"Repair attempt {n} status={attempt.get('status')} "
                    f"rate {attempt.get('prior_match_rate_percent')}→{attempt.get('new_match_rate_percent')}"
                ),
                evidence_ref=_rel(repair_report, root),
                status=str(attempt.get('status') or 'recorded'),
                metadata={
                    'failed_scenarios_addressed': attempt.get('failed_scenarios_addressed'),
                    'changed_files': attempt.get('changed_files'),
                    'newly_passed_tests': attempt.get('newly_passed_tests'),
                    'regressed_tests': attempt.get('regressed_tests'),
                    'candidate_dir': attempt.get('candidate_dir'),
                    'validation_artifact': attempt.get('validation_artifact'),
                    'accepted_as_best': attempt.get('accepted_as_best'),
                },
            ))
            for tid in attempt.get('failed_scenarios_addressed') or []:
                test_node = f'validation_test:{tid}'
                mismatch_id = f'mismatch:{tid}:attempt-{n}'
                nodes.append(EvidenceNode(
                    id=mismatch_id,
                    type='mismatch',
                    description=f'Observed mismatch motivating repair attempt {n} for {tid}',
                    evidence_ref=_rel(repair_report, root),
                    status='recorded',
                    metadata={'test_id': tid, 'attempt': n},
                ))
                if any(node.id == test_node for node in nodes):
                    add_edge('derived_from', mismatch_id, test_node, 'Mismatch derived from failed validation test')
                add_edge('repaired_by', mismatch_id, rid, 'Mismatch addressed by repair attempt')
            cand = attempt.get('candidate_dir')
            if cand:
                cand_node = f'reconstruction:repair-attempt-{n}'
                nodes.append(EvidenceNode(
                    id=cand_node,
                    type='reconstruction',
                    description=f'Repaired candidate from attempt {n}',
                    evidence_ref=str(cand).replace('\\', '/'),
                    status='repaired',
                    metadata={'attempt': n, 'changed_files': attempt.get('changed_files')},
                ))
                add_edge('produced', rid, cand_node, 'Repair attempt produced updated reconstruction')
                val_art = attempt.get('validation_artifact')
                if val_art:
                    reval_node = f'validation_outcome:repair-attempt-{n}'
                    nodes.append(EvidenceNode(
                        id=reval_node,
                        type='validation_outcome',
                        description=(
                            f"Revalidation after repair attempt {n}: "
                            f"{attempt.get('new_match_rate_percent')}%"
                        ),
                        evidence_ref=str(val_art).replace('\\', '/'),
                        status=str(attempt.get('status') or 'recorded'),
                    ))
                    add_edge('revalidated_by', cand_node, reval_node, 'Repaired reconstruction revalidated')

    return EvidenceGraph(
        generated_at=_now(),
        source_artifacts=sources,
        nodes=nodes,
        edges=edges,
    )


def export_evidence_graph(graph: EvidenceGraph, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph.model_dump(mode='json'), indent=2), encoding='utf-8')
    return path
