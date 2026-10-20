import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Empty, ErrorAlert, Loading, TagInput, Tags } from '../components/ui'
import { AUTO_REFRESH_MS, useApi } from '../hooks/useApi'
import { api, errorMessage } from '../lib/api'
import { formatDateTime, timeAgo, timeLeft } from '../lib/format'
import type { Contact, ContactDetail, ContactStatus, Paginated, TagCount } from '../types'

const EVENT_LABELS: Record<string, string> = {
  messages: 'Mensagem',
  comments: 'Comentário',
  live_comments: 'Comentário em live',
  message_reactions: 'Reação',
  messaging_referral: 'Link ig.me',
  messaging_postbacks: 'Clique em botão',
}
const STATUS_LABELS: Record<ContactStatus, string> = { active: 'Ativo', blocked: 'Bloqueado', archived: 'Arquivado' }
const PAGE_SIZE = 25

function ContactPanel({ id, tagSuggestions, onSaved }: { id: string; tagSuggestions: string[]; onSaved: () => void }) {
  const { data, error, loading, reload } = useApi<ContactDetail>(`/api/contacts/${id}`, { refreshMs: AUTO_REFRESH_MS })
  if (loading && !data) return <Loading />
  if (error) return <div className="card-body"><ErrorAlert message={error} /></div>
  if (!data) return null
  return <ContactForm data={data} tagSuggestions={tagSuggestions} onSaved={() => { reload(); onSaved() }} />
}

