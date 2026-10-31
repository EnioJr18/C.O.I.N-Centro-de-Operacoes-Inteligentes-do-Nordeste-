import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'
import { listMissions, localDateTimeToIso } from '../api/missions'
import type { MissionFilters } from '../api/missions'
import type { Mission, MissionStatus, Page } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { OperationalShell } from '../layout/OperationalShell'

const statuses: MissionStatus[] = ['Pendente', 'Em Andamento', 'Concluída', 'Cancelada']
const dateTime = (value: string) => new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value))

export function MissionsPage() {
  const { client } = useAuth()
  const [status, setStatus] = useState<MissionStatus | ''>('')
  const [createdAfter, setCreatedAfter] = useState('')
  const [createdBefore, setCreatedBefore] = useState('')
  const [filters, setFilters] = useState<MissionFilters>({})
  const [page, setPage] = useState(1)
  const [data, setData] = useState<Page<Mission> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filterError, setFilterError] = useState('')
  const sequence = useRef(0)

  const load = useCallback(async (signal?: AbortSignal) => {
    const current = ++sequence.current
    setLoading(true)
    try {
      const result = await listMissions(client, { ...filters, page }, signal)
      if (current !== sequence.current || signal?.aborted) return
      setData(result); setError('')
    } catch (reason) {
      if (current !== sequence.current || signal?.aborted) return
      setError(reason instanceof ApiError && reason.status === 403
        ? 'Seu usuário não tem autorização para consultar missões.'
        : 'Não foi possível carregar as missões. Verifique a conexão e tente novamente.')
    } finally { if (current === sequence.current && !signal?.aborted) setLoading(false) }
  }, [client, filters, page])

  useEffect(() => { const controller = new AbortController(); void load(controller.signal); return () => { controller.abort(); sequence.current++ } }, [load])

  function applyFilters(event: FormEvent) {
    event.preventDefault()
    const after = localDateTimeToIso(createdAfter)
    const before = localDateTimeToIso(createdBefore)
    if ((createdAfter && !after) || (createdBefore && !before)) { setFilterError('Informe datas válidas.'); return }
    if (after && before && new Date(after) > new Date(before)) { setFilterError('A data inicial deve ser anterior à data final.'); return }
    setFilterError(''); setPage(1); setFilters({ status: status || undefined, createdAfter: after, createdBefore: before })
  }

  return <OperationalShell section="MISSÕES"><main className="content">
    <div className="page-heading"><div><p className="eyebrow">CENTRAL DE MONITORAMENTO <span> / </span> MISSÕES</p><h1>Missões operacionais<span>.</span></h1><p>Consulte ocorrências, histórico e operações de despacho.</p></div><div className="page-actions"><Link className="secondary-action" to="/missions/new">Nova missão</Link><Link className="primary-action" to="/missions/dispatch">Despachar emergência</Link></div></div>
    <form className="mission-filters" onSubmit={applyFilters}><label>Status<select value={status} onChange={event => setStatus(event.target.value as MissionStatus | '')}><option value="">Todos</option>{statuses.map(item => <option key={item}>{item}</option>)}</select></label>
      <label>Criadas a partir de<input type="datetime-local" value={createdAfter} onChange={event => setCreatedAfter(event.target.value)} /></label>
      <label>Criadas até<input type="datetime-local" value={createdBefore} onChange={event => setCreatedBefore(event.target.value)} /></label>
      <button className="filter-button" type="submit">Aplicar filtros</button>{filterError && <p className="filter-error" role="alert">{filterError}</p>}
    </form>
    {error && <div className="error-banner" role="alert"><span>{error}</span><button onClick={() => void load()}>Tentar novamente ↻</button></div>}
    <section className="mission-panel" aria-label="Lista de missões">
      {loading && <div className="empty-state" role="status">Carregando missões...</div>}
      {!loading && !error && data?.results.length === 0 && <div className="empty-state"><strong>Nenhuma missão encontrada.</strong><span>Ajuste os filtros ou registre uma nova missão.</span></div>}
      {!loading && data?.results.map(mission => <Link className="mission-row" to={`/missions/${mission.id}`} key={mission.id}>
        <span className="mission-id">#{mission.id}</span><span className="mission-main"><strong>{mission.description}</strong><small>{dateTime(mission.created_at)}</small></span>
        <span className={`mission-status status-${mission.status.toLowerCase().replaceAll(' ', '-').normalize('NFD').replace(/[\u0300-\u036f]/g, '')}`}>{mission.status}</span>
        <span className="mission-unit">{mission.assigned_unit ? mission.assigned_unit.name : 'Sem unidade atribuída'}</span><span aria-hidden="true">↗</span>
      </Link>)}
      {!loading && data && data.count > 0 && <div className="pagination"><button disabled={!data.previous || page === 1} onClick={() => setPage(value => Math.max(1, value - 1))}>← Anterior</button><span>Página {page} de {Math.max(1, Math.ceil(data.count / 20))}</span><button disabled={!data.next} onClick={() => setPage(value => value + 1)}>Próxima →</button></div>}
    </section><footer className="app-footer"><span>C.O.I.N. <b> / </b> CENTRO DE OPERAÇÕES INTELIGENTES</span><span>GESTÃO DE MISSÕES</span></footer>
  </main></OperationalShell>
}
