import { useCallback, useEffect, useRef, useState } from 'react'
import type { FleetUnit, UnitStatus } from '../api/types'
import { ApiError } from '../api/client'
import { loadFleet, validCoordinates } from '../api/fleet'
import { useAuth } from '../auth/AuthContext'
import { FleetMap } from '../map/FleetMap'
import { FleetSocket } from '../realtime/fleetSocket'
import type { ConnectionState } from '../realtime/fleetSocket'
import { OperationalShell } from '../layout/OperationalShell'
import { FleetUnitFormDialog, MaintenanceDialog } from './FleetUnitDialogs'
import { FleetUnitHistoryPanel } from './FleetUnitHistoryPanel'

const labels: Record<UnitStatus, string> = { AVAILABLE: 'Disponível', BUSY: 'Em atendimento', MAINTENANCE: 'Manutenção' }

export function OperationsPage() {
  const { client, logout, user } = useAuth()
  const [units, setUnits] = useState<FleetUnit[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const request = useRef<AbortController | null>(null)
  const sequence = useRef(0)
  const loaded = useRef(false)
  const [formMode, setFormMode] = useState<'create' | 'edit' | null>(null)
  const [maintenanceOpen, setMaintenanceOpen] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [historyVersion, setHistoryVersion] = useState(0)
  const selectedRef = useRef<number | null>(null)

  const selectUnit = useCallback((unitId: number | null) => {
    selectedRef.current = unitId
    setSelected(unitId)
  }, [])

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
        if (event.action === 'DISPATCH') {
          setUnits(previous => previous.map(unit => unit.id === event.unit_id ? { ...unit, status: event.new_status } : unit))
        }
        if (
          (event.action === 'UNIT_MAINTENANCE_STARTED'
            || event.action === 'UNIT_MAINTENANCE_ENDED')
          && event.unit_id === selectedRef.current
        ) setHistoryVersion(value => value + 1)
        void reload()
      },
    })
    socket.start()
    return () => { socket.stop(); request.current?.abort(); sequence.current++ }
  }, [client, logout, reload])

  const active = units.find(unit => unit.id === selected)
  useEffect(() => {
    if (loaded.current && selected !== null && !active) selectUnit(null)
  }, [active, selected, selectUnit])

  const reconcile = useCallback((unit: FleetUnit, message: string) => {
    setUnits(previous => previous.some(item => item.id === unit.id)
      ? previous.map(item => item.id === unit.id ? unit : item)
      : [...previous, unit])
    selectUnit(unit.id); setFeedback(message); setHistoryVersion(value => value + 1)
    setFormMode(null); setMaintenanceOpen(false); void reload()
  }, [reload, selectUnit])

  const capabilities = active ? Object.entries(active.capabilities) : []
  return <OperationalShell section="FROTA" connection={connection}>
    <main id="main-content" className="content" tabIndex={-1}><div className="page-heading"><div><p className="eyebrow">CENTRAL DE MONITORAMENTO <span> / </span> FROTA</p><h1>Frota operacional<span>.</span></h1><p>Disponibilidade e localização das unidades em campo.</p></div><div className="fleet-heading-actions"><div className="heading-meta"><span className="meta-dot" /> MONITORAMENTO EM TEMPO REAL</div>{user?.role === 'ADMIN' && <button className="primary-action" onClick={() => setFormMode('create')}>Nova unidade</button>}</div></div>
        {feedback && <div className="mission-success" role="status" tabIndex={-1}>{feedback}</div>}
        <section className="summary" aria-label="Resumo da frota"><div className="summary-intro"><span className="summary-icon">◉</span><div><small>FROTA MONITORADA</small><strong>{loaded.current ? units.length.toString().padStart(2, '0') : '—'}</strong></div></div>{(['AVAILABLE', 'BUSY', 'MAINTENANCE'] as const).map(status => <div className="summary-item" key={status}><span className={`status-indicator ${status.toLowerCase()}`} /><div><small>{labels[status].toUpperCase()}</small><strong>{loaded.current ? units.filter(u => u.status === status).length.toString().padStart(2, '0') : '—'}</strong></div></div>)}<span className="summary-note">Dados da frota<br />atualizados pela API</span></section>
        {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => void reload()}>Tentar novamente ↻</button></div>}
        <div className="workspace"><section className="map-panel"><div className="panel-heading"><div><p className="eyebrow">VISUALIZAÇÃO GEOGRÁFICA</p><h2>Mapa da frota</h2></div><span className="panel-meta">◉ {loaded.current ? units.filter(u => validCoordinates(u.current_location)).length : '—'} COM LOCALIZAÇÃO</span></div>
          <FleetMap units={units} selected={selected} onSelect={selectUnit} loading={loading} hasError={!!error && !loaded.current} /><div className="panel-foot"><span>POSIÇÃO INFORMADA PELA API</span><span>↗ ARRASTE PARA EXPLORAR</span></div></section>
          <section className="fleet-panel"><div className="panel-heading"><div><p className="eyebrow">UNIDADES EM CAMPO</p><h2>Frota <span className="count-pill">{loaded.current ? units.length : '—'}</span></h2></div><span className="panel-meta">TODAS AS UNIDADES</span></div>
            <div className="fleet-scroll">{loading && <div className="empty-state" role="status">Carregando unidades...</div>}{!loading && !units.length && !error && <div className="empty-state">Nenhuma viatura cadastrada.</div>}{!loading && !units.length && error && <div className="empty-state">A frota não pôde ser carregada.</div>}
              {units.map(unit => <button key={unit.id} onClick={() => selectUnit(unit.id)} aria-pressed={selected === unit.id} className={`fleet-row ${selected === unit.id ? 'fleet-row-selected' : ''}`}><span className={`unit-symbol ${unit.status.toLowerCase()}`}>{unit.status === 'AVAILABLE' ? '+' : unit.status === 'BUSY' ? '●' : '×'}</span><span className="unit-info"><strong>{unit.name}</strong><small>{unit.unit_type} <span>·</span> {unit.license_plate}</small></span><span className="unit-status"><span className={`status-indicator ${unit.status.toLowerCase()}`} />{labels[unit.status]}<small>{validCoordinates(unit.current_location) ? 'Localização disponível' : 'Sem localização'}</small></span><span className="row-arrow">↗</span></button>)}
            </div>{active && <aside className="selection-detail" aria-label={`Detalhes de ${active.name}`}><div className="selection-title"><span>UNIDADE SELECIONADA</span><button onClick={() => selectUnit(null)} aria-label="Fechar detalhes">×</button></div><strong>{active.name}</strong><dl className="unit-detail-grid"><div><dt>Placa</dt><dd>{active.license_plate}</dd></div><div><dt>Tipo</dt><dd>{active.unit_type}</dd></div><div><dt>Status</dt><dd>{labels[active.status]}</dd></div><div><dt>Localização</dt><dd>{validCoordinates(active.current_location) ? `${active.current_location.latitude.toFixed(4)}, ${active.current_location.longitude.toFixed(4)}` : 'Localização indisponível'}</dd></div></dl>
              <div className="unit-capabilities"><span>CAPACIDADES</span>{capabilities.length ? <ul>{capabilities.map(([key, value]) => <li key={key}><b>{key}</b><small>{typeof value === 'string' ? value : JSON.stringify(value)}</small></li>)}</ul> : <p>Nenhuma capacidade informada.</p>}</div>
              {user?.role === 'ADMIN' && <><div className="unit-admin-actions"><button className="secondary-action" onClick={() => setFormMode('edit')}>Editar dados</button>{active.status !== 'BUSY' && <button className={active.status === 'MAINTENANCE' ? 'primary-action' : 'secondary-action maintenance-action'} onClick={() => setMaintenanceOpen(true)}>{active.status === 'MAINTENANCE' ? 'Retirar da manutenção' : 'Colocar em manutenção'}</button>}</div><FleetUnitHistoryPanel client={client} unitId={active.id} version={historyVersion} /></>}
            </aside>}
          </section></div><footer className="app-footer"><span>C.O.I.N. <b> / </b> CENTRO DE OPERAÇÕES INTELIGENTES</span><span>VISÃO OPERACIONAL DA FROTA</span></footer>
      <FleetUnitFormDialog client={client} unit={formMode === 'edit' ? active ?? null : null} open={formMode !== null} onClose={() => setFormMode(null)} onRefreshed={unit => { setUnits(previous => previous.map(item => item.id === unit.id ? unit : item)); selectUnit(unit.id) }} onSaved={(unit, created) => reconcile(unit, created ? 'Unidade cadastrada com sucesso.' : 'Dados da unidade atualizados.')} />
      {active && <MaintenanceDialog client={client} unit={active} open={maintenanceOpen} onClose={() => setMaintenanceOpen(false)} onRefresh={() => { setMaintenanceOpen(false); void reload() }} onSaved={unit => reconcile(unit, unit.status === 'MAINTENANCE' ? 'Unidade colocada em manutenção.' : 'Unidade disponível para operações.')} />}
    </main>
  </OperationalShell>
}
