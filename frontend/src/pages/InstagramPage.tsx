import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ConfirmButton, ErrorAlert, Loading } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { api, errorMessage } from '../lib/api'
import { formatDateTime, timeAgo } from '../lib/format'
import type { DiagnosticCheck, InstagramStatus } from '../types'

const CHECK_ICON = { ok: '✓', warning: '!', error: '✕' }

function Diagnostics() {
  const { data, error, loading, reload } = useApi<{ healthy: boolean; checks: DiagnosticCheck[] }>(
    '/api/instagram/diagnostics',
  )
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const resubscribe = async () => {
    setBusy(true)
    setActionError(null)
    try {
      await api.post('/api/instagram/resubscribe')
      await reload()
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const webhookFailed = data?.checks.some((c) => c.key === 'webhook_subscribed' && c.status !== 'ok')

  return (
    <div className="card">
      <div className="card-header">
        <h2>Diagnóstico da integração</h2>
        <div className="row">
          {webhookFailed && (
            <button className="btn btn-sm" onClick={resubscribe} disabled={busy}>
              Reativar webhooks
            </button>
          )}
          <button className="btn btn-sm" onClick={reload} disabled={loading}>
            {loading ? 'Verificando…' : 'Verificar novamente'}
          </button>
        </div>
      </div>
      {(error || actionError) && (
        <div className="card-body">
          <ErrorAlert message={error || actionError} />
        </div>
      )}
      {loading && !data && <Loading />}
      {data?.checks.map((check) => (
        <div key={check.key} className="check-row">
          <span className={`check-icon check-${check.status}`}>{CHECK_ICON[check.status]}</span>
          <div>
            <div style={{ fontWeight: 550 }}>{check.label}</div>
            {check.detail && <div className="small muted">{check.detail}</div>}
          </div>
        </div>
      ))}
    </div>
  )
}

export function InstagramPage() {
  const { data, error, loading, reload, setData } = useApi<InstagramStatus>('/api/instagram/status')
  const [params] = useSearchParams()
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const connect = async () => {
    setBusy(true)
    setActionError(null)
    try {
      const { authorize_url } = await api.get<{ authorize_url: string }>('/api/instagram/connect')
      window.location.href = authorize_url
    } catch (err) {
      setActionError(errorMessage(err))
      setBusy(false)
    }
  }

  // Token gerado no painel da Meta e configurado no servidor (sem passar pelo login do Instagram)
  const connectWithServerToken = async () => {
    setBusy(true)
    setActionError(null)
    try {
      setData(await api.post<InstagramStatus>('/api/instagram/connect-token'))
    } catch (err) {
      setActionError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const disconnect = async () => {
    setActionError(null)
    try {
      setData(await api.post<InstagramStatus>('/api/instagram/disconnect'))
    } catch (err) {
      setActionError(errorMessage(err))
    }
  }

  if (loading && !data) return <Loading />
  const account = data?.account
  const expired = data?.status === 'token_expired'
  const options = data?.connect_options ?? { oauth: false, server_token: false }
  const viaServerToken = account?.connection_method === 'server_token'
  const reconnect = viaServerToken && options.server_token ? connectWithServerToken : connect
  const canReconnect = viaServerToken ? options.server_token : options.oauth

  return (
    <div className="page stack" style={{ maxWidth: 860 }}>
      <div className="page-header">
        <div>
          <h1>Instagram</h1>
          <p>Conexão oficial via Meta (Instagram API com login do Instagram).</p>
        </div>
      </div>
      {params.get('connected') && data?.connected && (
        <div className="alert alert-success">Instagram conectado com sucesso!</div>
      )}
      <ErrorAlert message={error || actionError} onRetry={error ? reload : undefined} />

      <div className="card card-body">
        {account && !expired && data?.connected ? (
          <div className="row" style={{ gap: 16 }}>
            {account.profile_picture_url ? (
              <img className="avatar" src={account.profile_picture_url} alt="" referrerPolicy="no-referrer" />
            ) : (
              <span className="avatar">{account.username?.[0]?.toUpperCase()}</span>
            )}
            <div>
              <div style={{ fontWeight: 600, fontSize: 16 }}>@{account.username}</div>
              <div className="row small muted" style={{ gap: 8, marginTop: 4 }}>
                <span className="badge badge-success">Conectado</span>
                <span>Desde {formatDateTime(account.connected_at)}</span>
                <span>· Último evento {timeAgo(account.last_webhook_at)}</span>
                {viaServerToken && <span>· via token do painel da Meta</span>}
              </div>
            </div>
            <span className="spacer" />
            {canReconnect && (
              <button className="btn" onClick={reconnect} disabled={busy}>
                Reconectar
              </button>
            )}
            <ConfirmButton onConfirm={disconnect} confirmLabel="Desconectar">
              Desconectar
            </ConfirmButton>
          </div>
        ) : (
          <div className="stack" style={{ alignItems: 'flex-start' }}>
            <div>
              <h2>{expired ? 'Conexão expirada' : 'Conecte seu Instagram'}</h2>
              <p className="muted" style={{ marginTop: 6, maxWidth: 560 }}>
                {expired
                  ? `A autorização de @${account?.username} expirou ou foi revogada. Reconecte para reativar as automações.`
                  : 'Só usamos as permissões necessárias para ler e responder mensagens e comentários.'}
              </p>
            </div>
            <div className="row">
              {options.server_token && (
                <button className="btn btn-instagram btn-lg" onClick={connectWithServerToken} disabled={busy}>
                  {busy ? 'Conectando…' : 'Conectar com o token do painel da Meta'}
                </button>
              )}
              {options.oauth && (
                <button className={`btn btn-lg ${options.server_token ? '' : 'btn-instagram'}`} onClick={connect} disabled={busy}>
                  {busy ? 'Abrindo Instagram…' : expired ? 'Reconectar Instagram' : 'Conectar com login do Instagram'}
                </button>
              )}
            </div>
            {!options.oauth && !options.server_token && (
              <div className="alert alert-warning">
                A conexão com o Instagram ainda não foi configurada pelo administrador da plataforma.
              </div>
            )}
            <ul className="small muted" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
              <li>A conta precisa ser profissional (Empresa ou Criador de conteúdo).</li>
              <li>
                Em Configurações do Instagram → Mensagens, ative “Permitir acesso às mensagens” para ferramentas
                conectadas.
              </li>
              <li>Para automações de comentários, a conta precisa ser pública.</li>
            </ul>
          </div>
        )}
      </div>

      {data?.account && <Diagnostics key={data.account.id + data.status} />}
    </div>
  )
}

/** Página de retorno do OAuth (META_REDIRECT_URI aponta para cá). */
export function InstagramCallbackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const sent = useRef(false) // o código OAuth é de uso único: evita envio duplo (StrictMode)

  useEffect(() => {
    if (sent.current) return
    sent.current = true
    const code = params.get('code')
    const state = params.get('state')
    if (params.get('error')) {
      setError(
        params.get('error_reason') === 'user_denied'
          ? 'Você cancelou a autorização no Instagram.'
          : params.get('error_description') || 'O Instagram recusou a autorização.',
      )
      return
    }
    if (!code || !state) {
      setError('Retorno de autorização incompleto.')
      return
    }
    api
      .post('/api/instagram/callback', { code, state })
      .then(() => navigate('/instagram?connected=1', { replace: true }))
      .catch((err) => setError(errorMessage(err)))
  }, [params, navigate])

  return (
    <div className="page" style={{ maxWidth: 560 }}>
      <div className="card card-body stack">
        {error ? (
          <>
            <h2>Não foi possível conectar</h2>
            <div className="alert alert-error">{error}</div>
            <Link className="btn" to="/instagram">
              Voltar
            </Link>
          </>
        ) : (
          <div className="row">
            <div className="spinner" />
            <span>Finalizando a conexão com o Instagram…</span>
          </div>
        )}
      </div>
    </div>
  )
}
