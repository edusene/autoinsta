import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Empty, ErrorAlert, Loading, Tags } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { api, errorMessage } from '../lib/api'
import { formatDateTime, timeAgo, timeLeft } from '../lib/format'
import type { Conversation, ConversationDetail, InboxMessage, Paginated } from '../types'

const SOURCE_LABELS: Record<InboxMessage['source'], string> = {
  contact: '',
  workflow: 'Workflow',
  inbox: 'Você',
  broadcast: 'Disparo',
  instagram_app: 'App do Instagram',
}

function displayName(c: { username: string | null; name: string | null }) {
  return c.username ? `@${c.username}` : c.name || 'Contato sem username'
}

function Initials({ c }: { c: { username: string | null; name: string | null } }) {
  const base = (c.name || c.username || '?').replace('@', '')
  return <span className="avatar avatar-sm" aria-hidden>{base.slice(0, 1).toUpperCase()}</span>
}

function MessageBubble({ m }: { m: InboxMessage }) {
  const out = m.direction === 'out'
  return (
    <div className={`bubble-row ${out ? 'out' : 'in'}`}>
      <div className={`bubble ${out ? 'bubble-out' : 'bubble-in'} ${m.status === 'failed' ? 'bubble-failed' : ''}`}>
        <div className="bubble-text">{m.text || '[sem texto]'}</div>
        {m.buttons.length > 0 && (
          <div className="bubble-buttons">
            {m.buttons.map((b) => (
              <span key={b.id} className="bubble-button">{b.type === 'url' ? '↗ ' : ''}{b.title}</span>
            ))}
          </div>
        )}
      </div>
      <div className="bubble-meta">
        {out && SOURCE_LABELS[m.source] && <span>{SOURCE_LABELS[m.source]}</span>}
        <span title={formatDateTime(m.created_at)}>{timeAgo(m.created_at)}</span>
        {m.status === 'sending' && <span>enviando…</span>}
        {m.status === 'failed' && <span style={{ color: 'var(--danger)' }} title={m.error ?? ''}>falhou: {m.error}</span>}
        {m.clicked_at && <span style={{ color: 'var(--success)' }}>✓ clicou</span>}
      </div>
    </div>
  )
}

function Thread({ contactId, onRead }: { contactId: string; onRead: () => void }) {
  const { data, setData, error, loading, reload } = useApi<ConversationDetail>(
    `/api/inbox/conversations/${contactId}`, { refreshMs: 5_000 })
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const [busyToggle, setBusyToggle] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const lastId = data?.messages.at(-1)?.id

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [lastId])

  const unread = data?.contact.unread_count ?? 0
  useEffect(() => {
    if (unread > 0) api.post(`/api/inbox/conversations/${contactId}/read`).then(onRead).catch(() => {})
  }, [unread, contactId, onRead])

  if (loading && !data) return <Loading />
  if (error && !data) return <div className="card-body"><ErrorAlert message={error} onRetry={reload} /></div>
  if (!data) return null
  const { contact, messages } = data

  const send = async (e?: FormEvent) => {
    e?.preventDefault()
    if (!text.trim() || sending) return
    setSending(true)
    setSendError(null)
    try {
      setData(await api.post<ConversationDetail>(`/api/inbox/conversations/${contactId}/messages`, { text: text.trim() }))
      setText('')
    } catch (err) {
      setSendError(errorMessage(err))
    } finally {
      setSending(false)
    }
  }

  const togglePause = async () => {
    setBusyToggle(true)
    try {
      await api.put(`/api/contacts/${contactId}`, { automation_paused: !contact.automation_paused })
      await reload()
    } catch (err) {
      setSendError(errorMessage(err))
    } finally {
      setBusyToggle(false)
    }
  }

  return (
    <div className="thread">
      <div className="thread-header">
        <Link to="/inbox" className="btn btn-ghost btn-sm thread-back" aria-label="Voltar">←</Link>
        <Initials c={contact} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 600 }}>{displayName(contact)}</div>
          <div className="small muted row" style={{ gap: 6 }}>
            {contact.name && contact.username && <span>{contact.name}</span>}
            <Tags tags={contact.tags} />
          </div>
        </div>
        <button className={`btn btn-sm ${contact.automation_paused ? 'btn-primary' : ''}`} onClick={togglePause}
          disabled={busyToggle} title="Com a automação pausada, os workflows não respondem este contato.">
          {contact.automation_paused ? '▶ Retomar automação' : '⏸ Pausar automação'}
        </button>
        <Link className="btn btn-sm" to={`/contacts?id=${contact.id}`}>Perfil</Link>
      </div>
      {contact.automation_paused && (
        <div className="thread-notice">Atendimento humano: a automação está pausada para este contato.</div>
      )}
      <div className="thread-messages">
        {messages.length === 0 && <div className="empty small">Nenhuma mensagem registrada ainda.</div>}
        {messages.map((m) => <MessageBubble key={m.id} m={m} />)}
        <div ref={endRef} />
      </div>
      <form className="composer" onSubmit={send}>
        {sendError && <div className="alert alert-error small">{sendError}</div>}
        {contact.can_message ? (
          <div className="small muted">Janela de 24h da Meta: resta {timeLeft(contact.window_expires_at)} para responder.</div>
        ) : (
          <div className="alert alert-warning small">
            Fora da janela de 24h: a Meta só permite responder depois que o contato enviar uma nova mensagem.
          </div>
        )}
        <div className="composer-row">
          <textarea className="textarea" rows={2} maxLength={1000} value={text} disabled={!contact.can_message}
            placeholder={contact.can_message ? 'Escreva uma resposta… (Enter envia, Shift+Enter quebra linha)' : ''}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }} />
          <button className="btn btn-primary" disabled={!contact.can_message || sending || !text.trim()}>
            {sending ? 'Enviando…' : 'Enviar'}
          </button>
        </div>
      </form>
    </div>
  )
}

