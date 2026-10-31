import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import type { ConnectionState } from '../realtime/fleetSocket'

const connectionLabels: Record<ConnectionState, string> = {
  connecting: 'Conectando', connected: 'Conectado', reconnecting: 'Reconectando', disconnected: 'Desconectado',
}

export function OperationalShell({ section, connection, children }: {
  section: 'VISÃO GERAL' | 'MISSÕES'
  connection?: ConnectionState
  children: ReactNode
}) {
  const { user, logout } = useAuth()
  const displayName = user?.first_name || user?.username || 'Operador'
  const linkClass = ({ isActive }: { isActive: boolean }) => `side-link${isActive ? ' side-active' : ''}`
  return <div className="app-shell">
    <aside className="sidebar"><div className="side-brand"><span className="brand-symbol">✳</span><div><strong>C.O.I.N.</strong><small>CENTRO DE OPERAÇÕES</small></div></div>
      <div className="side-label">ÁREA OPERACIONAL</div>
      <nav className="side-nav" aria-label="Navegação operacional">
        <NavLink end to="/" className={linkClass}><span aria-hidden="true">◈</span> Visão geral <span className="active-line" /></NavLink>
        <NavLink to="/missions" className={linkClass}><span aria-hidden="true">◆</span> Missões <span className="active-line" /></NavLink>
      </nav>
      <div className="side-bottom"><div className="side-separator" /><span className="side-label">AMBIENTE OPERACIONAL</span><p>Frota e ocorrências<br />em um só lugar.</p></div>
    </aside>
    <div className="main-column"><header className="topbar"><div className="top-path">OPERAÇÕES <span>/</span> <strong>{section}</strong></div>
      <nav className="mobile-nav" aria-label="Navegação operacional móvel"><NavLink end to="/">Visão geral</NavLink><NavLink to="/missions">Missões</NavLink></nav>
      <div className="top-right">{connection && <><span className={`connection connection-${connection}`} role="status"><i />{connectionLabels[connection]}</span><span className="top-divider" /></>}
        <span className="user-name">{displayName}<small>{user?.role === 'ADMIN' ? 'Administrador' : 'Operador'}</small></span><button className="logout" onClick={logout}>Sair <span aria-hidden="true">↗</span></button>
      </div></header>
      {children}
    </div>
  </div>
}
