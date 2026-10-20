import { Handle, NodeToolbar, Position, type NodeProps } from '@xyflow/react'
import type { CSSProperties } from 'react'
import { ctrPercent } from '../lib/format'
import {
  CATEGORY_META, configButtons, iconFor, nodeOutputs, outputColor, outputLabel, summarize, useCatalog, useEditor,
  type FlowNode,
} from './catalog'
import { Icon } from './Icon'

export function FlowNodeView({ id, data, selected }: NodeProps<FlowNode>) {
  const catalog = useCatalog()
  const { duplicateNode, deleteNode, stats } = useEditor()
  const def = catalog[data.nodeType]
  const meta = def ? CATEGORY_META[def.category] : { label: 'Desconhecido', color: 'var(--danger)' }
  const outputs = nodeOutputs(def, data.config)
  const isButtons = def?.dynamic_outputs === 'buttons'
  const isBranch = outputs.length > 1
  const nodeStats = stats[id]
  const summary = summarize(def, data.config)

  return (
    <div className={`flow-node ${selected ? 'selected' : ''} ${data.hasError ? 'has-error' : ''}`}
      style={{ '--node-color': meta.color } as CSSProperties}>
      <NodeToolbar isVisible={selected} position={Position.Top} offset={10} className="node-toolbar">
        {def?.category !== 'trigger' && (
          <button onClick={() => duplicateNode(id)} title="Duplicar (Ctrl+D)"><Icon name="copy" size={14} /> Duplicar</button>
        )}
        <button className="danger" onClick={() => deleteNode(id)} title="Remover (Delete)"><Icon name="trash" size={14} /> Remover</button>
      </NodeToolbar>
      {def?.category !== 'trigger' && <Handle type="target" position={Position.Top} className="handle-target" />}
      <div className="flow-node-header">
        <span className="flow-node-icon"><Icon name={iconFor(data.nodeType)} size={16} /></span>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="flow-node-kind">{meta.label}</div>
          <div className="flow-node-title">{def?.label ?? data.nodeType}</div>
        </div>
        {data.hasError && <span className="flow-node-error" title="Este bloco tem erros">!</span>}
      </div>
      {summary && <div className="flow-node-body">{summary}</div>}

      {isButtons && (
        <div className="flow-node-buttons">
          {configButtons(data.config).map((b) => (
            <div key={b.id} className={`flow-node-button ${b.type === 'url' ? 'is-link' : ''}`}>
              <span>{b.type === 'url' ? '↗ ' : ''}{b.title || 'Botão'}</span>
              {b.type !== 'url' && outputs.includes(b.id) && (
                <Handle id={b.id} type="source" position={Position.Right} className="handle-source"
                  style={{ background: outputColor(b.id) }} />
              )}
            </div>
          ))}
          {outputs.includes('timeout') && (
            <div className="flow-node-button is-timeout">
              <span>Sem clique</span>
              <Handle id="timeout" type="source" position={Position.Right} className="handle-source"
                style={{ background: outputColor('timeout') }} />
            </div>
          )}
        </div>
      )}

      {nodeStats && nodeStats.sent > 0 && (
        <div className="flow-node-stats" title={`${nodeStats.sent} enviada(s) · ${nodeStats.clicked} com clique de ${nodeStats.trackable} com link/botão`}>
          <Icon name="chart" size={12} />
          <span>{nodeStats.sent} enviada{nodeStats.sent > 1 ? 's' : ''}</span>
          {nodeStats.trackable > 0 && <strong>CTR {ctrPercent(nodeStats.trackable, nodeStats.clicked)}</strong>}
        </div>
      )}

      {!isButtons && isBranch && (
        <div className="flow-node-outputs">
          {outputs.map((o) => (
            <span key={o} className="flow-node-output" style={{ color: outputColor(o) }}>{outputLabel(def, data.config, o)}</span>
          ))}
        </div>
      )}
      {!isButtons && outputs.map((output, i) => (
        <Handle
          key={output}
          id={isBranch ? output : undefined}
          type="source"
          position={Position.Bottom}
          className="handle-source"
          style={{ ...(isBranch ? { left: `${((i + 1) * 100) / (outputs.length + 1)}%` } : {}), background: outputColor(isBranch ? output : null) }}
        />
      ))}
      {isButtons && outputs.length === 1 && (
        <Handle type="source" position={Position.Bottom} className="handle-source" style={{ background: outputColor(null) }} />
      )}
    </div>
  )
}
