import { Link } from 'react-router-dom'
import { ErrorAlert, ExecutionStatusBadge, Loading } from '../components/ui'
import { AUTO_REFRESH_MS, useApi } from '../hooks/useApi'
import { ctrPercent, formatDuration, timeAgo } from '../lib/format'
import type { Dashboard, ExecutionSummary } from '../types'

function ExecutionList({ items, empty }: { items: ExecutionSummary[]; empty: string }) {
  if (!items.length) return <div className="empty small">{empty}</div>
  return (
    <div className="list">
      {items.map((e) => (
        <Link key={e.id} to={`/logs?execution=${e.id}`} className="list-item" style={{ color: 'inherit' }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontWeight: 550 }}>{e.workflow_name}</div>
            <div className="muted small" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {e.error || `${timeAgo(e.started_at)} · ${formatDuration(e.duration_ms)}`}
            </div>
          </div>
          <ExecutionStatusBadge status={e.status} />
        </Link>
      ))}
    </div>
  )
}

export function DashboardPage() {
  const { data, error, loading, reload } = useApi<Dashboard>('/api/dashboard', { refreshMs: AUTO_REFRESH_MS })

  if (loading && !data) return <Loading />
  return (
    <div className="page stack">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Visão geral das suas automações.</p>
        </div>
        <Link className="btn btn-primary" to="/workflows/new">
          + Novo workflow
        </Link>
      </div>
      <ErrorAlert message={error} onRetry={reload} />
      {data && (
        <>
          {!data.instagram.connected && (
            <div className="alert alert-info row">
              <span>
                {data.instagram.status === 'token_expired'
                  ? 'A conexão com o Instagram expirou. Reconecte para voltar a automatizar.'
                  : 'Conecte seu Instagram profissional para começar a receber mensagens e comentários.'}
              </span>
              <Link className="btn btn-instagram btn-sm" to="/instagram" style={{ marginLeft: 'auto' }}>
                {data.instagram.status === 'token_expired' ? 'Reconectar' : 'Conectar Instagram'}
              </Link>
            </div>
          )}
          <div className="grid grid-4">
            <div className="card card-body">
              <div className="stat-label">Instagram</div>
              <div className="stat-value" style={{ fontSize: 18 }}>
                {data.instagram.connected ? `@${data.instagram.account?.username}` : 'Não conectado'}
              </div>
              <div className="small muted" style={{ marginTop: 4 }}>
                {data.instagram.connected
                  ? `Último evento: ${timeAgo(data.instagram.account?.last_webhook_at)}`
                  : 'Conecte em Instagram'}
              </div>
            </div>
            <div className="card card-body">
              <div className="stat-label">Workflows</div>
              <div className="stat-value">{data.workflows.total}</div>
              <div className="small muted" style={{ marginTop: 4 }}>
                {data.workflows.active} ativo(s)
              </div>
            </div>
            <div className="card card-body">
              <div className="stat-label">Execuções (24h)</div>
              <div className="stat-value">{data.executions_24h.total}</div>
              <div className="small muted" style={{ marginTop: 4 }}>
                {data.executions_24h.success} com sucesso · {data.executions_24h.in_progress} em andamento
              </div>
            </div>
            <div className="card card-body">
              <div className="stat-label">Erros (24h)</div>
              <div className="stat-value" style={{ color: data.executions_24h.errors ? 'var(--danger)' : undefined }}>
                {data.executions_24h.errors}
              </div>
              <div className="small muted" style={{ marginTop: 4 }}>
                {data.contacts_count} contato(s) no total
              </div>
            </div>
          </div>
          <div className="grid grid-2">
            <div className="card card-body stack" style={{ gap: 14 }}>
              <div className="row">
                <div>
                  <div className="stat-label">CTR dos links e botões (7 dias)</div>
                  <div className="stat-value">{ctrPercent(data.ctr_7d.trackable, data.ctr_7d.clicked)}</div>
                </div>
                <span className="spacer" />
                <Link className="btn btn-sm" to="/inbox">
                  ✉ Caixa de entrada{data.unread_conversations ? ` · ${data.unread_conversations} não lida(s)` : ''}
                </Link>
              </div>
              <div className="ctr-bar" aria-hidden>
                <div style={{ width: `${data.ctr_7d.trackable ? (data.ctr_7d.clicked / data.ctr_7d.trackable) * 100 : 0}%` }} />
              </div>
              <div className="small muted">
                {data.ctr_7d.sent} DM(s) enviada(s) pela plataforma · {data.ctr_7d.trackable} com link rastreado ou botão ·{' '}
                {data.ctr_7d.clicked} com clique
              </div>
            </div>
            <div className="card">
              <div className="card-header"><h2>Links mais clicados (7 dias)</h2></div>
              {!data.top_links.length ? (
                <div className="empty small">Ative “Rastrear cliques nos links” nos blocos de mensagem para medir o CTR.</div>
              ) : (
                <div className="list">
                  {data.top_links.map((l) => (
                    <div key={l.url} className="list-item">
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div className="small" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.url}</div>
                        <div className="small muted">{l.clicks} clique(s) · enviado {l.sent}x</div>
                      </div>
                      <strong>{ctrPercent(l.sent, l.clicked)}</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="grid grid-2">
            <div className="card">
              <div className="card-header">
                <h2>Execuções recentes</h2>
                <Link to="/logs" className="small">
                  Ver todas
                </Link>
              </div>
              <ExecutionList items={data.recent_executions} empty="Nenhuma execução ainda." />
            </div>
            <div className="card">
              <div className="card-header">
                <h2>Erros recentes</h2>
                <Link to="/logs?status=error" className="small">
                  Ver erros
                </Link>
              </div>
              <ExecutionList items={data.recent_errors} empty="Nenhum erro. 🎉" />
            </div>
          </div>
          {!data.openai_configured && (
            <div className="alert alert-warning">
              A OpenAI não está configurada no servidor: nós de IA vão falhar até OPENAI_API_KEY ser definida.
            </div>
          )}
        </>
      )}
    </div>
  )
}
