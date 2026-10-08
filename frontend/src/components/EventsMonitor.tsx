import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../lib/api'
import { formatDateTime, timeAgo } from '../lib/format'
import { ErrorAlert } from './ui'

interface WebhookEventRow {
  id: string
  field: string
  status: 'received' | 'processed' | 'ignored' | 'error'
  status_reason: string | null
  received_at: string
  executions: number
  simulated: boolean
  text?: string
  from?: string
}

interface Rejection {
  received_at: string
  reason: string
  fields: string[]
}

interface EventsData {
  account: { username: string; last_webhook_at: string | null } | null
  events: WebhookEventRow[]
  rejections: Rejection[]
}

const FIELD_LABELS: Record<string, string> = { messages: 'DM', comments: 'Comentário' }
const STATUS: Record<WebhookEventRow['status'], [string, string]> = {
  received: ['Na fila', 'badge-info'],
  processed: ['Processado', 'badge-success'],
  ignored: ['Ignorado', 'badge-warning'],
  error: ['Erro', 'badge-danger'],
}
const REFRESH_MS = 10_000

/** Mostra os eventos que a Meta entregou ao AutoInsta e permite simular uma DM/comentário. */
export function EventsMonitor() {
  const [data, setData] = useState<EventsData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [kind, setKind] = useState<'message' | 'comment'>('message')
  const [text, setText] = useState('Olá! Quanto custa?')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const result = await api.get<EventsData>('/api/instagram/events?limit=30')
        if (active) {
          setData(result)
          setError(null)
        }
      } catch (err) {
        if (active) setError(errorMessage(err))
      }
    }
    load()
    const timer = window.setInterval(() => document.visibilityState === 'visible' && load(), REFRESH_MS)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  const simulate = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setNotice(null)
    setError(null)
    try {
      await api.post('/api/instagram/simulate', { kind, text })
      setNotice('Evento simulado criado. Ele aparece na lista em alguns segundos e roda seus workflows ativos sem enviar nada ao Instagram.')
      window.setTimeout(async () => setData(await api.get<EventsData>('/api/instagram/events?limit=30')), 2500)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2>Eventos recebidos</h2>
          <div className="small muted">Atualiza a cada 10 segundos · mostra o que a Meta entregou ao AutoInsta</div>
        </div>
        {data?.account && (
          <span className="small muted">Último evento real: {timeAgo(data.account.last_webhook_at)}</span>
        )}
      </div>

      {error && <div className="card-body"><ErrorAlert message={error} /></div>}

      {data && data.rejections.length > 0 && (
        <div className="card-body">
          <div className="alert alert-error">
            <strong>{data.rejections.length} evento(s) recusado(s) pela verificação de assinatura</strong> (desde o último
            deploy). Último: {formatDateTime(data.rejections[0].received_at)}: {data.rejections[0].reason}
            <div style={{ marginTop: 6 }}>
              A Meta pode assinar os eventos com a <strong>Chave secreta do app</strong> (Configurações do app → Básico). Coloque esse
              valor em <code>META_WEBHOOK_EXTRA_SECRETS</code> no servidor e mande uma nova DM.
            </div>
          </div>
        </div>
      )}

      <form className="card-body row" onSubmit={simulate} style={{ borderBottom: '1px solid var(--border)', alignItems: 'flex-end' }}>
        <div className="field">
          <label htmlFor="sim-kind">Simular</label>
          <select id="sim-kind" className="select" value={kind} onChange={(e) => setKind(e.target.value as 'message' | 'comment')}>
            <option value="message">DM recebida</option>
            <option value="comment">Comentário recebido</option>
          </select>
        </div>
        <div className="field" style={{ flex: 1, minWidth: 220 }}>
          <label htmlFor="sim-text">Texto</label>
          <input id="sim-text" className="input" maxLength={1000} required value={text} onChange={(e) => setText(e.target.value)} />
        </div>
        <button className="btn" disabled={busy || !text.trim()}>{busy ? 'Enviando…' : 'Simular evento'}</button>
      </form>
      {notice && <div className="card-body"><div className="alert alert-info">{notice}</div></div>}

      {!data ? null : data.events.length === 0 ? (
        <div className="empty small">
          Nenhum evento recebido ainda. Mande uma DM de <strong>outra conta</strong> para @{data.account?.username}. Em modo
          desenvolvimento, essa conta precisa ser testadora do app.
        </div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Quando</th><th>Tipo</th><th>Conteúdo</th><th>Status</th><th>Execuções</th></tr></thead>
            <tbody>
              {data.events.map((ev) => {
                const [label, cls] = STATUS[ev.status]
                return (
                  <tr key={ev.id}>
                    <td className="muted" style={{ whiteSpace: 'nowrap' }}>{formatDateTime(ev.received_at)}</td>
                    <td>
                      {FIELD_LABELS[ev.field] ?? ev.field}
                      {ev.simulated && <span className="badge" style={{ marginLeft: 6 }}>simulado</span>}
                    </td>
                    <td style={{ maxWidth: 320 }}>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{ev.text || <span className="muted">—</span>}</div>
                      {ev.from && <div className="small muted">de {ev.from}</div>}
                    </td>
                    <td>
                      <span className={`badge ${cls}`}>{label}</span>
                      {ev.status_reason && <div className="small muted">{ev.status_reason}</div>}
                    </td>
                    <td>{ev.executions > 0 ? <Link to="/logs">{ev.executions}</Link> : <span className="muted">0</span>}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
