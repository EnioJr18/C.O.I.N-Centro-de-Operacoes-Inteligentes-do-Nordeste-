import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { cancelMission, completeMission, getMission, getMissionHistory } from '../api/missions'
import type { Mission, MissionHistory, Page } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { OperationalShell } from '../layout/OperationalShell'

const dateTime = (value: string) => new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const actorName = (entry: MissionHistory) => {
  if (!entry.actor) return 'Não identificado'
  const name = `${entry.actor.first_name} ${entry.actor.last_name}`.trim()
  return name || entry.actor.username
}
type MissionAction = 'complete' | 'cancel'

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
  const [action, setAction] = useState<MissionAction | null>(null)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [operationError, setOperationError] = useState('')
  const [success, setSuccess] = useState('')
  const sequence = useRef(0)
  const dialog = useRef<HTMLDivElement>(null)
  const confirmButton = useRef<HTMLButtonElement>(null)
  const actionTrigger = useRef<HTMLButtonElement | null>(null)
  const successMessage = useRef<HTMLDivElement>(null)

  const loadMission = useCallback(async (signal?: AbortSignal) => {
    if (!id) return
    const current = ++sequence.current; setLoading(true)
    try { const result = await getMission(client, id, signal); if (current === sequence.current && !signal?.aborted) { setMission(result); setError('') } }
    catch (reason) { if (current === sequence.current && !signal?.aborted) setError(reason instanceof ApiError && reason.status === 404 ? 'Missão não encontrada.' : 'Não foi possível carregar a missão.') }
    finally { if (current === sequence.current && !signal?.aborted) setLoading(false) }
  }, [client, id])

  const loadHistory = useCallback(async (page = historyPage, signal?: AbortSignal) => {
    if (!id) return
    setHistoryLoading(true)
    try { setHistory(await getMissionHistory(client, id, page, signal)); if (!signal?.aborted) setHistoryError('') }
    catch { if (!signal?.aborted) setHistoryError('Não foi possível carregar o histórico.') }
    finally { if (!signal?.aborted) setHistoryLoading(false) }
  }, [client, historyPage, id])

  useEffect(() => { const controller = new AbortController(); void loadMission(controller.signal); return () => { controller.abort(); sequence.current++ } }, [loadMission])
  useEffect(() => { const controller = new AbortController(); void loadHistory(historyPage, controller.signal); return () => controller.abort() }, [historyPage, loadHistory])
  useEffect(() => { if (action) confirmButton.current?.focus() }, [action])

  function openAction(next: MissionAction, trigger: HTMLButtonElement) {
    actionTrigger.current = trigger
    setReason(''); setOperationError(''); setSuccess(''); setAction(next)
  }

  function closeDialog() {
    if (submitting) return
    setAction(null); setReason('')
    requestAnimationFrame(() => actionTrigger.current?.focus())
  }

  function handleDialogKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') { event.preventDefault(); closeDialog(); return }
    if (event.key !== 'Tab' || !dialog.current) return
    const focusable = [...dialog.current.querySelectorAll<HTMLElement>('button:not(:disabled), textarea:not(:disabled)')]
    if (!focusable.length) return
    const first = focusable[0]; const last = focusable[focusable.length - 1]
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
  }

  async function refreshAll() {
    setOperationError(''); setSuccess(''); setHistoryPage(1)
    await Promise.all([loadMission(), loadHistory(1)])
  }

  async function submitAction() {
    if (!id || !action || submitting) return
    setSubmitting(true); setOperationError('')
    try {
      const result = action === 'complete'
        ? await completeMission(client, id)
        : await cancelMission(client, id, reason)
      setMission(result)
      setSuccess(action === 'complete' ? 'Missão concluída com sucesso.' : 'Missão cancelada com sucesso.')
      setAction(null); setReason('')
      if (historyPage === 1) await loadHistory(1)
      else setHistoryPage(1)
      requestAnimationFrame(() => successMessage.current?.focus())
    } catch (failure) {
      setAction(null)
      if (failure instanceof ApiError && failure.status === 409) setOperationError('A missão ou a unidade foi alterada por outra operação. Atualize os dados antes de tentar novamente.')
      else if (failure instanceof ApiError && failure.status === 400) setOperationError('O motivo informado é inválido. Revise o conteúdo e tente novamente.')
      else if (failure instanceof ApiError && failure.status === 403) setOperationError('Seu usuário não possui autorização para esta operação.')
      else setOperationError('Não foi possível confirmar a operação. Os dados exibidos foram preservados.')
      requestAnimationFrame(() => actionTrigger.current?.focus())
    } finally { setSubmitting(false) }
  }

  return <OperationalShell section="MISSÕES"><main id="main-content" className="content narrow-content" tabIndex={-1}><div className="back-line"><Link to="/missions">← Voltar para missões</Link></div>
    {loading && <div className="empty-state" role="status">Carregando missão...</div>}
    {error && !loading && <div className="error-banner" role="alert"><span>{error}</span>{id && <button onClick={() => void loadMission()}>Tentar novamente ↻</button>}</div>}
    {operationError && <div className="error-banner" role="alert"><span>{operationError}</span><button onClick={() => void refreshAll()}>Atualizar dados ↻</button></div>}
    {success && <div ref={successMessage} className="mission-success" role="status" tabIndex={-1}>{success}</div>}
    {mission && !loading && <><div className="page-heading"><div><p className="eyebrow">MISSÃO <span> / </span> #{mission.id}</p><h1>Detalhes da missão<span>.</span></h1><p>{mission.description}</p></div><span className="mission-status detail-status">{mission.status}</span></div>
      {(mission.status === 'Em Andamento' || mission.status === 'Pendente') && <div className="mission-actions" aria-label="Ações da missão">
        {mission.status === 'Em Andamento' && <button className="primary-action" onClick={event => openAction('complete', event.currentTarget)}>Concluir missão</button>}
        <button className="secondary-action mission-cancel-action" onClick={event => openAction('cancel', event.currentTarget)}>Cancelar missão</button>
      </div>}
      <section className="details-grid"><article className="detail-card"><h2>Ocorrência</h2><dl><div><dt>Localização</dt><dd>{mission.location.latitude.toFixed(6)}, {mission.location.longitude.toFixed(6)}</dd></div><div><dt>Criada em</dt><dd>{dateTime(mission.created_at)}</dd></div><div><dt>Atualizada em</dt><dd>{dateTime(mission.updated_at)}</dd></div></dl></article>
        <article className="detail-card"><h2>Unidade atribuída</h2>{mission.assigned_unit ? <dl><div><dt>Identificação</dt><dd>{mission.assigned_unit.name}</dd></div><div><dt>Tipo / placa</dt><dd>{mission.assigned_unit.unit_type} / {mission.assigned_unit.license_plate}</dd></div><div><dt>Status</dt><dd>{mission.assigned_unit.status}</dd></div></dl> : <p className="muted-copy">Nenhuma unidade foi atribuída a esta missão.</p>}</article></section>
      <section className="history-panel"><div className="panel-heading"><div><p className="eyebrow">AUDITORIA</p><h2>Histórico da missão</h2></div></div>
        {historyLoading && <div className="empty-state" role="status">Carregando histórico...</div>}{historyError && !historyLoading && <div className="error-banner" role="alert"><span>{historyError}</span><button onClick={() => void loadHistory()}>Tentar novamente ↻</button></div>}
        {!historyLoading && !historyError && history?.results.length === 0 && <div className="empty-state">Nenhum registro de histórico.</div>}
        {!historyLoading && history?.results.map(item => <div className="history-row" key={item.id}><span className="history-dot" /><div><strong>{item.status}</strong><p>{item.notes || 'Sem observações.'}</p><small>Operador: {actorName(item)}</small></div><time>{dateTime(item.timestamp)}</time></div>)}
        {!historyLoading && history && history.count > 0 && <div className="pagination"><button disabled={!history.previous || historyPage === 1} onClick={() => setHistoryPage(value => Math.max(1, value - 1))}>← Anterior</button><span>Página {historyPage} de {Math.max(1, Math.ceil(history.count / 20))}</span><button disabled={!history.next} onClick={() => setHistoryPage(value => value + 1)}>Próxima →</button></div>}
      </section></>}

    {action && <div className="mission-dialog-layer"><button className="mission-dialog-backdrop" aria-label="Fechar confirmação" onClick={closeDialog} /><div ref={dialog} className="mission-dialog" role="dialog" aria-modal="true" aria-labelledby="mission-dialog-title" onKeyDown={handleDialogKeyDown}>
      <p className="eyebrow">CONFIRMAÇÃO OPERACIONAL</p><h2 id="mission-dialog-title">{action === 'complete' ? 'Concluir missão?' : 'Cancelar missão?'}</h2>
      <p>{action === 'complete' ? 'A missão será encerrada e, se estiver ocupada, a unidade associada voltará a ficar disponível.' : 'A missão será encerrada. Se houver uma unidade ocupada associada, ela será liberada.'}</p>
      {action === 'cancel' && <label>Motivo do cancelamento <span>(opcional)</span><textarea value={reason} maxLength={1000} rows={4} onChange={event => setReason(event.target.value)} /><small>{reason.length}/1000 caracteres</small></label>}
      <div className="form-actions"><button className="secondary-action" type="button" onClick={closeDialog} disabled={submitting}>Voltar</button><button ref={confirmButton} className={`primary-action ${action === 'cancel' ? 'danger-action' : ''}`} type="button" onClick={() => void submitAction()} disabled={submitting}>{submitting ? 'Confirmando...' : action === 'complete' ? 'Confirmar conclusão' : 'Confirmar cancelamento'}</button></div>
    </div></div>}
  </main></OperationalShell>
}
