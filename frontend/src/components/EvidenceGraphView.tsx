import { useMemo, useState } from 'react'
import type { EvidenceEdge, EvidenceGraph, EvidenceNode } from '../api/types'

const TYPE_COLOR: Record<string, string> = {
  investigation: '#8b7cf7',
  action: '#5ec8ff',
  observation: '#6ee7b7',
  requirement: '#fbbf24',
  hypothesis: '#fb923c',
  reconstruction: '#f472b6',
  artifact: '#a3a3a3',
  validation_test: '#38bdf8',
  validation_outcome: '#34d399',
}

function layoutNodes(nodes: EvidenceNode[]) {
  const groups = new Map<string, EvidenceNode[]>()
  for (const n of nodes) {
    const list = groups.get(n.type) || []
    list.push(n)
    groups.set(n.type, list)
  }
  const types = [...groups.keys()]
  const positions = new Map<string, { x: number; y: number }>()
  const width = 920
  const height = Math.max(360, types.length * 88)
  types.forEach((type, row) => {
    const rowNodes = groups.get(type) || []
    rowNodes.forEach((node, i) => {
      const x = 80 + ((i + 1) * (width - 120)) / (rowNodes.length + 1)
      const y = 50 + row * 80
      positions.set(node.id, { x, y })
    })
  })
  return { positions, width, height }
}

export function EvidenceGraphView({ graph }: { graph: EvidenceGraph | null }) {
  const [selected, setSelected] = useState<EvidenceNode | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<EvidenceEdge | null>(null)

  const { positions, width, height } = useMemo(
    () => layoutNodes(graph?.nodes || []),
    [graph],
  )

  if (!graph) {
    return <p className="muted">No evidence graph loaded yet.</p>
  }

  return (
    <div className="graph-layout">
      <svg className="graph-canvas" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Evidence graph">
        {graph.edges.map((edge) => {
          const a = positions.get(edge.source)
          const b = positions.get(edge.target)
          if (!a || !b) return null
          return (
            <g key={edge.id}>
              <line
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                className={selectedEdge?.id === edge.id ? 'edge active' : 'edge'}
                onClick={() => {
                  setSelectedEdge(edge)
                  setSelected(null)
                }}
              />
            </g>
          )
        })}
        {graph.nodes.map((node) => {
          const p = positions.get(node.id)
          if (!p) return null
          const fill = TYPE_COLOR[node.type] || '#94a3b8'
          return (
            <g
              key={node.id}
              className="node"
              transform={`translate(${p.x}, ${p.y})`}
              onClick={() => {
                setSelected(node)
                setSelectedEdge(null)
              }}
            >
              <circle r={14} fill={fill} opacity={selected?.id === node.id ? 1 : 0.85} />
              <title>{node.id}</title>
            </g>
          )
        })}
      </svg>
      <aside className="graph-detail panel">
        <h3>Evidence detail</h3>
        {!selected && !selectedEdge && (
          <p className="muted">Click a node or edge to inspect recorded evidence.</p>
        )}
        {selected && (
          <div className="detail-block">
            <div className="badge">{selected.type}</div>
            <p className="mono">{selected.id}</p>
            <p>{selected.description}</p>
            <p className="muted">Status: {selected.status || '—'}</p>
            <p className="muted">Ref: {selected.evidence_ref || '—'}</p>
            {selected.timestamp && <p className="muted">Time: {selected.timestamp}</p>}
            {selected.metadata && Object.keys(selected.metadata).length > 0 && (
              <pre>{JSON.stringify(selected.metadata, null, 2)}</pre>
            )}
          </div>
        )}
        {selectedEdge && (
          <div className="detail-block">
            <div className="badge">{selectedEdge.type}</div>
            <p className="mono">{selectedEdge.source} → {selectedEdge.target}</p>
            <p>{selectedEdge.description}</p>
          </div>
        )}
        <p className="muted small">
          Sources: {graph.source_artifacts.join(', ') || 'none'}
        </p>
      </aside>
    </div>
  )
}
