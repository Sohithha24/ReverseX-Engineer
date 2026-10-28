from pathlib import Path

from reversex.evidence_graph import build_evidence_graph, export_evidence_graph

ROOT = Path(__file__).resolve().parents[1]


def test_phase_artifacts_produce_connected_graph():
    graph = build_evidence_graph(root=ROOT)
    types = {n.type for n in graph.nodes}
    assert 'investigation' in types
    assert 'action' in types
    assert 'requirement' in types
    assert 'reconstruction' in types
    assert 'validation_test' in types
    assert 'validation_outcome' in types
    assert graph.edges
    edge_types = {e.type for e in graph.edges}
    assert 'observed_during' in edge_types
    assert 'supports' in edge_types
    assert 'implemented_by' in edge_types
    assert 'validated_by' in edge_types
    # No edges to unknown nodes
    node_ids = {n.id for n in graph.nodes}
    for edge in graph.edges:
        assert edge.source in node_ids
        assert edge.target in node_ids


def test_export_evidence_graph(tmp_path: Path):
    graph = build_evidence_graph(root=ROOT)
    path = export_evidence_graph(graph, tmp_path / 'evidence_graph.json')
    assert path.is_file()
    loaded = path.read_text(encoding='utf-8')
    assert 'investigation:phase1b' in loaded


def test_missing_artifacts_do_not_invent_nodes(tmp_path: Path):
    graph = build_evidence_graph(
        root=tmp_path,
        investigation_report=tmp_path / 'nope.json',
        behavior_spec=tmp_path / 'nope2.json',
        reconstruction_dir=tmp_path / 'nope3',
        validation_results=tmp_path / 'nope4.json',
    )
    assert graph.nodes == []
    assert graph.edges == []
