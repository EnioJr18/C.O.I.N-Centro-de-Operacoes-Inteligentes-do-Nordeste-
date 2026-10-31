import { FormEvent, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'
import { dispatchEmergency } from '../api/missions'
import type { DispatchResult, UnitType } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { OperationalShell } from '../layout/OperationalShell'
import { LocationPicker } from '../map/LocationPicker'
import { safeApiMessage, validateMissionForm } from './missionForm'

function distance(value: number) { return value >= 1000 ? `${(value / 1000).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} km` : `${Math.round(value).toLocaleString('pt-BR')} m` }

export function DispatchPage() {
  const { client } = useAuth()
  const [description, setDescription] = useState(''); const [latitude, setLatitude] = useState(''); const [longitude, setLongitude] = useState(''); const [requiredType, setRequiredType] = useState<UnitType | ''>('')
  const [errors, setErrors] = useState<ReturnType<typeof validateMissionForm>['errors']>({}); const [message, setMessage] = useState(''); const [result, setResult] = useState<DispatchResult | null>(null); const [submitting, setSubmitting] = useState(false)
  const sending = useRef(false)

  async function submit(event: FormEvent) {
    event.preventDefault(); if (sending.current) return
    const validated = validateMissionForm(description, latitude, longitude); setErrors(validated.errors); setMessage(''); setResult(null)
    if (!validated.payload) return
    sending.current = true; setSubmitting(true)
    try { setResult(await dispatchEmergency(client, { ...validated.payload, required_type: requiredType || undefined })) }
    catch (reason) {
      if (reason instanceof ApiError && reason.status === 403) setMessage('Seu usuário não possui autorização para despachar emergências.')
      else if (reason instanceof ApiError && reason.status === 404) setMessage(safeApiMessage(reason) || 'Nenhuma viatura elegível está disponível.')
      else if (reason instanceof ApiError && reason.status === 409) setMessage(safeApiMessage(reason) || 'O despacho entrou em conflito com outra operação. Atualize os dados antes de tentar novamente.')
      else if (reason instanceof ApiError && reason.status === 400) setMessage(safeApiMessage(reason) || 'Revise os dados informados.')
      else if (reason instanceof ApiError) setMessage('Não foi possível realizar o despacho. Atualize os dados e tente novamente.')
      else setMessage('Resultado indeterminado: o servidor pode ter confirmado o despacho. Confira a lista de missões e a frota antes de tentar novamente.')
    } finally { sending.current = false; setSubmitting(false) }
  }

  return <OperationalShell section="MISSÕES"><main className="content form-content"><div className="back-line"><Link to="/missions">← Voltar para missões</Link></div><div className="page-heading"><div><p className="eyebrow">MISSÕES <span> / </span> DESPACHO</p><h1>Despachar emergência<span>.</span></h1><p>Cria uma nova missão e seleciona a viatura elegível mais próxima.</p></div></div>
    <form className="mission-form" onSubmit={submit}><div className="form-section"><label>Descrição da ocorrência<textarea value={description} aria-invalid={!!errors.description} onChange={event => setDescription(event.target.value)} rows={4} />{errors.description && <span className="field-error">{errors.description}</span>}</label><label>Tipo de unidade (opcional)<select value={requiredType} onChange={event => setRequiredType(event.target.value as UnitType | '')}><option value="">Qualquer unidade elegível</option><option value="USB">USB — Suporte Básico</option><option value="USA">USA — Suporte Avançado</option><option value="UR">UR — Resgate</option></select></label></div>
      <div className="form-section"><h2>Localização da ocorrência</h2><LocationPicker latitude={latitude} longitude={longitude} errors={errors} onChange={(lat, lon) => { setLatitude(lat); setLongitude(lon) }} /></div>
      {message && <div className="form-message" role="alert">{message}</div>}{result && <section className="dispatch-result" role="status"><p className="eyebrow">DESPACHO CONFIRMADO PELA API</p><h2>Missão #{result.mission.id}</h2><dl><div><dt>Status</dt><dd>{result.mission.status}</dd></div><div><dt>Viatura</dt><dd>{result.dispatched_unit.name}</dd></div><div><dt>Tipo / identificação</dt><dd>{result.dispatched_unit.unit_type} / {result.dispatched_unit.license_plate}</dd></div><div><dt>Distância</dt><dd>{distance(result.distance_meters)}</dd></div></dl><Link to={`/missions/${result.mission.id}`}>Ver detalhes da missão →</Link></section>}
      <div className="form-actions"><Link className="secondary-action" to="/missions">Cancelar</Link><button className="primary-action danger-action" disabled={submitting || !!result} type="submit">{submitting ? 'Despachando...' : result ? 'Despacho confirmado' : 'Confirmar despacho'}</button></div>
    </form>
  </main></OperationalShell>
}
