import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import type { ConnectionState } from '../realtime/fleetSocket'
import { Icon } from './Icon'
import type { IconName } from './Icon'

export type AppSection = 'VISÃO GERAL' | 'FROTA' | 'MISSÕES' | 'DESPACHO' | 'ALERTAS' | 'USUÁRIOS' | 'PERFIL'

const connectionLabels: Record<ConnectionState, string> = {
  connecting: 'Conectando', connected: 'Conectado', reconnecting: 'Reconectando', disconnected: 'Desconectado',
}

type NavItem = { label: string; to: string; icon: IconName; adminOnly?: boolean; active: (path: string) => boolean }
const operationalItems: NavItem[] = [
  { label: 'Visão geral', to: '/', icon: 'overview', active: path => path === '/' },
  { label: 'Frota', to: '/fleet', icon: 'fleet', active: path => path.startsWith('/fleet') },
  { label: 'Missões', to: '/missions', icon: 'missions', active: path => path.startsWith('/missions') && path !== '/missions/dispatch' },
  { label: 'Despacho', to: '/missions/dispatch', icon: 'dispatch', active: path => path === '/missions/dispatch' },
  { label: 'Alertas', to: '/alerts', icon: 'alerts', active: path => path.startsWith('/alerts') },
]
const administrativeItems: NavItem[] = [
  { label: 'Usuários', to: '/users', icon: 'users', adminOnly: true, active: path => path.startsWith('/users') },
]

function Brand() {
  return <div className="side-brand"><span className="brand-mark" aria-hidden="true">C</span><div><strong>C.O.I.N.</strong><small>CENTRO DE OPERAÇÕES</small></div></div>
}

function Navigation({ path, isAdmin, onNavigate }: { path: string; isAdmin: boolean; onNavigate?: () => void }) {
  const group = (label: string, items: NavItem[]) => <><p className="side-label">{label}</p><nav className="side-nav" aria-label={label === 'OPERAÇÕES' ? 'Operações' : 'Administração'}>{items.filter(item => !item.adminOnly || isAdmin).map(item => {
    const active = item.active(path)
    return <Link key={item.to} to={item.to} onClick={onNavigate} className={`side-link${active ? ' side-active' : ''}`} aria-current={active ? 'page' : undefined}><Icon name={item.icon} /><span>{item.label}</span></Link>
  })}</nav></>
  return <div className="navigation-groups">{group('OPERAÇÕES', operationalItems)}{isAdmin && group('ADMINISTRAÇÃO', administrativeItems)}</div>
}

export function OperationalShell({ section, connection, children }: { section: AppSection; connection?: ConnectionState; children: ReactNode }) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const drawer = useRef<HTMLElement>(null)
  const menuButton = useRef<HTMLButtonElement>(null)
  const account = useRef<HTMLDivElement>(null)
  const accountButton = useRef<HTMLButtonElement>(null)
  const displayName = [user?.first_name, user?.last_name].filter(Boolean).join(' ') || user?.username || 'Operador'
  const initials = displayName.split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase()
  const roleLabel = user?.role === 'ADMIN' ? 'Administrador' : 'Operador'

  function closeDrawer(returnFocus = true) {
    setDrawerOpen(false)
    if (returnFocus) window.setTimeout(() => menuButton.current?.focus(), 0)
  }

  useEffect(() => {
    if (!drawerOpen) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.setTimeout(() => drawer.current?.querySelector<HTMLElement>('a, button')?.focus(), 0)
    return () => { document.body.style.overflow = previous }
  }, [drawerOpen])

  useEffect(() => {
    if (!accountOpen) return
    const close = (event: MouseEvent) => { if (!account.current?.contains(event.target as Node)) setAccountOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [accountOpen])

  function trapDrawerFocus(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') { event.preventDefault(); closeDrawer(); return }
    if (event.key !== 'Tab') return
    const focusable = [...(drawer.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])') || [])]
    if (!focusable.length) return
    const first = focusable[0]; const last = focusable.at(-1)!
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
  }

  function handleLogout() {
    setAccountOpen(false); logout(); navigate('/login', { replace: true })
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Pular para o conteúdo principal</a>
    <aside className="sidebar desktop-sidebar"><Brand /><Navigation path={location.pathname} isAdmin={user?.role === 'ADMIN'} /><div className="side-bottom"><p>Central operacional</p><span>Frota, missões e despacho em um só lugar.</span></div></aside>
    {drawerOpen && <div className="drawer-layer"><button className="drawer-backdrop" aria-label="Fechar menu" onClick={() => closeDrawer()} /><aside ref={drawer} className="sidebar mobile-drawer" role="dialog" aria-modal="true" aria-label="Menu principal" onKeyDown={trapDrawerFocus}><div className="drawer-head"><Brand /><button className="icon-button" onClick={() => closeDrawer()} aria-label="Fechar menu"><Icon name="close" /></button></div><Navigation path={location.pathname} isAdmin={user?.role === 'ADMIN'} onNavigate={() => closeDrawer(false)} /></aside></div>}
    <div className="main-column"><header className="topbar">
      <div className="topbar-title"><button ref={menuButton} className="icon-button menu-button" onClick={() => setDrawerOpen(true)} aria-label="Abrir menu" aria-expanded={drawerOpen}><Icon name="menu" /></button><div><span>Centro de operações</span><strong>{section}</strong></div></div>
      <div className="top-right">{connection && <span className={`connection connection-${connection}`} role="status"><i />{connectionLabels[connection]}</span>}
        <button className="icon-button notification-button" aria-label="Notificações — módulo em preparação" title="Módulo de alertas em preparação" disabled><Icon name="bell" /></button>
        <div className="account" ref={account}><button ref={accountButton} className="account-trigger" onClick={() => setAccountOpen(open => !open)} aria-expanded={accountOpen} aria-haspopup="menu"><span className="avatar" aria-hidden="true">{initials}</span><span className="user-name">{displayName}<small>{roleLabel}</small></span><span className="account-caret" aria-hidden="true">⌄</span></button>
          {accountOpen && <div className="account-menu" role="menu" onKeyDown={event => { if (event.key === 'Escape') { setAccountOpen(false); accountButton.current?.focus() } }}><div className="account-identity"><strong>{displayName}</strong><span>{user?.email || 'E-mail não informado'}</span><small>{roleLabel}</small></div><Link role="menuitem" to="/profile" onClick={() => setAccountOpen(false)}><Icon name="profile" /> Ver perfil</Link><button role="menuitem" onClick={handleLogout}>Sair da sessão <span aria-hidden="true">↗</span></button></div>}
        </div>
      </div></header>{children}
    </div>
  </div>
}
