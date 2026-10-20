import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ConfirmButton, Empty, ErrorAlert, Loading, TagInput, Tags } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { api, errorMessage } from '../lib/api'
import { ctrPercent, formatDateTime } from '../lib/format'
import type { Broadcast, BroadcastRecipient, BroadcastStatus, FlowButton, Paginated, TagCount } from '../types'

const STATUS: Record<BroadcastStatus, [string, string]> = {
  draft: ['Rascunho', ''],
  scheduled: ['Agendado', 'badge-info'],
  sending: ['Enviando', 'badge-info'],
  done: ['Concluído', 'badge-success'],
  cancelled: ['Cancelado', 'badge-warning'],
  failed: ['Falhou', 'badge-danger'],
}
const RECIPIENT_STATUS: Record<BroadcastRecipient['status'], [string, string]> = {
  pending: ['Na fila', ''],
  processing: ['Enviando', 'badge-info'],
  sent: ['Enviado', 'badge-success'],
  skipped: ['Pulado', 'badge-warning'],
  failed: ['Falhou', 'badge-danger'],
}

function StatusBadge({ status }: { status: BroadcastStatus }) {
  const [label, cls] = STATUS[status]
  return <span className={`badge ${cls}`}>{label}</span>
}

export function BroadcastsPage() {
  const { data, error, loading, reload } = useApi<Broadcast[]>('/api/broadcasts', { refreshMs: 10_000 })
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const create = async () => {
    setBusy(true)
    try {
      const b = await api.post<Broadcast>('/api/broadcasts', { name: `Disparo ${new Date().toLocaleDateString('pt-BR')}` })
      navigate(`/broadcasts/${b.id}`)
    } catch (err) {
      setActionError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <div className="page stack">
      <div className="page-header">
        <div>
          <h1>Disparos em massa</h1>
          <p>Envie uma DM para vários contatos de uma vez, segmentando por tags.</p>
        </div>
        <button className="btn btn-primary" onClick={create} disabled={busy}>+ Novo disparo</button>
      </div>
      <div className="alert alert-info small">
        Regra da Meta: só recebe DM quem mandou mensagem para a conta nas <strong>últimas 24 horas</strong>.
        Os demais contatos do público são pulados automaticamente (e aparecem como “Pulado” no relatório).
      </div>
      <ErrorAlert message={error || actionError} onRetry={error ? reload : undefined} />
      {loading && !data ? <Loading /> : (
        <div className="card">
          {!data?.length ? (
            <Empty title="Nenhum disparo ainda">
              <p style={{ marginBottom: 14 }}>Crie uma mensagem e escolha quem vai receber.</p>
              <button className="btn btn-primary" onClick={create} disabled={busy}>Criar disparo</button>
            </Empty>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>Nome</th><th>Status</th><th>Público</th><th>Enviados</th><th>CTR</th><th>Criado</th></tr>
                </thead>
                <tbody>
                  {data.map((b) => (
                    <tr key={b.id} className="clickable" onClick={() => navigate(`/broadcasts/${b.id}`)}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{b.name}</div>
                        <div className="small muted" style={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{b.text || '—'}</div>
                      </td>
                      <td><StatusBadge status={b.status} /></td>
                      <td>{b.audience.tags?.length ? <Tags tags={b.audience.tags} /> : <span className="muted">Todos</span>}</td>
                      <td className="muted">{b.total_count ? `${b.sent_count} / ${b.total_count}` : '—'}</td>
                      <td>{ctrPercent(b.trackable_count, b.clicked_count)}</td>
                      <td className="muted">{formatDateTime(b.scheduled_at && b.status === 'scheduled' ? b.scheduled_at : b.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function newButtonId(buttons: FlowButton[]) {
  let n = buttons.length + 1
  while (buttons.some((b) => b.id === `b${n}`)) n++
  return `b${n}`
}

function DraftEditor({ broadcast, onChange }: { broadcast: Broadcast; onChange: (b: Broadcast) => void }) {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: broadcast.name,
    text: broadcast.text,
    buttons: broadcast.buttons,
    tags: broadcast.audience.tags ?? [],
    track_links: broadcast.track_links,
  })
  const [preview, setPreview] = useState<{ total: number; eligible: number } | null>(null)
  const [schedule, setSchedule] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)
  const { data: tags } = useApi<TagCount[]>('/api/contacts/tags')
  const tagKey = form.tags.join(',')

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api.post<{ total: number; eligible: number }>('/api/broadcasts/audience-preview', { tags: tagKey ? tagKey.split(',') : [] })
        .then(setPreview).catch(() => setPreview(null))
    }, 300)
    return () => window.clearTimeout(timer)
  }, [tagKey])

  const payload = () => ({
    name: form.name.trim() || broadcast.name,
    text: form.text,
    buttons: form.buttons.map((b) => ({ id: b.id, title: b.title, url: b.url ?? '' })),
    audience: { tags: form.tags },
    track_links: form.track_links,
  })

  const run = async (fn: () => Promise<Broadcast>, success: string) => {
    setBusy(true)
    setMessage(null)
    try {
      onChange(await fn())
      setMessage({ kind: 'success', text: success })
    } catch (err) {
      setMessage({ kind: 'error', text: errorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  const save = () => run(() => api.put<Broadcast>(`/api/broadcasts/${broadcast.id}`, payload()), 'Rascunho salvo.')
  const send = (scheduledAt: string | null) => run(async () => {
    await api.put<Broadcast>(`/api/broadcasts/${broadcast.id}`, payload())
    return api.post<Broadcast>(`/api/broadcasts/${broadcast.id}/send`,
      { scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : null })
  }, scheduledAt ? 'Disparo agendado.' : 'Disparo iniciado!')

  const setButton = (i: number, patch: Partial<FlowButton>) =>
    setForm({ ...form, buttons: form.buttons.map((b, n) => (n === i ? { ...b, ...patch } : b)) })
  const textLimit = form.buttons.length ? 640 : 1000

  return (
    <div className="broadcast-layout">
      <div className="card card-body stack">
        <div className="field">
          <label htmlFor="b-name">Nome interno</label>
          <input id="b-name" className="input" maxLength={120} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="b-text">Mensagem</label>
          <textarea id="b-text" className="textarea" rows={5} maxLength={textLimit} value={form.text}
            placeholder="Ex.: Oi! Hoje tem 20% de desconto em toda a loja 💜 https://seusite.com"
            onChange={(e) => setForm({ ...form, text: e.target.value })} />
          <span className="help">{form.text.length}/{textLimit} caracteres{form.buttons.length ? ' (com botões o limite é 640)' : ''}.</span>
        </div>
        <div className="field">
          <label>Botões de link (opcional, até 3)</label>
          {form.buttons.map((b, i) => (
            <div key={b.id} className="button-editor">
              <input className="input" placeholder="Texto do botão" maxLength={20} value={b.title}
                onChange={(e) => setButton(i, { title: e.target.value })} />
              <input className="input" placeholder="https://…" value={b.url ?? ''} onChange={(e) => setButton(i, { url: e.target.value })} />
              <button type="button" className="btn btn-sm btn-ghost" aria-label="Remover botão"
                onClick={() => setForm({ ...form, buttons: form.buttons.filter((_, n) => n !== i) })}>×</button>
            </div>
          ))}
          {form.buttons.length < 3 && (
            <button type="button" className="btn btn-sm" style={{ alignSelf: 'flex-start' }}
              onClick={() => setForm({ ...form, buttons: [...form.buttons, { id: newButtonId(form.buttons), title: '', type: 'url', url: '' }] })}>
              + Adicionar botão
            </button>
          )}
        </div>
        <div className="field">
          <label>Público (tags)</label>
          <TagInput value={form.tags} suggestions={tags?.map((t) => t.tag) ?? []} placeholder="Vazio = todos os contatos ativos"
            onChange={(t) => setForm({ ...form, tags: t })} />
          <span className="help">Recebe quem tem <strong>qualquer uma</strong> das tags. Contatos bloqueados ou arquivados não recebem.</span>
        </div>
        <label className="checkbox">
          <input type="checkbox" checked={form.track_links} onChange={(e) => setForm({ ...form, track_links: e.target.checked })} />
          Rastrear cliques nos links (CTR)
        </label>
        {message && <div className={`alert ${message.kind === 'error' ? 'alert-error' : 'alert-success'}`}>{message.text}</div>}
        <div className="row">
          <button className="btn" onClick={save} disabled={busy}>Salvar rascunho</button>
          <span className="spacer" />
          <ConfirmButton className="btn btn-danger btn-sm" confirmLabel="Excluir"
            onConfirm={async () => { await api.del(`/api/broadcasts/${broadcast.id}`); navigate('/broadcasts') }}>
            Excluir
          </ConfirmButton>
        </div>
      </div>
      <div className="stack">
        <div className="card card-body stack" style={{ gap: 10 }}>
          <div className="stat-label">Prévia</div>
          <div className="phone-preview">
            <div className="bubble bubble-out">
              <div className="bubble-text">{form.text || 'Sua mensagem aparece aqui.'}</div>
              {form.buttons.length > 0 && (
                <div className="bubble-buttons">
                  {form.buttons.map((b) => <span key={b.id} className="bubble-button">↗ {b.title || 'Botão'}</span>)}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="card card-body stack" style={{ gap: 10 }}>
          <div className="stat-label">Quem vai receber</div>
          {preview ? (
            <>
              <div className="stat-value">{preview.eligible}</div>
              <div className="small muted">
                de {preview.total} contato(s) no público estão dentro da janela de 24h agora.
                {preview.total > preview.eligible && ' Os demais serão pulados.'}
              </div>
            </>
          ) : <div className="small muted">Conecte o Instagram para ver o público.</div>}
          <button className="btn btn-primary" disabled={busy || !form.text.trim()} onClick={() => send(null)}>Enviar agora</button>
          <div className="row" style={{ gap: 6 }}>
            <input className="input" type="datetime-local" value={schedule} onChange={(e) => setSchedule(e.target.value)} style={{ flex: 1 }} />
            <button className="btn" disabled={busy || !schedule || !form.text.trim()} onClick={() => send(schedule)}>Agendar</button>
          </div>
          <span className="help small muted">No horário agendado, recebe quem estiver dentro da janela de 24h naquele momento.</span>
        </div>
      </div>
    </div>
  )
}

function Report({ broadcast, onChange }: { broadcast: Broadcast; onChange: (b: Broadcast) => void }) {
  const [filter, setFilter] = useState<BroadcastRecipient['status'] | ''>('')
  const live = broadcast.status === 'sending'
  const { data } = useApi<Paginated<BroadcastRecipient>>(
    `/api/broadcasts/${broadcast.id}/recipients?limit=100${filter ? `&status=${filter}` : ''}`, { refreshMs: live ? 3_000 : undefined })
  const [error, setError] = useState<string | null>(null)
  const done = broadcast.sent_count + broadcast.skipped_count + broadcast.failed_count
  const progress = broadcast.total_count ? Math.round((done / broadcast.total_count) * 100) : 0

  const cancel = async () => {
    try {
      onChange(await api.post<Broadcast>(`/api/broadcasts/${broadcast.id}/cancel`))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <div className="stack">
      <ErrorAlert message={error || broadcast.last_error} />
      {broadcast.status === 'scheduled' && (
        <div className="alert alert-info row">
          <span>Agendado para {formatDateTime(broadcast.scheduled_at)}.</span>
          <button className="btn btn-sm" style={{ marginLeft: 'auto' }} onClick={cancel}>Cancelar agendamento (volta a rascunho)</button>
        </div>
      )}
      <div className="grid grid-4">
        <div className="card card-body"><div className="stat-label">Enviados</div><div className="stat-value">{broadcast.sent_count}</div>
          <div className="small muted">de {broadcast.total_count} no público</div></div>
        <div className="card card-body"><div className="stat-label">Pulados</div><div className="stat-value">{broadcast.skipped_count}</div>
          <div className="small muted">fora da janela de 24h etc.</div></div>
        <div className="card card-body"><div className="stat-label">Falhas</div>
          <div className="stat-value" style={{ color: broadcast.failed_count ? 'var(--danger)' : undefined }}>{broadcast.failed_count}</div></div>
        <div className="card card-body"><div className="stat-label">CTR</div><div className="stat-value">{ctrPercent(broadcast.trackable_count, broadcast.clicked_count)}</div>
          <div className="small muted">{broadcast.clicked_count} clique(s) em {broadcast.trackable_count} mensagem(ns) com link</div></div>
      </div>
      {(live || broadcast.total_count > 0) && (
        <div className="card card-body stack" style={{ gap: 8 }}>
          <div className="row">
            <strong>{progress}% processado</strong>
            <span className="spacer" />
            {live && <ConfirmButton className="btn btn-sm btn-danger" confirmLabel="Parar envio" onConfirm={cancel}>Cancelar disparo</ConfirmButton>}
          </div>
          <div className="progress"><div className="progress-bar" style={{ width: `${progress}%` }} /></div>
        </div>
      )}
      <div className="card">
        <div className="card-header">
          <h2>Destinatários</h2>
          <select className="select" style={{ width: 180 }} value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)}>
            <option value="">Todos</option>
            {Object.entries(RECIPIENT_STATUS).map(([v, [l]]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        {!data ? <Loading /> : !data.items.length ? <div className="empty small">Nenhum destinatário.</div> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Contato</th><th>Status</th><th>Detalhe</th><th>Clicou</th></tr></thead>
              <tbody>
                {data.items.map((r) => (
                  <tr key={r.id}>
                    <td><Link to={`/inbox/${r.contact_id}`}>{r.username ? `@${r.username}` : r.name || 'Contato'}</Link></td>
                    <td><span className={`badge ${RECIPIENT_STATUS[r.status][1]}`}>{RECIPIENT_STATUS[r.status][0]}</span></td>
                    <td className="small muted">{r.reason || formatDateTime(r.processed_at)}</td>
                    <td>{r.clicked_at ? <span style={{ color: 'var(--success)' }}>✓</span> : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <div className="card card-body">
        <div className="stat-label" style={{ marginBottom: 8 }}>Mensagem enviada</div>
        <div className="phone-preview">
          <div className="bubble bubble-out">
            <div className="bubble-text">{broadcast.text}</div>
            {broadcast.buttons.length > 0 && (
              <div className="bubble-buttons">{broadcast.buttons.map((b) => <span key={b.id} className="bubble-button">↗ {b.title}</span>)}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export function BroadcastEditorPage() {
  const { id } = useParams()
  // Atualiza sozinho para acompanhar o envio (o rascunho em edição fica no estado do formulário)
  const { data, setData, error, loading } = useApi<Broadcast>(`/api/broadcasts/${id}`, { refreshMs: 4_000 })

  if (loading && !data) return <Loading />
  if (error && !data) return <div className="page"><ErrorAlert message={error} /><Link to="/broadcasts">Voltar</Link></div>
  if (!data) return null
  return (
    <div className="page stack">
      <div className="page-header">
        <div>
          <Link to="/broadcasts" className="small">← Disparos</Link>
          <h1 style={{ marginTop: 6 }}>{data.name} <StatusBadge status={data.status} /></h1>
        </div>
      </div>
      {data.status === 'draft'
        ? <DraftEditor key={data.id} broadcast={data} onChange={setData} />
        : <Report broadcast={data} onChange={setData} />}
    </div>
  )
}
