import type { FieldDef, NodeTypeDef, ValidationIssue } from '../types'
import { CATEGORY_META } from './catalog'

const VARIABLES = [
  ['{{message.text}}', 'texto da DM recebida'],
  ['{{comment.text}}', 'texto do comentário'],
  ['{{contact.username}}', 'username de quem interagiu'],
  ['{{contact.name}}', 'nome (quando disponível)'],
  ['{{ai.response}}', 'última resposta da IA'],
  ['{{vars.nome}}', 'variável definida no fluxo'],
]

function FieldInput({ field, value, onChange }: { field: FieldDef; value: unknown; onChange: (v: unknown) => void }) {
  const id = `field-${field.name}`
  switch (field.type) {
    case 'textarea':
      return <textarea id={id} className="textarea" value={String(value ?? '')} maxLength={field.max_length}
        onChange={(e) => onChange(e.target.value)} />
    case 'number':
      return <input id={id} className="input" type="number" value={value === undefined || value === null ? '' : String(value)}
        min={field.min} max={field.max} step={field.step ?? 1}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />
    case 'select':
      return (
        <select id={id} className="select" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)}>
          {field.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      )
    case 'checkbox':
      return (
        <label className="checkbox">
          <input id={id} type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
          {field.label}
        </label>
      )
    default:
      return <input id={id} className="input" value={String(value ?? '')} maxLength={field.max_length}
        onChange={(e) => onChange(e.target.value)} />
  }
}

export function NodeInspector({
  def,
  nodeId,
  config,
  issues,
  onChange,
  onDelete,
}: {
  def: NodeTypeDef | undefined
  nodeId: string
  config: Record<string, unknown>
  issues: ValidationIssue[]
  onChange: (config: Record<string, unknown>) => void
  onDelete: () => void
}) {
  if (!def) {
    return (
      <div className="inspector-body">
        <div className="alert alert-error">Tipo de nó desconhecido.</div>
        <button className="btn btn-danger" onClick={onDelete}>Remover nó</button>
      </div>
    )
  }
  const meta = CATEGORY_META[def.category]
  return (
    <div className="inspector-body">
      <div>
        <div className="flow-node-kind" style={{ color: meta.color }}>{meta.label}</div>
        <h2 style={{ marginTop: 2 }}>{def.label}</h2>
        <p className="small muted" style={{ marginTop: 6 }}>{def.description}</p>
      </div>
      {issues.length > 0 && (
        <div className="alert alert-error">
          <ul style={{ margin: 0 }}>{issues.map((i, n) => <li key={n}>{i.message}</li>)}</ul>
        </div>
      )}
      {def.fields.map((field) => (
        <div key={field.name} className="field">
          {field.type !== 'checkbox' && (
            <label htmlFor={`field-${field.name}`}>
              {field.label}
              {field.required && <span style={{ color: 'var(--danger)' }}> *</span>}
            </label>
          )}
          <FieldInput field={field} value={config[field.name]}
            onChange={(v) => onChange({ ...config, [field.name]: v })} />
          {field.help && <span className="help">{field.help}</span>}
        </div>
      ))}
      {def.category === 'trigger' && def.variables && (
        <div className="small muted">
          Variáveis deste gatilho: {def.variables.map((v) => <code key={v} style={{ marginRight: 4 }}>{`{{${v}}}`}</code>)}
        </div>
      )}
      <div className="row" style={{ justifyContent: 'space-between', marginTop: 8 }}>
        <span className="small muted">ID: <code>{nodeId}</code></span>
        <button className="btn btn-sm btn-danger" onClick={onDelete}>Remover nó</button>
      </div>
    </div>
  )
}

export function EditorHelp() {
  return (
    <div className="inspector-body">
      <h2>Como montar o fluxo</h2>
      <ol className="small muted" style={{ paddingLeft: 18, margin: 0, lineHeight: 1.7 }}>
        <li>Comece pelo <strong>gatilho</strong> (DM ou comentário).</li>
        <li>Clique nos blocos à esquerda para adicioná-los.</li>
        <li>Arraste da bolinha de baixo de um bloco até outro para conectar.</li>
        <li>Condições têm duas saídas: <span style={{ color: 'var(--success)' }}>Sim</span> e <span style={{ color: 'var(--danger)' }}>Não</span>.</li>
        <li>Selecione um bloco para configurar. Delete/Backspace remove o item selecionado.</li>
        <li>Salve, valide e ative.</li>
      </ol>
      <h3 style={{ marginTop: 8 }}>Variáveis</h3>
      <div className="small" style={{ display: 'grid', gap: 6 }}>
        {VARIABLES.map(([v, d]) => <div key={v}><code>{v}</code> <span className="muted">{d}</span></div>)}
      </div>
      <div className="alert alert-info small">
        Regras da Meta: DMs só podem ser enviadas até 24h após a última mensagem do cliente. Em comentários, use “Responder comentário por DM” (1 por comentário).
      </div>
    </div>
  )
}
