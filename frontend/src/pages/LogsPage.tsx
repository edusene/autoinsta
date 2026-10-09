import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { Empty, ErrorAlert, ExecutionStatusBadge, Loading } from '../components/ui'
import { AUTO_REFRESH_MS, useApi } from '../hooks/useApi'
import { formatDateTime, formatDuration, formatTime, TRIGGER_LABELS } from '../lib/format'
import type { ExecutionDetail, ExecutionSummary, Paginated, Workflow } from '../types'

const PAGE_SIZE = 25
const STATUS_FILTERS = [
  ['', 'Todos'],
  ['success', 'Sucesso'],
  ['error', 'Erro'],
  ['waiting', 'Aguardando'],
  ['cancelled', 'Cancelada'],
]

function ExecutionPanel({ id }: { id: string }) {
  const { data, error, loading } = useApi<ExecutionDetail>(`/api/executions/${id}`, { refreshMs: AUTO_REFRESH_MS })
  if (loading && !data) return <Loading />
  if (error) return <div className="card-body"><ErrorAlert message={error} /></div>
  if (!data) return null
  return (
    <>
      <div className="card-header">
        <div>
          <h2>{data.workflow_name}</h2>
          <div className="small muted">{TRIGGER_LABELS[data.trigger_type] ?? data.trigger_type}</div>
        </div>
        <ExecutionStatusBadge status={data.status} />
      </div>
      <div className="card-body small stack" style={{ gap: 4 }}>
        <div><span className="muted">Início:</span> {formatDateTime(data.started_at)}</div>
        <div><span className="muted">Fim:</span> {formatDateTime(data.finished_at)}</div>
        <div><span className="muted">Duração:</span> {formatDuration(data.duration_ms)} · {data.steps_count} passo(s)</div>
        <div><span className="muted">ID:</span> <code>{data.id}</code></div>
        {data.error && <div className="alert alert-error" style={{ marginTop: 8 }}><strong>Erro:</strong> {data.error}</div>}
        {typeof data.trigger_event.summary === 'string' && (
          <div style={{ marginTop: 6 }}><span className="muted">Evento:</span> “{data.trigger_event.summary}”</div>
        )}
      </div>
      <div className="card-header"><h3>Passos</h3></div>
      <div className="timeline">
        {data.logs.map((log) => (
          <div key={log.id} className="timeline-item">
            <span className={`timeline-dot ${log.level}`} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="row small" style={{ justifyContent: 'space-between' }}>
                <strong>{log.message}</strong>
                <span className="muted">{formatTime(log.created_at)}</span>
              </div>
              {log.node_type && <div className="small muted">{log.node_type} · nó {log.node_id}</div>}
              {Object.keys(log.data ?? {}).length > 0 && <pre className="json">{JSON.stringify(log.data, null, 2)}</pre>}
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

export function LogsPage() {
  const { id: workflowId } = useParams()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? ''
  const selected = params.get('execution')
  const [offset, setOffset] = useState(0)
  const base = workflowId ? `/api/workflows/${workflowId}/executions` : '/api/logs'
  const { data, error, loading, reload } = useApi<Paginated<ExecutionSummary>>(
    `${base}?limit=${PAGE_SIZE}&offset=${offset}${status ? `&status=${status}` : ''}`,
    { refreshMs: AUTO_REFRESH_MS },
  )
  const workflow = useApi<Workflow>(workflowId ? `/api/workflows/${workflowId}` : null)

  const update = (key: string, value: string | null) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <div className="page stack">
      <div className="page-header">
        <div>
          <h1>{workflowId ? `Logs · ${workflow.data?.name ?? ''}` : 'Logs de execução'}</h1>
          <p>
            {workflowId ? <Link to={`/workflows/${workflowId}`}>← Voltar ao editor</Link> : 'Cada vez que um workflow roda, o resultado aparece aqui.'}
          </p>
        </div>
        <div className="row">
          <select className="select" style={{ width: 160 }} value={status}
            onChange={(e) => { setOffset(0); update('status', e.target.value) }}>
            {STATUS_FILTERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button className="btn" onClick={reload}>Atualizar</button>
        </div>
      </div>
      <ErrorAlert message={error} onRetry={reload} />
      <div className="split">
        <div className="card">
          {loading && !data ? <Loading /> : !data?.items.length ? (
            <Empty title="Nenhuma execução encontrada"><p>Ative um workflow e envie uma DM de teste para a conta conectada.</p></Empty>
          ) : (
            <>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Workflow</th><th>Status</th><th>Início</th><th>Duração</th></tr></thead>
                  <tbody>
                    {data.items.map((e) => (
                      <tr key={e.id} className={`clickable ${selected === e.id ? 'selected' : ''}`} onClick={() => update('execution', e.id)}>
                        <td>
                          <div style={{ fontWeight: 550 }}>{e.workflow_name}</div>
                          {e.error && <div className="small" style={{ color: 'var(--danger)' }}>{e.error}</div>}
                        </td>
                        <td><ExecutionStatusBadge status={e.status} /></td>
                        <td className="muted">{formatDateTime(e.started_at)}</td>
                        <td className="muted">{formatDuration(e.duration_ms)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="row card-body" style={{ justifyContent: 'space-between' }}>
                <span className="small muted">{data.total} execução(ões)</span>
                <div className="row">
                  <button className="btn btn-sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</button>
                  <button className="btn btn-sm" disabled={offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Próxima</button>
                </div>
              </div>
            </>
          )}
        </div>
        <div className="card">
          {selected ? <ExecutionPanel key={selected} id={selected} /> : <div className="empty small">Selecione uma execução para ver os detalhes.</div>}
        </div>
      </div>
    </div>
  )
}
