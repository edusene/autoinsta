import { Handle, Position, type NodeProps } from '@xyflow/react'
import { CATEGORY_META, summarize, useCatalog, type FlowNode } from './catalog'

const OUTPUT_LABELS: Record<string, string> = { true: 'Sim', false: 'Não' }

export function FlowNodeView({ data, selected }: NodeProps<FlowNode>) {
  const catalog = useCatalog()
  const def = catalog[data.nodeType]
  const meta = def ? CATEGORY_META[def.category] : { label: 'Desconhecido', color: 'var(--danger)' }
  const outputs = def?.outputs ?? []
  const isBranch = outputs.length > 1

  return (
    <div className={`flow-node ${selected ? 'selected' : ''} ${data.hasError ? 'has-error' : ''}`}>
      {def?.category !== 'trigger' && <Handle type="target" position={Position.Top} />}
      <div className="flow-node-header" style={{ borderTop: `3px solid ${meta.color}`, borderRadius: '9px 9px 0 0' }}>
        <div style={{ minWidth: 0 }}>
          <div className="flow-node-kind" style={{ color: meta.color }}>{meta.label}</div>
          <div>{def?.label ?? data.nodeType}</div>
        </div>
      </div>
      <div className="flow-node-body">{summarize(def, data.config) || ' '}</div>
      {isBranch && (
        <div className="flow-node-outputs">
          {outputs.map((o) => (
            <span key={o} style={{ color: o === 'true' ? 'var(--success)' : 'var(--danger)' }}>{OUTPUT_LABELS[o] ?? o}</span>
          ))}
        </div>
      )}
      {outputs.map((output, i) => (
        <Handle
          key={output}
          id={isBranch ? output : undefined}
          type="source"
          position={Position.Bottom}
          className={isBranch ? `handle-${output}` : undefined}
          style={isBranch ? { left: `${((i + 1) * 100) / (outputs.length + 1)}%` } : undefined}
        />
      ))}
    </div>
  )
}
