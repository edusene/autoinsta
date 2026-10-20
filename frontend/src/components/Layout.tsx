import { NavLink, Outlet } from 'react-router-dom'
import { useApi } from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: '◧' },
  { to: '/inbox', label: 'Caixa de entrada', icon: '✉', badge: true },
  { to: '/workflows', label: 'Workflows', icon: '⇄' },
  { to: '/broadcasts', label: 'Disparos', icon: '➤' },
  { to: '/contacts', label: 'Contatos', icon: '☺' },
  { to: '/instagram', label: 'Instagram', icon: '◎' },
  { to: '/logs', label: 'Logs', icon: '≡' },
  { to: '/settings', label: 'Configurações', icon: '⚙' },
]

export function Layout() {
  const { session, signOut } = useAuth()
  const { data: unread } = useApi<{ unread_conversations: number }>('/api/inbox/unread-count', { refreshMs: 15_000 })
  const unreadCount = unread?.unread_conversations ?? 0
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-logo">A</span>
          AutoInsta
        </div>
        <nav className="nav">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to}>
              <span className="nav-icon" aria-hidden>
                {item.icon}
              </span>
              {item.label}
              {item.badge && unreadCount > 0 && (
                <span className="nav-badge" aria-label={`${unreadCount} conversa(s) não lida(s)`}>
                  {unreadCount > 99 ? '99+' : unreadCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="email" title={session?.user.email}>
            {session?.user.email}
          </div>
          <button className="btn btn-sm btn-ghost" style={{ padding: 0 }} onClick={signOut}>
            Sair
          </button>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
