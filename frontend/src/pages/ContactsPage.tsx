import { useState } from 'react'
import { Empty, ErrorAlert, Loading } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { formatDateTime, timeAgo } from '../lib/format'
import type { Contact, ContactDetail, Paginated } from '../types'

const EVENT_LABELS: Record<string, string> = { messages: 'Mensagem', comments: 'Comentário' }
const PAGE_SIZE = 25

function ContactPanel({ id }: { id: string }) {
  const { data, error, loading } = useApi<ContactDetail>(`/api/contacts/${id}`)
  if (loading && !data) return <Loading />
  if (error) return <div className="card-body"><ErrorAlert message={error} /></div>
  if (!data) return null
  return (
    <>
      <div className="card-header">
        <div>
          <h2>{data.username ? `@${data.username}` : 'Contato sem username'}</h2>
          {data.name && <div className="small muted">{data.name}</div>}
        </div>
      </div>
      <div className="card-body small muted stack" style={{ gap: 4 }}>
        <div>Primeiro contato: {formatDateTime(data.created_at)}</div>
        <div>Última interação: {formatDateTime(data.last_interaction_at)}</div>
        <div>ID no Instagram: <code>{data.ig_scoped_id}</code></div>
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
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const path = `/api/contacts?limit=${PAGE_SIZE}&offset=${offset}${query ? `&search=${encodeURIComponent(query)}` : ''}`
  const { data, error, loading, reload } = useApi<Paginated<Contact>>(path)

  return (
    <div className="page stack">
      <div className="page-header">
        <div>
          <h1>Contatos</h1>
          <p>Pessoas que interagiram com sua conta por mensagem ou comentário.</p>
        </div>
        <form className="row" onSubmit={(e) => { e.preventDefault(); setOffset(0); setQuery(search.trim()) }}>
          <input className="input" style={{ width: 240 }} placeholder="Buscar por nome ou username"
            value={search} onChange={(e) => setSearch(e.target.value)} />
          <button className="btn">Buscar</button>
        </form>
      </div>
      <ErrorAlert message={error} onRetry={reload} />
      <div className="split">
        <div className="card">
          {loading && !data ? <Loading /> : !data?.items.length ? (
            <Empty title={query ? 'Nenhum contato encontrado' : 'Nenhum contato ainda'}>
              <p>Os contatos aparecem automaticamente quando alguém envia DM ou comenta.</p>
            </Empty>
          ) : (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Contato</th><th>Último evento</th><th>Última interação</th></tr></thead>
                  <tbody>
                    {data.items.map((c) => (
                      <tr key={c.id} className={`clickable ${selected === c.id ? 'selected' : ''}`} onClick={() => setSelected(c.id)}>
                        <td>
                          <div style={{ fontWeight: 550 }}>{c.username ? `@${c.username}` : <span className="muted">sem username</span>}</div>
                          {c.name && <div className="small muted">{c.name}</div>}
                        </td>
                        <td className="muted">{EVENT_LABELS[c.last_event_type ?? ''] ?? '—'}</td>
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
          {selected ? <ContactPanel key={selected} id={selected} /> : <div className="empty small">Selecione um contato para ver o histórico.</div>}
        </div>
      </div>
    </div>
  )
}
