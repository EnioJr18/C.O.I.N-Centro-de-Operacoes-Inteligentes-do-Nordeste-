import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import { createFleetUnit, endMaintenance, getFleetUnit, startMaintenance, updateFleetUnit } from '../api/fleet'
import type { ApiClient } from '../api/client'
import type { FleetUnit, FleetUnitPayload, UnitType } from '../api/types'
import { LocationPicker } from '../map/LocationPicker'

type CapabilityRow = { id: number; key: string; value: string }
let capabilityId = 0

function focusable(container: HTMLElement | null) {
  if (!container) return []
  const selector = 'button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [href]'
  return [...container.querySelectorAll<HTMLElement>('*')]
    .filter(element => element.matches(selector))
}

function useDialog(open: boolean, close: () => void, initial: React.RefObject<HTMLElement | null>) {
  const dialog = useRef<HTMLDivElement>(null)
  const previous = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (!open) return
    previous.current = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    queueMicrotask(() => initial.current?.focus())
    return () => { document.body.style.overflow = overflow; previous.current?.focus() }
  }, [open, initial])
  function onKeyDown(event: KeyboardEvent) {
    if (event.key === 'Escape') { event.preventDefault(); close(); return }
    if (event.key !== 'Tab') return
    const items = focusable(dialog.current)
    if (!items.length) {
      event.preventDefault()
      dialog.current?.focus()
      return
    }
    const first = items[0]; const last = items.at(-1)!
    const moveFocus = (target: HTMLElement) => {
      event.preventDefault(); target.focus()
    }
    if (!items.includes(document.activeElement as HTMLElement)) {
      moveFocus(event.shiftKey ? last : first)
    }
    else if (event.shiftKey && document.activeElement === first) moveFocus(last)
    else if (!event.shiftKey && document.activeElement === last) moveFocus(first)
  }
  return { dialog, onKeyDown }
}

function messageFrom(error: ApiError) {
  const find = (value: unknown): string | null => {
    if (typeof value === 'string' && value.trim()) return value.slice(0, 400)
    if (Array.isArray(value)) for (const item of value) { const found = find(item); if (found) return found }
    if (value && typeof value === 'object') for (const item of Object.values(value)) { const found = find(item); if (found) return found }
    return null
  }
  return find(error.details)
}

function rowsFrom(capabilities: Record<string, unknown>): CapabilityRow[] {
  return Object.entries(capabilities).map(([key, value]) => ({
    id: ++capabilityId,
    key,
    value: typeof value === 'string' ? value : JSON.stringify(value),
  }))
}

function parseCapabilities(rows: CapabilityRow[]) {
  const result: Record<string, unknown> = {}
  for (const row of rows) {
    const key = row.key.trim()
    if (!key) throw new Error('Informe o nome de cada capacidade.')
    if (key.length > 64) throw new Error('Cada capacidade pode ter no máximo 64 caracteres.')
    if (Object.hasOwn(result, key)) throw new Error(`A capacidade “${key}” está repetida.`)
    const raw = row.value.trim()
    if (!raw) result[key] = ''
    else {
      try { result[key] = JSON.parse(raw) as unknown }
      catch { result[key] = raw }
    }
  }
  let properties = 0
  const validate = (value: unknown, depth: number) => {
    if (depth > 5) throw new Error('Capacidades permitem no máximo cinco níveis.')
    if (Array.isArray(value)) { value.forEach(item => validate(item, depth + 1)); return }
    if (!value || typeof value !== 'object') return
    const entries = Object.entries(value)
    properties += entries.length
    if (properties > 100) throw new Error('Capacidades permitem no máximo 100 propriedades.')
    for (const [key, item] of entries) {
      if (key.length > 64) throw new Error('Cada capacidade pode ter no máximo 64 caracteres.')
      validate(item, depth + 1)
    }
  }
  validate(result, 1)
  if (new TextEncoder().encode(JSON.stringify(result)).length > 16 * 1024) throw new Error('Capacidades excedem o limite de 16 KiB.')
  return result
}

