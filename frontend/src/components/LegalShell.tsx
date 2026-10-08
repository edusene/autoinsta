import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { privacyContactEmail } from '../lib/supabase'

// Moldura das páginas públicas exigidas pela Meta (Política de Privacidade e Termos de Uso).
export const LEGAL_UPDATED_AT = '08/10/2026'

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="stack" style={{ gap: 8 }}>
      <h2>{title}</h2>
      {children}
    </section>
  )
}

/** E-mail público de contato (PRIVACY_CONTACT_EMAIL no .env). */
export function ContactEmail() {
  return privacyContactEmail ? (
    <strong>{privacyContactEmail}</strong>
  ) : (
    <em>o e-mail de contato indicado pelo responsável pela plataforma</em>
  )
}

export function LegalShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="auth-page" style={{ placeItems: 'start center' }}>
      <article className="card" style={{ maxWidth: 820, width: '100%', margin: '24px 0' }}>
        <div className="card-body stack legal" style={{ gap: 22, lineHeight: 1.65, padding: '32px 36px' }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div className="brand" style={{ padding: 0 }}>
              <span className="brand-logo">A</span>
              AutoInsta
            </div>
            <Link to="/login" className="small">Acessar a plataforma</Link>
          </div>
          <div>
            <h1>{title}</h1>
            <p className="muted small" style={{ marginTop: 4 }}>Última atualização: {LEGAL_UPDATED_AT}</p>
          </div>
          {children}
          <nav className="row small" style={{ gap: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <Link to="/privacy">Política de Privacidade</Link>
            <Link to="/terms">Termos de Uso</Link>
          </nav>
        </div>
      </article>
    </div>
  )
}
