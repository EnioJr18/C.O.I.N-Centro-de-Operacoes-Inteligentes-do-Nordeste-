import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'
import { loadDashboardSummary } from '../api/dashboard'
import type { DashboardSummary, MissionStatus, UnitStatus } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Icon } from '../layout/Icon'
import { OperationalShell } from '../layout/OperationalShell'
import { FleetSocket } from '../realtime/fleetSocket'
import type { ConnectionState } from '../realtime/fleetSocket'


const fleetLabels: Record<UnitStatus, string> = {
  AVAILABLE: 'Disponíveis',
  BUSY: 'Em atendimento',
  MAINTENANCE: 'Em manutenção',
}
const missionStatuses: MissionStatus[] = ['Pendente', 'Em Andamento', 'Concluída', 'Cancelada']
const dateTime = (value: string) => new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short', timeStyle: 'short',
}).format(new Date(value))
const missionClass = (status: MissionStatus) => status.toLowerCase().replaceAll(' ', '-')
  .normalize('NFD').replace(/[\u0300-\u036f]/g, '')


export function OverviewPage() {
  const { client, logout } = useAuth()
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
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
    if (loaded.current) setRefreshing(true)
    else setLoading(true)
    try {
      const result = await loadDashboardSummary(client, controller.signal)
      if (current !== sequence.current || controller.signal.aborted) return
      setSummary(result)
      setError('')
      loaded.current = true
    } catch (reason) {
      if (current !== sequence.current || controller.signal.aborted) return
      setError(reason instanceof ApiError && reason.status === 403
        ? 'Seu usuário não tem autorização para consultar o resumo operacional.'
        : 'Não foi possível carregar o resumo operacional. Verifique a conexão e tente novamente.')
    } finally {
      if (current === sequence.current && !controller.signal.aborted) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [client])

  useEffect(() => {
    void reload()
    let connectedOnce = false
    const socket = new FleetSocket({
      client,
      onState: setConnection,
      onConnected: () => {
        if (connectedOnce) void reload()
        connectedOnce = true
      },
      onEvent: () => { void reload() },
      onForbidden: logout,
    })
    socket.start()
    return () => {
      socket.stop()
      request.current?.abort()
      sequence.current++
    }
  }, [client, logout, reload])

  const fleet = summary?.fleet
  const missions = summary?.missions
  const percentage = fleet ? Math.max(0, Math.min(100, fleet.availability_percentage)) : 0

  return <OperationalShell section="VISÃO GERAL" connection={connection}>
    <main id="main-content" className="content overview-content" tabIndex={-1}>
      <div className="page-heading dashboard-heading">
        <div><p className="eyebrow">CENTRAL DE OPERAÇÕES</p><h1>Visão geral<span>.</span></h1><p>Indicadores consolidados da frota e das missões operacionais.</p></div>
        <div className="dashboard-actions">
          {summary && <span className="heading-meta"><span className="meta-dot" /> Atualizado em {dateTime(summary.generated_at)}</span>}
          <button className="secondary-action" onClick={() => void reload()} disabled={loading || refreshing}>{refreshing ? 'Atualizando…' : 'Atualizar dados'}</button>
        </div>
      </div>

      {error && <div className="error-banner" role="alert"><span>{error}{summary ? ' Os últimos dados válidos continuam visíveis.' : ''}</span><button onClick={() => void reload()}>Tentar novamente ↻</button></div>}
      {loading && !summary && <div className="dashboard-loading" role="status"><span className="loading-pulse" />Carregando indicadores operacionais...</div>}

      {summary && <>
        <section aria-labelledby="fleet-summary-title">
          <div className="section-heading"><div><p className="eyebrow">FROTA</p><h2 id="fleet-summary-title">Situação operacional</h2></div><span className="section-note">Disponibilidade calculada pelo status informado</span></div>
          <div className="metric-grid">
            <article className="metric-card metric-total"><span className="metric-icon"><Icon name="fleet" /></span><div><span>Frota cadastrada</span><strong>{fleet!.total}</strong><small>Total de unidades</small></div></article>
            <article className="metric-card metric-available"><span className="status-indicator available" /><div><span>Disponíveis</span><strong>{fleet!.available}</strong><small>{fleet!.availability_percentage.toFixed(1)}% da frota por status</small></div></article>
            <article className="metric-card metric-busy"><span className="status-indicator busy" /><div><span>Em atendimento</span><strong>{fleet!.by_status.BUSY}</strong><small>Unidades ocupadas</small></div></article>
            <article className="metric-card metric-maintenance"><span className="status-indicator maintenance" /><div><span>Em manutenção</span><strong>{fleet!.by_status.MAINTENANCE}</strong><small>Unidades indisponíveis</small></div></article>
          </div>
        </section>

        <section className="dashboard-fleet-grid" aria-label="Cobertura e distribuição da frota">
          <article className="overview-panel location-summary"><div className="panel-heading"><div><p className="eyebrow">COBERTURA DE LOCALIZAÇÃO</p><h2>Posições informadas</h2></div></div>
            <div className="location-counts"><div><strong>{fleet!.with_location}</strong><span>Com localização</span></div><div><strong>{fleet!.without_location}</strong><span>Sem localização</span></div></div>
            <p>Localização e disponibilidade são indicadores independentes. Uma unidade disponível pode não possuir posição informada.</p>
            <Link to="/fleet">Explorar mapa da frota →</Link>
          </article>
          <article className="overview-panel status-distribution"><div className="panel-heading"><div><p className="eyebrow">DISTRIBUIÇÃO</p><h2>Frota por situação</h2></div></div>
            {fleet!.total === 0 ? <div className="empty-state"><strong>Nenhuma unidade cadastrada.</strong><span>Os indicadores serão exibidos quando a frota for registrada.</span></div> : <div className="distribution-list">
              {(['AVAILABLE', 'BUSY', 'MAINTENANCE'] as UnitStatus[]).map(status => {
                const value = fleet!.by_status[status]
                const width = fleet!.total ? (value / fleet!.total) * 100 : 0
                return <div className="distribution-row" key={status}><div><span><i className={`status-indicator ${status.toLowerCase()}`} />{fleetLabels[status]}</span><strong>{value}</strong></div><div className="distribution-track" role="img" aria-label={`${fleetLabels[status]}: ${value} de ${fleet!.total}`}><span className={`distribution-fill ${status.toLowerCase()}`} style={{ width: `${width}%` }} /></div></div>
              })}
            </div>}
            <div className="availability-line"><span>Disponibilidade por status</span><strong>{fleet!.availability_percentage.toFixed(1)}%</strong><div className="availability-track"><span style={{ width: `${percentage}%` }} /></div></div>
          </article>
        </section>

        <section className="dashboard-missions" aria-labelledby="mission-summary-title">
          <div className="section-heading"><div><p className="eyebrow">MISSÕES</p><h2 id="mission-summary-title">Resumo histórico</h2></div><Link to="/missions">Consultar todas as missões →</Link></div>
          <div className="mission-metric-grid">
            <article><span>Total histórico</span><strong>{missions!.total}</strong></article>
            {missionStatuses.map(status => <article key={status}><span>{status}</span><strong>{missions!.by_status[status]}</strong></article>)}
          </div>
        </section>

        <section className="overview-panel recent-missions" aria-labelledby="recent-missions-title">
          <div className="panel-heading"><div><p className="eyebrow">ACOMPANHAMENTO</p><h2 id="recent-missions-title">Missões recentes</h2></div><span className="panel-meta">ÚLTIMAS 5 CRIADAS</span></div>
          {missions!.recent.length === 0 ? <div className="empty-state"><strong>Nenhuma missão registrada.</strong><span>As missões mais recentes aparecerão aqui.</span></div> : <div className="recent-mission-list">
            {missions!.recent.map(mission => <Link to={`/missions/${mission.id}`} className="recent-mission-row" key={mission.id}>
              <span className="mission-id">#{mission.id}</span><span className="recent-mission-main"><strong>{mission.description}</strong><small>{dateTime(mission.created_at)}</small></span>
              <span className={`mission-status status-${missionClass(mission.status)}`}>{mission.status}</span><span className="recent-mission-unit">{mission.assigned_unit?.name ?? 'Sem unidade atribuída'}</span><span aria-hidden="true">↗</span>
            </Link>)}
          </div>}
        </section>
      </>}
    </main>
  </OperationalShell>
}
