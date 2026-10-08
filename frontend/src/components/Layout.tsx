import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: '◧' },
  { to: '/workflows', label: 'Workflows', icon: '⇄' },
  { to: '/instagram', label: 'Instagram', icon: '◎' },
  { to: '/contacts', label: 'Contatos', icon: '☺' },
  { to: '/logs', label: 'Logs', icon: '≡' },
  { to: '/settings', label: 'Configurações', icon: '⚙' },
]

export function Layout() {
  const { session, signOut } = useAuth()
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