export function FleetUnitFormDialog({ client, unit, open, onClose, onSaved, onRefreshed }: {
  client: ApiClient; unit: FleetUnit | null; open: boolean; onClose: () => void
  onSaved: (unit: FleetUnit, created: boolean) => void
  onRefreshed?: (unit: FleetUnit) => void
}) {
  const title = useRef<HTMLHeadingElement>(null)
  const { dialog, onKeyDown } = useDialog(open, onClose, title)
  const [name, setName] = useState(''); const [plate, setPlate] = useState('')
  const [unitType, setUnitType] = useState<UnitType>('USB')
  const [latitude, setLatitude] = useState(''); const [longitude, setLongitude] = useState('')
  const [capabilities, setCapabilities] = useState<CapabilityRow[]>([])
  const [error, setError] = useState(''); const [notice, setNotice] = useState('')
  const [conflict, setConflict] = useState(false); const [submitting, setSubmitting] = useState(false)
  const sending = useRef(false)
  const reconciling = useRef(false)
  const requestGeneration = useRef(0)
  const currentUnitId = useRef(unit?.id ?? null)
  currentUnitId.current = unit?.id ?? null
  const restricted = !!unit && unit.status !== 'AVAILABLE'

  function populate(current: FleetUnit | null) {
    setName(current?.name ?? ''); setPlate(current?.license_plate ?? '')
    setUnitType(current?.unit_type ?? 'USB')
    setLatitude(current?.current_location ? String(current.current_location.latitude) : '')
    setLongitude(current?.current_location ? String(current.current_location.longitude) : '')
    setCapabilities(rowsFrom(current?.capabilities ?? {}))
    setError(''); setNotice(''); setConflict(false)
  }

  useEffect(() => {
    if (open) populate(unit)
  }, [open, unit?.id])

  useEffect(() => {
    requestGeneration.current += 1
    return () => { requestGeneration.current += 1 }
  }, [open, unit?.id])

  async function reconcileConflict() {
    if (reconciling.current || !unit || !window.confirm('Descartar o rascunho local e carregar os dados atuais da unidade?')) return
    reconciling.current = true
    const generation = requestGeneration.current
    const unitId = unit.id
    setSubmitting(true)
    try {
      const current = await getFleetUnit(client, unitId)
      if (generation !== requestGeneration.current || currentUnitId.current !== unitId) return
      populate(current); setNotice('Dados atuais carregados. Revise antes de salvar novamente.')
      onRefreshed?.(current)
    } catch {
      if (generation === requestGeneration.current && currentUnitId.current === unitId) {
        setError('Não foi possível carregar os dados atuais da unidade.')
      }
    } finally {
      reconciling.current = false
      if (generation === requestGeneration.current) setSubmitting(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); if (sending.current) return
    const cleanName = name.trim(); const cleanPlate = plate.trim()
    if (!cleanName || !cleanPlate) { setError('Informe nome e placa da unidade.'); return }
    const hasLat = latitude.trim() !== ''; const hasLon = longitude.trim() !== ''
    if (hasLat !== hasLon) { setError('Informe latitude e longitude juntas ou deixe ambas vazias.'); return }
    const lat = Number(latitude); const lon = Number(longitude)
    if (hasLat && (!Number.isFinite(lat) || Math.abs(lat) > 90 || !Number.isFinite(lon) || Math.abs(lon) > 180)) {
      setError('Informe coordenadas válidas.'); return
    }
    let parsed: Record<string, unknown>
    try { parsed = parseCapabilities(capabilities) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Capacidades inválidas.'); return }
    const payload: FleetUnitPayload = {
      name: cleanName, license_plate: cleanPlate, unit_type: unitType,
      current_location: hasLat ? { latitude: lat, longitude: lon } : null,
      capabilities: parsed,
    }
    sending.current = true; setSubmitting(true); setError(''); setNotice(''); setConflict(false)
    try {
      const saved = unit
        ? await updateFleetUnit(client, unit.id, payload)
        : await createFleetUnit(client, payload)
      onSaved(saved, !unit)
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) {
        setConflict(true)
        setError('A unidade mudou durante a operação. Seu rascunho foi preservado.')
      }
      else if (reason instanceof ApiError && reason.status === 400) setError(messageFrom(reason) ?? 'Revise os dados informados.')
      else if (reason instanceof ApiError && reason.status === 403) setError('Seu usuário não possui autorização para administrar a frota.')
      else setError('Não foi possível salvar a unidade. Atualize os dados antes de tentar novamente.')
    } finally { sending.current = false; setSubmitting(false) }
  }

  if (!open) return null
  return <div className="unit-dialog-layer"><button className="unit-dialog-backdrop" tabIndex={-1} aria-label="Fechar formulário" onClick={onClose} />
    <div ref={dialog} tabIndex={-1} className="unit-dialog unit-form-dialog" role="dialog" aria-modal="true" aria-labelledby="unit-form-title" onKeyDownCapture={onKeyDown}>
      <div className="unit-dialog-heading"><div><p className="eyebrow">ADMINISTRAÇÃO DA FROTA</p><h2 id="unit-form-title" ref={title} tabIndex={-1}>{unit ? 'Editar unidade' : 'Nova unidade'}</h2></div><button aria-label="Fechar" onClick={onClose}>×</button></div>
      <form onSubmit={submit}><div className="unit-form-grid"><label>Nome<input value={name} onChange={event => setName(event.target.value)} maxLength={100} /></label><label>Placa<input value={plate} onChange={event => setPlate(event.target.value)} maxLength={20} /></label><label>Tipo<select value={unitType} disabled={restricted} onChange={event => setUnitType(event.target.value as UnitType)}><option value="USB">USB</option><option value="USA">USA</option><option value="UR">UR</option></select>{restricted && <small>Disponível somente quando a unidade estiver AVAILABLE.</small>}</label></div>
        <section className="unit-form-section"><h3>Localização opcional</h3><LocationPicker latitude={latitude} longitude={longitude} onChange={(lat, lon) => { setLatitude(lat); setLongitude(lon) }} ariaLabel="Selecione a localização da unidade no mapa" /></section>
        <section className="unit-form-section"><div className="capability-heading"><div><h3>Capacidades</h3><small>Valores simples ou JSON; limite total de 16 KiB.</small></div><button type="button" className="secondary-action" disabled={restricted} onClick={() => setCapabilities(rows => [...rows, { id: ++capabilityId, key: '', value: '' }])}>Adicionar capacidade</button></div>
          {restricted && <p className="field-help">Capacidades só podem ser alteradas quando a unidade estiver disponível.</p>}
          <div className="capability-editor">{capabilities.map(row => <div key={row.id}><label>Capacidade<input value={row.key} disabled={restricted} maxLength={64} onChange={event => setCapabilities(items => items.map(item => item.id === row.id ? { ...item, key: event.target.value } : item))} /></label><label>Valor<input value={row.value} disabled={restricted} onChange={event => setCapabilities(items => items.map(item => item.id === row.id ? { ...item, value: event.target.value } : item))} placeholder="true, 2 ou objeto JSON" /></label><button type="button" aria-label={`Remover capacidade ${row.key || 'sem nome'}`} disabled={restricted} onClick={() => setCapabilities(items => items.filter(item => item.id !== row.id))}>×</button></div>)}</div>
        </section>
        {!unit && <p className="unit-default-note">A unidade será criada com status AVAILABLE.</p>}
        {error && <div className="form-message" role="alert">{error}</div>}
        {notice && <div className="form-message" role="status">{notice}</div>}
        {conflict && unit && <button type="button" className="secondary-action" disabled={submitting} onClick={() => void reconcileConflict()}>Descartar rascunho e atualizar</button>}
        <div className="form-actions"><button type="button" className="secondary-action" onClick={onClose}>Cancelar</button><button type="submit" className="primary-action" disabled={submitting}>{submitting ? 'Salvando…' : unit ? 'Salvar alterações' : 'Cadastrar unidade'}</button></div>
      </form>
    </div></div>
}

export function MaintenanceDialog({ client, unit, open, onClose, onSaved, onRefresh }: {
  client: ApiClient; unit: FleetUnit; open: boolean; onClose: () => void
  onSaved: (unit: FleetUnit) => void; onRefresh: () => void
}) {
  const confirm = useRef<HTMLButtonElement>(null)
  const { dialog, onKeyDown } = useDialog(open, onClose, confirm)
  const [submitting, setSubmitting] = useState(false); const [error, setError] = useState('')
  const entering = unit.status !== 'MAINTENANCE'
  useEffect(() => { if (open) setError('') }, [open, unit.id])
  async function submit() {
    if (submitting) return
    setSubmitting(true); setError('')
    try { onSaved(entering ? await startMaintenance(client, unit.id) : await endMaintenance(client, unit.id)) }
    catch (reason) {
      if (reason instanceof ApiError && reason.status === 409) setError('A unidade possui estado ou missão incompatível. Atualize os dados antes de tentar novamente.')
      else setError('Não foi possível confirmar a operação de manutenção.')
    } finally { setSubmitting(false) }
  }
  if (!open) return null
  return <div className="unit-dialog-layer"><button className="unit-dialog-backdrop" tabIndex={-1} aria-label="Fechar confirmação" onClick={onClose} /><div ref={dialog} tabIndex={-1} className="unit-dialog maintenance-dialog" role="dialog" aria-modal="true" aria-labelledby="maintenance-title" onKeyDownCapture={onKeyDown}>
    <div className="unit-dialog-heading"><div><p className="eyebrow">ALTERAÇÃO OPERACIONAL</p><h2 id="maintenance-title">{entering ? 'Colocar em manutenção?' : 'Retirar da manutenção?'}</h2></div><button aria-label="Fechar" onClick={onClose}>×</button></div>
    <p><strong>{unit.name}</strong> passará de <b>{unit.status}</b> para <b>{entering ? 'MAINTENANCE' : 'AVAILABLE'}</b>. {entering ? 'Ela deixará de ser elegível para novos despachos.' : 'Ela voltará a ficar elegível para operações.'}</p>
    {error && <div className="form-message" role="alert">{error}<button type="button" onClick={onRefresh}>Atualizar dados</button></div>}
    <div className="form-actions"><button type="button" className="secondary-action" onClick={onClose}>Cancelar</button><button ref={confirm} type="button" className="primary-action" disabled={submitting} onClick={() => void submit()}>{submitting ? 'Confirmando…' : 'Confirmar alteração'}</button></div>
  </div></div>
}
