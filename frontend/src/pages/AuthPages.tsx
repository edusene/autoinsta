import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { supabase, supabaseConfigured } from '../lib/supabase'

const AUTH_ERRORS: Record<string, string> = {
  'Invalid login credentials': 'E-mail ou senha incorretos.',
  'Email not confirmed': 'Confirme seu e-mail antes de entrar (verifique sua caixa de entrada).',
  'User already registered': 'Já existe uma conta com este e-mail.',
}

function translate(message: string): string {
  return AUTH_ERRORS[message] ?? message
}

function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="auth-page">
      <div className="card auth-card">
        <div className="card-body">
          <div className="brand" style={{ padding: 0 }}>
            <span className="brand-logo">A</span>
            AutoInsta
          </div>
          <div>
            <h1>{title}</h1>
            <p className="muted" style={{ marginTop: 4 }}>
              {subtitle}
            </p>
          </div>
          {!supabaseConfigured && (
            <div className="alert alert-warning">
              Supabase não configurado: defina VITE_SUPABASE_URL e VITE_SUPABASE_ANON_KEY no arquivo .env do frontend.
            </div>
          )}
          {children}
        </div>
      </div>
    </div>
  )
}

export function LoginPage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (session) return <Navigate to="/dashboard" replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const { error: err } = await supabase.auth.signInWithPassword({ email, password })
    setBusy(false)
    if (err) return setError(translate(err.message))
    navigate('/dashboard')
  }

  return (
    <AuthShell title="Entrar" subtitle="Acesse seu painel de automações.">
      <form className="stack" onSubmit={submit}>
        {error && <div className="alert alert-error">{error}</div>}
        <div className="field">
          <label htmlFor="email">E-mail</label>
          <input id="email" className="input" type="email" autoComplete="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Senha</label>
          <input id="password" className="input" type="password" autoComplete="current-password" required
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <button className="btn btn-primary btn-lg" disabled={busy}>
          {busy ? 'Entrando…' : 'Entrar'}
        </button>
        <p className="muted small" style={{ textAlign: 'center' }}>
          Não tem conta? <Link to="/register">Criar conta</Link>
        </p>
      </form>
    </AuthShell>
  )
}

export function RegisterPage() {
  const { session } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  if (session) return <Navigate to="/dashboard" replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (password.length < 8) return setError('A senha deve ter pelo menos 8 caracteres.')
    if (password !== confirm) return setError('As senhas não conferem.')
    setBusy(true)
    const { data, error: err } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: `${window.location.origin}/login` },
    })
    setBusy(false)
    if (err) return setError(translate(err.message))
    if (data.session) navigate('/dashboard')
    else setDone(true) // confirmação de e-mail habilitada no Supabase
  }

  if (done) {
    return (
      <AuthShell title="Verifique seu e-mail" subtitle="Enviamos um link de confirmação.">
        <div className="alert alert-success">
          Abra o link enviado para <strong>{email}</strong> e depois faça login.
        </div>
        <Link className="btn" to="/login">
          Ir para o login
        </Link>
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Criar conta" subtitle="Comece a automatizar seu Instagram.">
      <form className="stack" onSubmit={submit}>
        {error && <div className="alert alert-error">{error}</div>}
        <div className="field">
          <label htmlFor="email">E-mail</label>
          <input id="email" className="input" type="email" autoComplete="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Senha</label>
          <input id="password" className="input" type="password" autoComplete="new-password" required
            value={password} onChange={(e) => setPassword(e.target.value)} />
          <span className="help">Mínimo de 8 caracteres.</span>
        </div>
        <div className="field">
          <label htmlFor="confirm">Confirmar senha</label>
          <input id="confirm" className="input" type="password" autoComplete="new-password" required
            value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        </div>
        <button className="btn btn-primary btn-lg" disabled={busy}>
          {busy ? 'Criando…' : 'Criar conta'}
        </button>
        <p className="muted small" style={{ textAlign: 'center' }}>
          Já tem conta? <Link to="/login">Entrar</Link>
        </p>
      </form>
    </AuthShell>
  )
}
