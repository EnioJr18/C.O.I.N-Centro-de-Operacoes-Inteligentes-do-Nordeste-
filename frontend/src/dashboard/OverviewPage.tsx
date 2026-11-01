import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { FleetUnit, UnitStatus } from '../api/types'
import { loadFleet, validCoordinates } from '../api/fleet'
import { useAuth } from '../auth/AuthContext'
import { OperationalShell } from '../layout/OperationalShell'
import { Icon } from '../layout/Icon'

const labels: Record<UnitStatus, string> = { AVAILABLE: 'Disponíveis', BUSY: 'Em atendimento', MAINTENANCE: 'Em manutenção' }

export function OverviewPage() {
  const { client } = useAuth()
  const [units, setUnits] = useState<FleetUnit[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    loadFleet(client, controller.signal).then(result => { setUnits(result); setError('') })
      .catch(() => { if (!controller.signal.aborted) setError('Não foi possível carregar o resumo da frota.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [client])

  const metric = (status: UnitStatus) => loading ? '—' : units.filter(unit => unit.status === status).length
  return <OperationalShell section="VISÃO GERAL"><main id="main-content" className="content overview-content" tabIndex={-1}>
    <div className="page-heading"><div><p className="eyebrow">CENTRAL DE OPERAÇÕES</p><h1>Visão geral<span>.</span></h1><p>Um ponto de entrada para acompanhar a operação e acessar os fluxos essenciais.</p></div><span className="heading-meta"><span className="meta-dot" /> DADOS CONSOLIDADOS DA FROTA</span></div>
    {error && <div className="error-banner" role="alert"><span>{error}</span><Link to="/fleet">Consultar frota</Link></div>}
    <section className="metric-grid" aria-label="Resumo operacional da frota">
      <article className="metric-card metric-total"><span className="metric-icon"><Icon name="fleet" /></span><div><span>Frota monitorada</span><strong>{loading ? '—' : units.length}</strong><small>Total carregado de todas as páginas</small></div></article>
      {(['AVAILABLE', 'BUSY', 'MAINTENANCE'] as const).map(status => <article className={`metric-card metric-${status.toLowerCase()}`} key={status}><span className={`status-indicator ${status.toLowerCase()}`} /><div><span>{labels[status]}</span><strong>{metric(status)}</strong><small>Unidades neste estado</small></div></article>)}
    </section>
    <section className="overview-grid">
      <article className="overview-panel"><div className="panel-heading"><div><p className="eyebrow">ACESSOS OPERACIONAIS</p><h2>Continue a operação</h2></div></div><div className="quick-links">
        <Link to="/fleet"><Icon name="fleet" /><span><strong>Abrir frota</strong><small>Mapa, unidades e posições atuais</small></span><Icon name="chevron" /></Link>
        <Link to="/missions"><Icon name="missions" /><span><strong>Consultar missões</strong><small>Filtros, histórico e detalhes</small></span><Icon name="chevron" /></Link>
        <Link to="/missions/dispatch"><Icon name="dispatch" /><span><strong>Despachar emergência</strong><small>Seleção segura da viatura elegível</small></span><Icon name="chevron" /></Link>
      </div></article>
      <article className="overview-panel"><div className="panel-heading"><div><p className="eyebrow">COBERTURA DE LOCALIZAÇÃO</p><h2>Posições informadas</h2></div></div><div className="coverage-content"><strong>{loading ? '—' : units.filter(unit => validCoordinates(unit.current_location)).length}</strong><span>de {loading ? '—' : units.length} unidades com localização válida</span><p>O mapa usa somente a posição atual informada pela API. Eventos de despacho não alteram coordenadas.</p><Link to="/fleet">Explorar mapa da frota →</Link></div></article>
    </section>
  </main></OperationalShell>
}
