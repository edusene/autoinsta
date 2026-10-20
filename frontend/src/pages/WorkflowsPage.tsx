import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ConfirmButton, Empty, ErrorAlert, Loading, WorkflowStatusBadge } from '../components/ui'
import { AUTO_REFRESH_MS, useApi } from '../hooks/useApi'
import { api, ApiError, errorMessage } from '../lib/api'
import { ctrPercent, formatDateTime, TRIGGER_LABELS } from '../lib/format'
import type { Workflow, WorkflowSummary } from '../types'
import { WORKFLOW_TEMPLATES, type WorkflowTemplate } from '../workflow/templates'

export function WorkflowsPage() {
  const { data, error, loading, reload } = useApi<WorkflowSummary[]>('/api/workflows', { refreshMs: AUTO_REFRESH_MS })
  const navigate = useNavigate()
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const run = async (id: string, fn: () => Promise<unknown>) => {
    setBusyId(id)
    setActionError(null)
    try {
      await fn()
      await reload()
    } catch (err) {
      if (err instanceof ApiError && err.code === 'WORKFLOW_INVALID') {
        setActionError('Este workflow tem erros. Abra o editor para corrigir antes de ativar.')
      } else {
        setActionError(errorMessage(err))
      }
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="page stack">
      <div className="page-header">
        <div>
          <h1>Workflows</h1>
          <p>Automações disparadas por mensagens e comentários do Instagram.</p>
        </div>
        <Link className="btn btn-primary" to="/workflows/new">
          + Novo workflow
        </Link>
      </div>
      <ErrorAlert message={error || actionError} onRetry={error ? reload : undefined} />
      {loading && !data ? (
        <Loading />
      ) : (
        <div className="card">
          {!data?.length ? (
            <Empty title="Nenhum workflow ainda">
              <p style={{ marginBottom: 14 }}>Crie seu primeiro fluxo de automação.</p>
              <Link className="btn btn-primary" to="/workflows/new">
                Criar workflow
              </Link>
            </Empty>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Nome</th>
                    <th>Status</th>
                    <th>Gatilho</th>
                    <th>Última atualização</th>
                    <th>Execuções</th>
                    <th title="Cliques em links rastreados e botões / mensagens com link ou botão">CTR</th>
                    <th style={{ textAlign: 'right' }}>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((w) => (
                    <tr key={w.id}>
                      <td>
                        <Link to={`/workflows/${w.id}`} style={{ fontWeight: 600, color: 'var(--text)' }}>
                          {w.name}
                        </Link>
                        {w.description && <div className="small muted">{w.description}</div>}
                      </td>
                      <td>
                        <WorkflowStatusBadge status={w.status} />
                      </td>
                      <td className="muted">{TRIGGER_LABELS[w.trigger_type ?? ''] ?? '—'}</td>
                      <td className="muted">{formatDateTime(w.updated_at)}</td>
                      <td>
                        <Link to={`/workflows/${w.id}/logs`}>{w.executions_count}</Link>
                        {w.errors_count > 0 && (
                          <span className="small" style={{ color: 'var(--danger)' }}>
                            {' '}
                            ({w.errors_count} erro{w.errors_count > 1 ? 's' : ''})
                          </span>
                        )}
                      </td>
                      <td title={`${w.clicked_count} clique(s) em ${w.trackable_count} mensagem(ns)`}>
                        {ctrPercent(w.trackable_count, w.clicked_count)}
                      </td>
                      <td>
                        <div className="row" style={{ justifyContent: 'flex-end', gap: 6 }}>
                          <Link className="btn btn-sm" to={`/workflows/${w.id}`}>
                            Editar
                          </Link>
                          {w.status === 'active' ? (
                            <button className="btn btn-sm" disabled={busyId === w.id}
                              onClick={() => run(w.id, () => api.post(`/api/workflows/${w.id}/deactivate`))}>
                              Desativar
                            </button>
                          ) : (
                            <button className="btn btn-sm" disabled={busyId === w.id}
                              onClick={() => run(w.id, () => api.post(`/api/workflows/${w.id}/activate`))}>
                              Ativar
                            </button>
                          )}
                          <button className="btn btn-sm" disabled={busyId === w.id}
                            onClick={() =>
                              run(w.id, async () => {
                                const copy = await api.post<Workflow>(`/api/workflows/${w.id}/duplicate`)
                                navigate(`/workflows/${copy.id}`)
                              })
                            }>
                            Duplicar
                          </button>
                          <ConfirmButton className="btn btn-sm btn-danger" confirmLabel="Excluir"
                            onConfirm={() => run(w.id, () => api.del(`/api/workflows/${w.id}`))}>
                            Excluir
                          </ConfirmButton>
                        </div>
                      </td>
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

export function NewWorkflowPage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [templateId, setTemplateId] = useState('blank')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const chooseTemplate = (t: WorkflowTemplate) => {
    setTemplateId(t.id)
    if (t.graph) {
      if (!name.trim()) setName(t.name)
      if (!description.trim()) setDescription(t.description)
    }
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const template = WORKFLOW_TEMPLATES.find((t) => t.id === templateId)
      const wf = await api.post<Workflow>('/api/workflows', {
        name: name.trim(),
        description: description.trim() || null,
        graph: template?.graph ?? null,
      })
      navigate(`/workflows/${wf.id}`, { replace: true })
    } catch (err) {
      setError(errorMessage(err))
      setBusy(false)
    }
  }

  return (
    <div className="page" style={{ maxWidth: 720 }}>
      <div className="page-header">
        <h1>Novo workflow</h1>
      </div>
      <form className="card card-body stack" onSubmit={submit}>
        <ErrorAlert message={error} />
        <div className="field">
          <label>Modelo</label>
          <div className="template-grid" role="radiogroup" aria-label="Modelo">
            {WORKFLOW_TEMPLATES.map((t) => (
              <button key={t.id} type="button" role="radio" aria-checked={templateId === t.id}
                className={`template-card ${templateId === t.id ? 'active' : ''}`} onClick={() => chooseTemplate(t)}>
                <strong>{t.name}</strong>
                <span className="small muted">{t.description}</span>
              </button>
            ))}
          </div>
          <span className="help">Modelos com IA exigem a OpenAI configurada. Revise os textos no editor antes de ativar.</span>
        </div>
        <div className="field">
          <label htmlFor="name">Nome</label>
          <input id="name" className="input" required maxLength={120} autoFocus value={name}
            placeholder="Ex.: Atendimento por DM" onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="desc">Descrição (opcional)</label>
          <textarea id="desc" className="textarea" maxLength={1000} value={description}
            onChange={(e) => setDescription(e.target.value)} />
        </div>
        <div className="row">
          <button className="btn btn-primary" disabled={busy || !name.trim()}>
            {busy ? 'Criando…' : 'Criar e abrir editor'}
          </button>
          <Link className="btn btn-ghost" to="/workflows">
            Cancelar
          </Link>
        </div>
      </form>
    </div>
  )
}