function ContactForm({ data, tagSuggestions, onSaved }: { data: ContactDetail; tagSuggestions: string[]; onSaved: () => void }) {
  const id = data.id
  // O formulário começa com os dados carregados; a atualização automática não apaga o que está sendo editado
  const [form, setForm] = useState<{ name: string; tags: string[]; notes: string; status: ContactStatus; automation_paused: boolean }>(
    () => ({ name: data.name ?? '', tags: data.tags, notes: data.notes ?? '', status: data.status, automation_paused: data.automation_paused }))
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)

  const save = async () => {
    setSaving(true)
    setMessage(null)
    try {
      await api.put(`/api/contacts/${id}`, { ...form, notes: form.notes || null })
      setMessage({ kind: 'success', text: 'Contato salvo.' })
      onSaved()
    } catch (err) {
      setMessage({ kind: 'error', text: errorMessage(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="card-header">
        <div style={{ minWidth: 0 }}>
          <h2>{data.username ? `@${data.username}` : 'Contato sem username'}</h2>
          {data.name && <div className="small muted">{data.name}</div>}
        </div>
        <Link className="btn btn-sm btn-primary" to={`/inbox/${data.id}`}>Abrir conversa</Link>
      </div>
      <div className="card-body stack" style={{ gap: 12 }}>
        <div className="small muted stack" style={{ gap: 4 }}>
          <div>Primeiro contato: {formatDateTime(data.created_at)} · Última interação: {timeAgo(data.last_interaction_at)}</div>
          <div>
            Janela de 24h:{' '}
            {data.can_message
              ? <span style={{ color: 'var(--success)' }}>aberta (resta {timeLeft(data.window_expires_at)})</span>
              : <span>fechada — só é possível enviar DM depois que o contato escrever</span>}
          </div>
        </div>
        <div className="field">
          <label htmlFor="c-name">Nome</label>
          <input id="c-name" className="input" maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="field">
          <label>Tags</label>
          <TagInput value={form.tags} suggestions={tagSuggestions} onChange={(tags) => setForm({ ...form, tags })} />
          <span className="help">Use tags para segmentar disparos em massa e condições nos workflows.</span>
        </div>
        <div className="field">
          <label htmlFor="c-notes">Notas internas</label>
          <textarea id="c-notes" className="textarea" maxLength={4000} value={form.notes}
            placeholder="Ex.: prefere atendimento à tarde" onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <div className="row" style={{ gap: 16 }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="c-status">Status</label>
            <select id="c-status" className="select" value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value as ContactStatus })}>
              {Object.entries(STATUS_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
          <label className="checkbox" style={{ flex: 1, marginTop: 18 }}>
            <input type="checkbox" checked={form.automation_paused}
              onChange={(e) => setForm({ ...form, automation_paused: e.target.checked })} />
            Pausar automação (atendimento humano)
          </label>
        </div>
        <div className="row">
          <button className="btn btn-primary btn-sm" onClick={save} disabled={saving}>{saving ? 'Salvando…' : 'Salvar'}</button>
          {message && <span className="small" style={{ color: message.kind === 'error' ? 'var(--danger)' : 'var(--success)' }}>{message.text}</span>}
        </div>
        <div className="small muted">ID no Instagram: <code>{data.ig_scoped_id}</code></div>
      </div>
      <div className="card-header"><h3>Histórico</h3></div>
      <div className="timeline">
        {data.events.map((ev) => (
          <div key={ev.id} className="timeline-item">
            <span className="timeline-dot" />
            <div style={{ minWidth: 0 }}>
              <div className="small"><strong>{EVENT_LABELS[ev.event_type] ?? ev.event_type}</strong> · {formatDateTime(ev.created_at)}</div>
              {ev.summary && <div className="small muted">{ev.summary}</div>}
            </div>
          </div>
        ))}
        {!data.events.length && <div className="empty small">Sem eventos.</div>}
      </div>
    </>
  )
}

export function ContactsPage() {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [tag, setTag] = useState<string | null>(null)
  const [offset, setOffset] = useState(0)
  const selected = params.get('id')
  const path = `/api/contacts?limit=${PAGE_SIZE}&offset=${offset}${query ? `&search=${encodeURIComponent(query)}` : ''}${tag ? `&tag=${encodeURIComponent(tag)}` : ''}`
  const { data, error, loading, reload } = useApi<Paginated<Contact>>(path, { refreshMs: AUTO_REFRESH_MS })
  const { data: tags, reload: reloadTags } = useApi<TagCount[]>('/api/contacts/tags')

  const select = (id: string) => setParams({ id }, { replace: true })

  return (
    <div className="page stack">
      <div className="page-header">
        <div>
          <h1>Contatos</h1>
          <p>Pessoas que interagiram com sua conta. Organize com tags e notas.</p>
        </div>
        <form className="row" onSubmit={(e) => { e.preventDefault(); setOffset(0); setQuery(search.trim()) }}>
          <input className="input" style={{ width: 240 }} placeholder="Buscar por nome ou username"
            value={search} onChange={(e) => setSearch(e.target.value)} />
          <button className="btn">Buscar</button>
        </form>
      </div>
      {tags && tags.length > 0 && (
        <div className="chip-row">
          <button className={`chip ${!tag ? 'active' : ''}`} onClick={() => { setTag(null); setOffset(0) }}>Todas</button>
          {tags.map((t) => (
            <button key={t.tag} className={`chip ${tag === t.tag ? 'active' : ''}`} onClick={() => { setTag(t.tag); setOffset(0) }}>
              {t.tag} <span className="chip-count">{t.count}</span>
            </button>
          ))}
        </div>
      )}
      <ErrorAlert message={error} onRetry={reload} />
      <div className="split">
        <div className="card">
          {loading && !data ? <Loading /> : !data?.items.length ? (
            <Empty title={query || tag ? 'Nenhum contato encontrado' : 'Nenhum contato ainda'}>
              <p>Os contatos aparecem automaticamente quando alguém envia DM ou comenta.</p>
            </Empty>
          ) : (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Contato</th><th>Tags</th><th>DM (24h)</th><th>Última interação</th></tr></thead>
                  <tbody>
                    {data.items.map((c) => (
                      <tr key={c.id} className={`clickable ${selected === c.id ? 'selected' : ''}`} onClick={() => select(c.id)}>
                        <td>
                          <div style={{ fontWeight: 550 }}>
                            {c.username ? `@${c.username}` : <span className="muted">sem username</span>}
                            {c.status !== 'active' && <span className="badge" style={{ marginLeft: 6 }}>{STATUS_LABELS[c.status]}</span>}
                            {c.automation_paused && <span className="badge badge-warning" style={{ marginLeft: 6 }}>Humano</span>}
                          </div>
                          {c.name && <div className="small muted">{c.name}</div>}
                        </td>
                        <td><Tags tags={c.tags} /></td>
                        <td>{c.can_message ? <span className="badge badge-success">Aberta</span> : <span className="badge">Fechada</span>}</td>
                        <td className="muted">{timeAgo(c.last_interaction_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="row card-body" style={{ justifyContent: 'space-between' }}>
                <span className="small muted">{data.total} contato(s)</span>
                <div className="row">
                  <button className="btn btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</button>
                  <button className="btn btn-sm" disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Próxima</button>
                </div>
              </div>
            </>
          )}
        </div>
        <div className="card">
          {selected ? (
            <ContactPanel key={selected} id={selected} tagSuggestions={tags?.map((t) => t.tag) ?? []}
              onSaved={() => { reload(); reloadTags() }} />
          ) : <div className="empty small">Selecione um contato para editar tags, notas e ver o histórico.</div>}
        </div>
      </div>
    </div>
  )
}
