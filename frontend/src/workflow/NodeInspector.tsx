import type { FieldDef, FlowButton, NodeTypeDef, ValidationIssue } from '../types'
import { CATEGORY_META, configButtons, iconFor } from './catalog'
import { Icon } from './Icon'

const VARIABLES = [
  ['{{message.text}}', 'texto da DM recebida'],
  ['{{comment.text}}', 'texto do comentário'],
  ['{{contact.username}}', 'username de quem interagiu'],
  ['{{contact.name}}', 'nome (quando disponível)'],
  ['{{contact.follows}}', 'true/false, depois da condição "Contato segue a conta?"'],
  ['{{story.url}}', 'link do story (menção ou resposta)'],
  ['{{referral.ref}}', 'origem do link ig.me'],
  ['{{reaction.emoji}}', 'emoji da reação'],
  ['{{reply.text}}', 'resposta do contato (após "Aguardar resposta")'],
  ['{{button.title}}', 'botão clicado (após "Mensagem com botões")'],
  ['{{ai.response}}', 'última resposta da IA'],
  ['{{vars.nome}}', 'variável definida no fluxo'],
]

function newButtonId(buttons: FlowButton[]): string {
  let n = buttons.length + 1
  while (buttons.some((b) => b.id === `b${n}`)) n++
  return `b${n}`
}

function ButtonsField({ value, style, onChange }: { value: FlowButton[]; style: string; onChange: (v: FlowButton[]) => void }) {
  const quick = style === 'quick_replies'
  const max = quick ? 13 : 3
  const update = (i: number, patch: Partial<FlowButton>) => onChange(value.map((b, n) => (n === i ? { ...b, ...patch } : b)))
  const move = (i: number, delta: number) => {
    const next = [...value]
    const [item] = next.splice(i, 1)
    next.splice(i + delta, 0, item)
    onChange(next)
  }
  return (
    <div className="stack" style={{ gap: 8 }}>
      {value.map((b, i) => (
        <div key={b.id} className="inspector-button">
          <div className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
            <input className="input" placeholder="Texto do botão" maxLength={20} value={b.title}
              onChange={(e) => update(i, { title: e.target.value })} aria-label={`Texto do botão ${i + 1}`} />
            {!quick && (
              <select className="select" style={{ width: 110 }} value={b.type ?? 'reply'} aria-label="Tipo do botão"
                onChange={(e) => update(i, { type: e.target.value as FlowButton['type'], url: e.target.value === 'url' ? b.url ?? 'https://' : undefined })}>
                <option value="reply">Resposta</option>
                <option value="url">Link</option>
              </select>
            )}
          </div>
          {b.type === 'url' && !quick && (
            <input className="input" placeholder="https://…" value={b.url ?? ''} onChange={(e) => update(i, { url: e.target.value })}
              aria-label={`Link do botão ${i + 1}`} />
          )}
          <div className="row small muted" style={{ gap: 4 }}>
            <span>{b.title.length}/20</span>
            <span className="spacer" />
            <button type="button" className="btn btn-sm btn-ghost" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Subir">↑</button>
            <button type="button" className="btn btn-sm btn-ghost" disabled={i === value.length - 1} onClick={() => move(i, 1)} aria-label="Descer">↓</button>
            <button type="button" className="btn btn-sm btn-ghost btn-danger" onClick={() => onChange(value.filter((_, n) => n !== i))}>Remover</button>
          </div>
        </div>
      ))}
      {value.length < max && (
        <button type="button" className="btn btn-sm" style={{ alignSelf: 'flex-start' }}
          onClick={() => onChange([...value, { id: newButtonId(value), title: '', type: 'reply' }])}>
          + Adicionar botão
        </button>
      )}
      {quick && value.some((b) => b.type === 'url') && (
        <div className="alert alert-warning small">Respostas rápidas não aceitam links. Mude o estilo para “Botões”.</div>
      )}
    </div>
  )
}

function FieldInput({ field, value, config, onChange }: { field: FieldDef; value: unknown; config: Record<string, unknown>; onChange: (v: unknown) => void }) {
  const id = `field-${field.name}`
  switch (field.type) {
    case 'buttons':
      return <ButtonsField value={configButtons(config)} style={String(config.style ?? 'buttons')} onChange={onChange} />
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

/** Campo com show_if só aparece quando a condição bate (valor atual ou o padrão do campo). */
function isVisible(field: FieldDef, def: NodeTypeDef, config: Record<string, unknown>): boolean {
  if (!field.show_if) return true
  const other = def.fields.find((f) => f.name === field.show_if!.field)
  const current = config[field.show_if.field] ?? other?.default
  return current === field.show_if.equals
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
      <div className="row" style={{ alignItems: 'flex-start', flexWrap: 'nowrap', gap: 12 }}>
        <span className="inspector-icon" style={{ background: meta.color }}><Icon name={iconFor(def.type)} size={18} /></span>
        <div>
          <div className="flow-node-kind" style={{ color: meta.color }}>{meta.label}</div>
          <h2 style={{ marginTop: 2 }}>{def.label}</h2>
          <p className="small muted" style={{ marginTop: 6 }}>{def.description}</p>
        </div>
      </div>
      {issues.length > 0 && (
        <div className="alert alert-error">
          <ul style={{ margin: 0 }}>{issues.map((i, n) => <li key={n}>{i.message}</li>)}</ul>
        </div>
      )}
      {def.fields.filter((field) => isVisible(field, def, config)).map((field) => (
        <div key={field.name} className="field">
          {field.type !== 'checkbox' && (
            <label htmlFor={`field-${field.name}`}>
              {field.label}
              {field.required && <span style={{ color: 'var(--danger)' }}> *</span>}
            </label>
          )}
          <FieldInput field={field} value={config[field.name]} config={config}
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
        <li>Comece pelo <strong>gatilho</strong>: DM, novo contato, story, link ig.me, reação ou comentário.</li>
        <li><strong>Arraste</strong> os blocos da esquerda para o quadro (ou clique para adicionar no centro).</li>
        <li>Puxe da bolinha de saída de um bloco até outro para conectar. Clique numa conexão para removê-la.</li>
        <li>Condições têm as saídas <span style={{ color: 'var(--success)' }}>Sim</span> e <span style={{ color: 'var(--danger)' }}>Não</span>; cada botão de resposta e o “Aguardar resposta” também criam caminhos.</li>
        <li>Arraste o fundo para mover o quadro; use a roda do mouse para zoom e “Organizar” para alinhar tudo.</li>
        <li>Atalhos: Delete remove, Ctrl+D duplica, Ctrl+S salva.</li>
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
