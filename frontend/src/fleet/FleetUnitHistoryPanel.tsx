import { useEffect, useRef, useState } from 'react'
import type { ApiClient } from '../api/client'
import { getFleetUnitHistory } from '../api/fleet'
import type { FleetUnitHistory, Page } from '../api/types'

const actions: Record<FleetUnitHistory['action'], string> = {
  UNIT_CREATED: 'Unidade cadastrada',
  UNIT_UPDATED: 'Dados atualizados',
  UNIT_MAINTENANCE_STARTED: 'Entrada em manutenção',
  UNIT_MAINTENANCE_ENDED: 'Saída de manutenção',
}
const fields: Record<string, string> = {
  name: 'nome', license_plate: 'placa', unit_type: 'tipo',
  current_location: 'localização', capabilities: 'capacidades',
}
const dateTime = (value: string) => new Intl.DateTimeFormat('pt-BR', {
  dateStyle: 'short', timeStyle: 'short',
}).format(new Date(value))

export function FleetUnitHistoryPanel({ client, unitId, version }: {
  client: ApiClient; unitId: number; version: number
}) {
  const [page, setPage] = useState(1)
  const [history, setHistory] = useState<Page<FleetUnitHistory> | null>(null)
  const [error, setError] = useState(''); const [loading, setLoading] = useState(true)
  const request = useRef<AbortController | null>(null)
  useEffect(() => { setPage(1) }, [unitId])
  useEffect(() => {
    request.current?.abort(); const controller = new AbortController(); request.current = controller
    setLoading(true); setError('')
    void getFleetUnitHistory(client, unitId, page, controller.signal)
      .then(result => { if (!controller.signal.aborted) setHistory(result) })
      .catch(() => { if (!controller.signal.aborted) setError('Não foi possível carregar o histórico da unidade.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [client, page, unitId, version])

  return <section className="unit-history" aria-labelledby="unit-history-title"><div className="unit-panel-heading"><div><p className="eyebrow">AUDITORIA</p><h3 id="unit-history-title">Histórico da unidade</h3></div><span>{history?.count ?? '—'} registros</span></div>
    {loading && <p className="unit-history-state" role="status">Carregando histórico…</p>}
    {error && <p className="unit-history-state" role="alert">{error}</p>}
    {!loading && !error && history?.results.length === 0 && <p className="unit-history-state">Nenhum evento registrado.</p>}
    {!loading && history?.results.map(entry => <article className="unit-history-row" key={entry.id}><span className="history-dot" /><div><strong>{actions[entry.action]}</strong><p>{entry.previous_status && entry.new_status ? `${entry.previous_status} → ${entry.new_status}` : entry.changed_fields.length ? `Campos: ${entry.changed_fields.map(field => fields[field] ?? field).join(', ')}` : 'Registro administrativo'}</p><small>{[entry.actor.first_name, entry.actor.last_name].filter(Boolean).join(' ') || entry.actor.username} · {dateTime(entry.created_at)}</small></div></article>)}
    {history && (history.previous || history.next) && <div className="pagination"><button disabled={!history.previous || loading} onClick={() => setPage(value => value - 1)}>← Anterior</button><span>Página {page}</span><button disabled={!history.next || loading} onClick={() => setPage(value => value + 1)}>Próxima →</button></div>}
  </section>
}
