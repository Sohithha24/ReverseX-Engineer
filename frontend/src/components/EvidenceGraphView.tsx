import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  MarkerType,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from '@xyflow/react'
import { useEffect, useMemo, useState } from 'react'
import type { EvidenceEdge, EvidenceGraph, EvidenceNode } from '../api/types'
import { EmptyState, Mono } from './ui'

/** Light-theme node accents: blue investigation, sage verified/outcomes, beige evidence */
const TYPE_COLOR: Record<string, string> = {
  investigation: '#315F86',
  experiment: '#315F86',
  action: '#315F86',
  observation: '#F3F0E8',
  requirement: '#477A63',
  hypothesis: '#B45309',
  reconstruction: '#477A63',
  artifact: '#E6E5DF',
  validation_test: '#315F86',
  validation_outcome: '#477A63',
  validation: '#315F86',
  repair: '#B42318',
  repair_attempt: '#B42318',
  mismatch: '#B42318',
}

function layout(nodes: EvidenceNode[]): Node[] {
  const groups = new Map<string, EvidenceNode[]>()
  for (const n of nodes) {
    const list = groups.get(n.type) || []
    list.push(n)
    groups.set(n.type, list)
  }
  const types = [...groups.keys()]
  const out: Node[] = []
  types.forEach((type, row) => {
    const rowNodes = groups.get(type) || []
    rowNodes.forEach((node, i) => {
      const color = TYPE_COLOR[node.type] || '#78817D'
      const softFill =
        node.type === 'observation' || node.type === 'artifact'
          ? '#F3F0E8'
          : node.type.includes('valid') || node.type === 'requirement' || node.type === 'reconstruction'
            ? '#DDEBDD'
            : '#E6F0FA'
      out.push({
        id: node.id,
        position: { x: 40 + i * 210, y: 40 + row * 120 },
        data: { label: `${node.type}\n${node.id.slice(0, 28)}`, evidence: node },
        style: {
          background: softFill,
          border: `1px solid ${color}`,
          borderRadius: 12,
          color: '#263238',
          fontSize: 11,
          padding: 10,
          width: 180,
          whiteSpace: 'pre-wrap',
          boxShadow: '0 1px 2px rgba(38,50,56,0.04)',
        },
      })
    })
  })
  return out
}

function toFlowEdges(edges: EvidenceEdge[]): Edge[] {
  return edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.type,
    type: 'smoothstep',
    animated: false,
    style: { stroke: '#C8C5BB' },
    labelStyle: { fill: '#78817D', fontSize: 10 },
    markerEnd: { type: MarkerType.ArrowClosed, color: '#C8C5BB' },
    data: { evidence: edge } as Record<string, unknown>,
  }))
}

export function EvidenceGraphView({ graph }: { graph: EvidenceGraph | null }) {
  const [selected, setSelected] = useState<EvidenceNode | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<EvidenceEdge | null>(null)

  const initialNodes = useMemo(() => layout(graph?.nodes || []), [graph])
  const initialEdges = useMemo(() => toFlowEdges(graph?.edges || []), [graph])
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  useEffect(() => {
    setNodes(initialNodes)
    setEdges(initialEdges)
    setSelected(null)
    setSelectedEdge(null)
  }, [initialNodes, initialEdges, setNodes, setEdges])

  if (!graph) {
    return <EmptyState>No evidence graph loaded yet.</EmptyState>
  }

  const onNodeClick: NodeMouseHandler = (_event, node) => {
    const evidence = (node.data as { evidence?: EvidenceNode }).evidence
    setSelected(evidence || null)
    setSelectedEdge(null)
  }

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="h-[520px] overflow-hidden rounded-[12px] border border-rx-line bg-white lg:col-span-2">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onEdgeClick={(_e, edge) => {
            const evidence = (edge.data as { evidence?: EvidenceEdge } | undefined)?.evidence
            setSelectedEdge(evidence || null)
            setSelected(null)
          }}
          fitView
          minZoom={0.3}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#E6E5DF" gap={18} />
          <MiniMap
            pannable
            zoomable
            maskColor="rgba(253,252,249,0.7)"
            nodeColor={(n) => {
              const evidence = (n.data as { evidence?: EvidenceNode }).evidence
              return TYPE_COLOR[evidence?.type || ''] || '#78817D'
            }}
            style={{ background: '#F3F0E8' }}
          />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <aside className="rounded-[12px] border border-rx-line bg-rx-beige p-4">
        <h3 className="mb-3 text-base font-semibold text-rx-text">Supporting evidence</h3>
        {!selected && !selectedEdge && (
          <EmptyState>Click a node or edge to inspect recorded evidence.</EmptyState>
        )}
        {selected && (
          <div className="space-y-2 text-sm">
            <span className="inline-flex rounded-full border border-rx-blue/20 bg-rx-blue-soft px-2.5 py-0.5 text-xs text-rx-blue">
              {selected.type}
            </span>
            <Mono className="block text-rx-text">{selected.id}</Mono>
            <p className="leading-relaxed text-rx-muted">{selected.description}</p>
            <p className="text-xs text-rx-muted">Status: {selected.status || '—'}</p>
            <p className="text-xs text-rx-muted">Ref: {selected.evidence_ref || '—'}</p>
            {selected.timestamp && <p className="text-xs text-rx-muted">Time: {selected.timestamp}</p>}
            {selected.metadata && Object.keys(selected.metadata).length > 0 && (
              <pre className="max-h-48 overflow-auto rounded-[12px] border border-rx-line bg-white p-2 font-mono text-xs text-rx-muted">
                {JSON.stringify(selected.metadata, null, 2)}
              </pre>
            )}
          </div>
        )}
        {selectedEdge && (
          <div className="space-y-2 text-sm">
            <span className="inline-flex rounded-full border border-rx-sage/25 bg-rx-sage-soft px-2.5 py-0.5 text-xs text-rx-sage">
              {selectedEdge.type}
            </span>
            <Mono className="block text-rx-text">
              {selectedEdge.source} → {selectedEdge.target}
            </Mono>
            <p className="leading-relaxed text-rx-muted">{selectedEdge.description}</p>
          </div>
        )}
        <p className="mt-4 text-xs text-rx-muted">Sources: {graph.source_artifacts.join(', ') || 'none'}</p>
      </aside>
    </div>
  )
}
