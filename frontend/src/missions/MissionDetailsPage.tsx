import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getMission, getMissionHistory } from '../api/missions'
import type { Mission, MissionHistory, Page } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { OperationalShell } from '../layout/OperationalShell'

const dateTime = (value: string) => new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))

export function MissionDetailsPage() {
  const { missionId = '' } = useParams()
  const id = /^\d+$/.test(missionId) && Number(missionId) > 0 ? Number(missionId) : null
  const { client } = useAuth()
  const [mission, setMission] = useState<Mission | null>(null)
  const [history, setHistory] = useState<Page<MissionHistory> | null>(null)
  const [historyPage, setHistoryPage] = useState(1)
  const [loading, setLoading] = useState(!!id)
  const [historyLoading, setHistoryLoading] = useState(!!id)
  const [error, setError] = useState(id ? '' : 'Identificador de missão inválido.')
  const [historyError, setHistoryError] = useState('')
  const sequence = useRef(0)

  const loadMission = useCallback(async (signal?: AbortSignal) => {
    if (!id) return
    const current = ++sequence.current; setLoading(true)
    try { const result = await getMission(client, id, signal); if (current === sequence.current && !signal?.aborted) { setMission(result); setError('') } }
    catch (reason) { if (current === sequence.current && !signal?.aborted) setError(reason instanceof ApiError && reason.status === 404 ? 'Missão não encontrada.' : 'Não foi possível carregar a missão.') }
    finally { if (current === sequence.current && !signal?.aborted) setLoading(false) }
  }, [client, id])

  const loadHistory = useCallback(async (signal?: AbortSignal) => {
    if (!id) return
    setHistoryLoading(true)
    try { setHistory(await getMissionHistory(client, id, historyPage, signal)); if (!signal?.aborted) setHistoryError('') }
    catch { if (!signal?.aborted) setHistoryError('Não foi possível carregar o histórico.') }
    finally { if (!signal?.aborted) setHistoryLoading(false) }
  }, [client, historyPage, id])

  useEffect(() => { const controller = new AbortController(); void loadMission(controller.signal); return () => { controller.abort(); sequence.current++ } }, [loadMission])
  useEffect(() => { const controller = new AbortController(); void loadHistory(controller.signal); return () => controller.abort() }, [loadHistory])

  return <OperationalShell section="MISSÕES"><main className="content narrow-content"><div className="back-line"><Link to="/missions">← Voltar para missões</Link></div>
    {loading && <div className="empty-state" role="status">Carregando missão...</div>}
    {error && !loading && <div className="error-banner" role="alert"><span>{error}</span>{id && <button onClick={() => void loadMission()}>Tentar novamente ↻</button>}</div>}
    {mission && !loading && <><div className="page-heading"><div><p className="eyebrow">MISSÃO <span> / </span> #{mission.id}</p><h1>Detalhes da missão<span>.</span></h1><p>{mission.description}</p></div><span className="mission-status detail-status">{mission.status}</span></div>
      <section className="details-grid"><article className="detail-card"><h2>Ocorrência</h2><dl><div><dt>Localização</dt><dd>{mission.location.latitude.toFixed(6)}, {mission.location.longitude.toFixed(6)}</dd></div><div><dt>Criada em</dt><dd>{dateTime(mission.created_at)}</dd></div><div><dt>Atualizada em</dt><dd>{dateTime(mission.updated_at)}</dd></div></dl></article>
        <article className="detail-card"><h2>Unidade atribuída</h2>{mission.assigned_unit ? <dl><div><dt>Identificação</dt><dd>{mission.assigned_unit.name}</dd></div><div><dt>Tipo / placa</dt><dd>{mission.assigned_unit.unit_type} / {mission.assigned_unit.license_plate}</dd></div><div><dt>Status</dt><dd>{mission.assigned_unit.status}</dd></div></dl> : <p className="muted-copy">Nenhuma unidade foi atribuída a esta missão.</p>}</article></section>
      <section className="history-panel"><div className="panel-heading"><div><p className="eyebrow">AUDITORIA</p><h2>Histórico da missão</h2></div></div>
        {historyLoading && <div className="empty-state" role="status">Carregando histórico...</div>}{historyError && !historyLoading && <div className="error-banner" role="alert"><span>{historyError}</span><button onClick={() => void loadHistory()}>Tentar novamente ↻</button></div>}
        {!historyLoading && !historyError && history?.results.length === 0 && <div className="empty-state">Nenhum registro de histórico.</div>}
        {!historyLoading && history?.results.map(item => <div className="history-row" key={item.id}><span className="history-dot" /><div><strong>{item.status}</strong><p>{item.notes || 'Sem observações.'}</p></div><time>{dateTime(item.timestamp)}</time></div>)}
        {!historyLoading && history && history.count > 0 && <div className="pagination"><button disabled={!history.previous || historyPage === 1} onClick={() => setHistoryPage(value => Math.max(1, value - 1))}>← Anterior</button><span>Página {historyPage} de {Math.max(1, Math.ceil(history.count / 20))}</span><button disabled={!history.next} onClick={() => setHistoryPage(value => value + 1)}>Próxima →</button></div>}
      </section></>}
  </main></OperationalShell>
}
