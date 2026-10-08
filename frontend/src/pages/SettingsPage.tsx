import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorAlert, Loading } from '../components/ui'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import { api, API_URL, errorMessage } from '../lib/api'
import { metaRedirectUri } from '../lib/supabase'
import { setTheme, useTheme, type Theme } from '../lib/theme'
import type { Settings } from '../types'

const THEME_OPTIONS: [Theme, string][] = [
  ['light', '☀ Claro'],
  ['dark', '☾ Escuro'],
]

export function SettingsPage() {
  const { session, signOut } = useAuth()
  const theme = useTheme()
  const { data, error, loading, reload, setData } = useApi<Settings>('/api/settings')
  const [model, setModel] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (data) setModel(data.ai.default_model ?? '')
  }, [data])

  const save = async () => {
    setSaving(true)
    setSaveMsg(null)
    setSaveError(null)
    try {
      setData(await api.put<Settings>('/api/settings', { ai_default_model: model.trim() || null }))
      setSaveMsg('Salvo.')
    } catch (err) {
      setSaveError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const apiBase = API_URL || window.location.origin

  if (loading && !data) return <Loading />
  return (
    <div className="page stack" style={{ maxWidth: 860 }}>
      <div className="page-header">
        <div>
          <h1>Configurações</h1>
        </div>
      </div>
      <ErrorAlert message={error} onRetry={reload} />

      <div className="card">
        <div className="card-header"><h2>Conta</h2></div>
        <div className="card-body row">
          <div>
            <div style={{ fontWeight: 550 }}>{session?.user.email}</div>
            <div className="small muted">Login gerenciado pelo Supabase Auth.</div>
          </div>
          <span className="spacer" />
          <button className="btn" onClick={signOut}>Sair</button>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h2>Aparência</h2></div>
        <div className="card-body row">
          <div>
            <div style={{ fontWeight: 550 }}>Tema</div>
            <div className="small muted">Salvo neste navegador.</div>
          </div>
          <span className="spacer" />
          <div className="segmented" role="radiogroup" aria-label="Tema">
            {THEME_OPTIONS.map(([value, label]) => (
              <button key={value} role="radio" aria-checked={theme === value}
                className={theme === value ? 'active' : ''} onClick={() => setTheme(value)}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {data && (
        <>
          <div className="card">
            <div className="card-header"><h2>Instagram</h2><Link to="/instagram" className="small">Gerenciar</Link></div>
            <div className="card-body row">
              {data.instagram.connected ? (
                <>
                  <span className="badge badge-success">Conectado</span>
                  <span>@{data.instagram.account?.username}</span>
                </>
              ) : (
                <>
                  <span className="badge badge-warning">{data.instagram.status === 'token_expired' ? 'Expirado' : 'Não conectado'}</span>
                  <Link className="btn btn-sm" to="/instagram">{data.instagram.status === 'token_expired' ? 'Reconectar' : 'Conectar'}</Link>
                </>
              )}
            </div>
          </div>

          <div className="card">
            <div className="card-header"><h2>IA (OpenAI)</h2></div>
            <div className="card-body stack">
              <div className="row">
                {data.ai.openai_configured ? (
                  <><span className="badge badge-success">Configurada</span><span className="small muted">Chave do servidor {data.ai.key_hint}</span></>
                ) : (
                  <><span className="badge badge-danger">Não configurada</span><span className="small muted">O administrador precisa definir OPENAI_API_KEY no servidor.</span></>
                )}
              </div>
              <div className="field" style={{ maxWidth: 380 }}>
                <label htmlFor="model">Modelo padrão</label>
                <input id="model" className="input" value={model} maxLength={80}
                  placeholder={data.ai.platform_default_model} onChange={(e) => setModel(e.target.value)} />
                <span className="help">Vazio = padrão da plataforma ({data.ai.platform_default_model}). Cada nó de IA pode sobrescrever.</span>
              </div>
              <div className="row">
                <button className="btn btn-primary" onClick={save} disabled={saving}>{saving ? 'Salvando…' : 'Salvar'}</button>
                {saveMsg && <span className="small" style={{ color: 'var(--success)' }}>{saveMsg}</span>}
              </div>
              <ErrorAlert message={saveError} />
            </div>
          </div>
        </>
      )}

      <div className="card">
        <div className="card-header"><h2>Documentos legais</h2></div>
        <div className="card-body stack small">
          {[
            ['Política de Privacidade', '/privacy'],
            ['Termos de Uso', '/terms'],
          ].map(([label, path]) => (
            <div key={path} className="row" style={{ justifyContent: 'space-between' }}>
              <a href={path} target="_blank" rel="noopener noreferrer" style={{ fontWeight: 550 }}>
                {label} ↗
              </a>
              <code>{window.location.origin}{path}</code>
            </div>
          ))}
          <div className="muted">Use esses endereços no painel da Meta (Configurações do app → Básico).</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header"><h2>Sistema</h2></div>
        <div className="card-body stack small">
          <div><span className="muted">API:</span> <code>{apiBase}</code></div>
          <div><span className="muted">URL de callback do webhook (painel da Meta):</span> <code>{apiBase}/webhooks/meta</code></div>
          <div><span className="muted">URL de redirecionamento OAuth (cadastre na Meta):</span> <code>{window.location.origin}/instagram/callback</code></div>
          <div>
            <span className="muted">META_REDIRECT_URI no servidor:</span> <code>{metaRedirectUri || '(vazio)'}</code>{' '}
            {metaRedirectUri === `${window.location.origin}/instagram/callback`
              ? <span style={{ color: 'var(--success)' }}>✓ confere</span>
              : <span style={{ color: 'var(--danger)' }}>✕ diferente — corrija no servidor</span>}
          </div>
          <div className="muted">Essas URLs são configuradas uma única vez pelo administrador no Meta App (veja o README).</div>
        </div>
      </div>
    </div>
  )
}

export function DataDeletionPage() {
  const code = new URLSearchParams(window.location.search).get('code')
  return (
    <div className="auth-page">
      <div className="card auth-card">
        <div className="card-body">
          <h1>Exclusão de dados</h1>
          <p className="muted">
            Sua solicitação de exclusão de dados do Instagram foi processada: a conta conectada, tokens e contatos associados foram removidos.
          </p>
          {code && <p>Código de confirmação: <code>{code}</code></p>}
        </div>
      </div>
    </div>
  )
}
