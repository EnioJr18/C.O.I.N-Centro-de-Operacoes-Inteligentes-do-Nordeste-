import { useCallback, useEffect, useRef, useState } from 'react'
import type { FleetUnit, UnitStatus } from '../api/types'
import { ApiError } from '../api/client'
import { loadFleet, validCoordinates } from '../api/fleet'
import { useAuth } from '../auth/AuthContext'
import { FleetMap } from '../map/FleetMap'
import { FleetSocket } from '../realtime/fleetSocket'
import type { ConnectionState } from '../realtime/fleetSocket'

const labels: Record<UnitStatus, string> = { AVAILABLE: 'Disponível', BUSY: 'Em atendimento', MAINTENANCE: 'Manutenção' }
const connectionLabels: Record<ConnectionState, string> = { connecting: 'Conectando', connected: 'Conectado', reconnecting: 'Reconectando', disconnected: 'Desconectado' }

export function OperationsPage() {
  const { user, client, logout } = useAuth()
  const [units, setUnits] = useState<FleetUnit[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const request = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const loaded = useRef(false)

  const reload = useCallback(async () => {
    request.current?.abort()
    const controller = new AbortController()
    request.current = controller
    const current = ++sequence.current
    if (!loaded.current) setLoading(true)
    try {
      const result = await loadFleet(client, controller.signal)
      if (current !== sequence.current || controller.signal.aborted) return
      setUnits(result); setError(''); loaded.current = true
    } catch (reason) {
      if (current === sequence.current && !controller.signal.aborted) setError(reason instanceof ApiError && reason.status === 403 ? 'Seu usuário não tem autorização para consultar a frota.' : 'Não foi possível carregar a frota. Verifique a conexão e tente novamente.')
    } finally { if (current === sequence.current && !controller.signal.aborted) setLoading(false) }
  }, [client])

  useEffect(() => {
    void reload()
    const socket = new FleetSocket({
      client, onState: setConnection, onConnected: () => { void reload() }, onForbidden: logout,
      onEvent: event => {
        setUnits(previous => previous.map(unit => unit.id === event.unit_id ? { ...unit, status: event.new_status } : unit))
        void reload()
      },
    })
    socket.start()
    return () => { socket.stop(); request.current?.abort(); sequence.current++ }
  }, [client, logout, reload])

  const active = units.find(unit => unit.id === selected)
  const displayName = user?.first_name || user?.username || 'Operador'
  return <div className="app-shell">
    <aside className="sidebar"><div className="side-brand"><span className="brand-symbol">✳</span><div><strong>C.O.I.N.</strong><small>CENTRO DE OPERAÇÕES</small></div></div>
      <div className="side-label">ÁREA OPERACIONAL</div><div className="side-active"><span aria-hidden="true">◈</span> Visão geral <span className="active-line" /></div>
      <div className="side-bottom"><div className="side-separator" /><span className="side-label">AMBIENTE OPERACIONAL</span><p>Frota e ocorrências<br />em um só lugar.</p></div>
    </aside>
    <div className="main-column"><header className="topbar"><div className="top-path">OPERAÇÕES <span>/</span> <strong>VISÃO GERAL</strong></div><div className="top-right"><span className={`connection connection-${connection}`} role="status"><i />{connectionLabels[connection]}</span><span className="top-divider" /><span className="user-name">{displayName}<small>{user?.role === 'ADMIN' ? 'Administrador' : 'Operador'}</small></span><button className="logout" onClick={logout}>Sair <span aria-hidden="true">↗</span></button></div></header>
      <main className="content"><div className="page-heading"><div><p className="eyebrow">CENTRAL DE MONITORAMENTO <span> / </span> FROTA</p><h1>Visão operacional<span>.</span></h1><p>Disponibilidade e localização das unidades em campo.</p></div><div className="heading-meta"><span className="meta-dot" /> MONITORAMENTO EM TEMPO REAL</div></div>
        <section className="summary" aria-label="Resumo da frota"><div className="summary-intro"><span className="summary-icon">◉</span><div><small>FROTA MONITORADA</small><strong>{loaded.current ? units.length.toString().padStart(2, '0') : '—'}</strong></div></div>{(['AVAILABLE', 'BUSY', 'MAINTENANCE'] as const).map(status => <div className="summary-item" key={status}><span className={`status-indicator ${status.toLowerCase()}`} /><div><small>{labels[status].toUpperCase()}</small><strong>{loaded.current ? units.filter(u => u.status === status).length.toString().padStart(2, '0') : '—'}</strong></div></div>)}<span className="summary-note">Dados da frota<br />atualizados pela API</span></section>
        {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => void reload()}>Tentar novamente ↻</button></div>}
        <div className="workspace"><section className="map-panel"><div className="panel-heading"><div><p className="eyebrow">VISUALIZAÇÃO GEOGRÁFICA</p><h2>Mapa da frota</h2></div><span className="panel-meta">◉ {loaded.current ? units.filter(u => validCoordinates(u.current_location)).length : '—'} COM LOCALIZAÇÃO</span></div>
          <FleetMap units={units} selected={selected} onSelect={setSelected} loading={loading} hasError={!!error && !loaded.current} /><div className="panel-foot"><span>POSIÇÃO INFORMADA PELA API</span><span>↗ ARRASTE PARA EXPLORAR</span></div></section>
          <section className="fleet-panel"><div className="panel-heading"><div><p className="eyebrow">UNIDADES EM CAMPO</p><h2>Frota <span className="count-pill">{loaded.current ? units.length : '—'}</span></h2></div><span className="panel-meta">TODAS AS UNIDADES</span></div>
            <div className="fleet-scroll">{loading && <div className="empty-state" role="status">Carregando unidades...</div>}{!loading && !units.length && !error && <div className="empty-state">Nenhuma viatura cadastrada.</div>}{!loading && !units.length && error && <div className="empty-state">A frota não pôde ser carregada.</div>}
              {units.map(unit => <button key={unit.id} onClick={() => setSelected(unit.id)} aria-pressed={selected === unit.id} className={`fleet-row ${selected === unit.id ? 'fleet-row-selected' : ''}`}><span className={`unit-symbol ${unit.status.toLowerCase()}`}>{unit.status === 'AVAILABLE' ? '+' : unit.status === 'BUSY' ? '●' : '×'}</span><span className="unit-info"><strong>{unit.name}</strong><small>{unit.unit_type} <span>·</span> {unit.license_plate}</small></span><span className="unit-status"><span className={`status-indicator ${unit.status.toLowerCase()}`} />{labels[unit.status]}<small>{validCoordinates(unit.current_location) ? 'Localização disponível' : 'Sem localização'}</small></span><span className="row-arrow">↗</span></button>)}
            </div>{active && <div className="selection-detail"><div><span>UNIDADE SELECIONADA</span><button onClick={() => setSelected(null)} aria-label="Fechar detalhes">×</button></div><strong>{active.name}</strong><p>{active.unit_type} · {active.license_plate} · {labels[active.status]}</p><small>{validCoordinates(active.current_location) ? `${active.current_location.latitude.toFixed(4)}, ${active.current_location.longitude.toFixed(4)}` : 'Localização indisponível'}</small></div>}
          </section></div><footer className="app-footer"><span>C.O.I.N. <b> / </b> CENTRO DE OPERAÇÕES INTELIGENTES</span><span>VISÃO OPERACIONAL DA FROTA</span></footer>
      </main>
    </div>
  </div>
}
