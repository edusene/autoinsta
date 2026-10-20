import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from '@xyflow/react'
import { outputColor, useEditor } from './catalog'

/** Conexão curva (bezier), colorida pela saída de origem, com botão para remover. */
export function FlowEdge({
  id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, sourceHandleId, markerEnd, selected,
}: EdgeProps) {
  const { deleteEdge } = useEditor()
  const [path, labelX, labelY] = getBezierPath({
    sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, curvature: 0.4,
  })
  const color = outputColor(sourceHandleId)
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} interactionWidth={24}
        style={{ stroke: color, strokeWidth: selected ? 3 : 2, opacity: selected ? 1 : 0.85 }} />
      <EdgeLabelRenderer>
        <button
          className={`edge-delete nodrag nopan ${selected ? 'visible' : ''}`}
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          onClick={(e) => {
            e.stopPropagation()
            deleteEdge(id)
          }}
          title="Remover conexão"
          aria-label="Remover conexão"
        >
          ×
        </button>
      </EdgeLabelRenderer>
    </>
  )
}