export function InboxPage() {
  const { contactId } = useParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<'all' | 'unread'>('all')
  const path = `/api/inbox/conversations?limit=50&filter=${filter}${query ? `&search=${encodeURIComponent(query)}` : ''}`
  const { data, setData, error, loading, reload } = useApi<Paginated<Conversation> & { unread_conversations: number }>(
    path, { refreshMs: 8_000 })

  // Ao abrir a conversa, zera o contador na lista sem esperar a próxima atualização
  const onRead = useCallback(
    () => setData((d) => d && { ...d, items: d.items.map((c) => (c.id === contactId ? { ...c, unread_count: 0 } : c)) }),
    [contactId, setData],
  )

  return (
    <div className={`inbox ${contactId ? 'has-selection' : ''}`}>
      <aside className="inbox-list">
        <div className="inbox-list-header">
          <h1 style={{ fontSize: 18 }}>Caixa de entrada</h1>
          <form onSubmit={(e) => { e.preventDefault(); setQuery(search.trim()) }}>
            <input className="input" placeholder="Buscar conversa" value={search} onChange={(e) => setSearch(e.target.value)} />
          </form>
          <div className="segmented" style={{ alignSelf: 'flex-start' }}>
            <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>Todas</button>
            <button className={filter === 'unread' ? 'active' : ''} onClick={() => setFilter('unread')}>
              Não lidas{data?.unread_conversations ? ` (${data.unread_conversations})` : ''}
            </button>
          </div>
        </div>
        <ErrorAlert message={error} onRetry={reload} />
        {loading && !data ? <Loading /> : !data?.items.length ? (
          <Empty title={query || filter === 'unread' ? 'Nada por aqui' : 'Nenhuma conversa ainda'}>
            <p className="small">As DMs recebidas aparecem aqui automaticamente.</p>
          </Empty>
        ) : (
          <div className="conv-items">
            {data.items.map((c) => (
              <button key={c.id} className={`conv-item ${c.id === contactId ? 'active' : ''} ${c.unread_count ? 'unread' : ''}`}
                onClick={() => navigate(`/inbox/${c.id}`)}>
                <Initials c={c} />
                <span className="conv-main">
                  <span className="conv-top">
                    <span className="conv-name">{displayName(c)}</span>
                    <span className="conv-time">{timeAgo(c.last_message_at)}</span>
                  </span>
                  <span className="conv-preview">{c.last_message_preview || ' '}</span>
                  <span className="conv-flags">
                    {c.automation_paused && <span className="badge badge-warning">Humano</span>}
                    {!c.can_message && <span className="badge">24h expirada</span>}
                    <Tags tags={c.tags.slice(0, 2)} />
                  </span>
                </span>
                {c.unread_count > 0 && <span className="nav-badge">{c.unread_count}</span>}
              </button>
            ))}
          </div>
        )}
      </aside>
      <section className="inbox-thread">
        {contactId ? <Thread key={contactId} contactId={contactId} onRead={onRead} /> : (
          <div className="center" style={{ height: '100%' }}>
            <Empty title="Selecione uma conversa">
              <p className="small">Responda manualmente, pause a automação para atendimento humano e veja o que os fluxos enviaram.</p>
            </Empty>
          </div>
        )}
      </section>
    </div>
  )
}
