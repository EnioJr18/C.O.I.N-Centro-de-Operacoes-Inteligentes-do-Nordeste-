import { FormEvent, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { createMission } from '../api/missions'
import { useAuth } from '../auth/AuthContext'
import { OperationalShell } from '../layout/OperationalShell'
import { LocationPicker } from '../map/LocationPicker'
import { safeApiMessage, validateMissionForm } from './missionForm'

export function MissionFormPage() {
  const { client } = useAuth(); const navigate = useNavigate()
  const [description, setDescription] = useState(''); const [latitude, setLatitude] = useState(''); const [longitude, setLongitude] = useState('')
  const [errors, setErrors] = useState<ReturnType<typeof validateMissionForm>['errors']>({}); const [message, setMessage] = useState(''); const [submitting, setSubmitting] = useState(false)
  const sending = useRef(false)

  async function submit(event: FormEvent) {
    event.preventDefault(); if (sending.current) return
    const validated = validateMissionForm(description, latitude, longitude); setErrors(validated.errors); setMessage('')
    if (!validated.payload) return
    sending.current = true; setSubmitting(true)
    try { const mission = await createMission(client, validated.payload); navigate(`/missions/${mission.id}`) }
    catch (reason) {
      if (reason instanceof ApiError && reason.status === 403) setMessage('Seu usuário não possui autorização para criar missões.')
      else if (reason instanceof ApiError && reason.status === 400) setMessage(safeApiMessage(reason) || 'Revise os dados informados.')
      else if (reason instanceof ApiError) setMessage('Não foi possível criar a missão. Tente novamente após atualizar os dados.')
      else setMessage('Não foi possível confirmar a criação. O servidor pode ter recebido a operação; confira a lista de missões antes de tentar novamente.')
    } finally { sending.current = false; setSubmitting(false) }
  }

  return <OperationalShell section="MISSÕES"><main className="content form-content"><div className="back-line"><Link to="/missions">← Voltar para missões</Link></div><div className="page-heading"><div><p className="eyebrow">MISSÕES <span> / </span> NOVA MISSÃO</p><h1>Registrar missão<span>.</span></h1><p>Cria uma missão pendente, sem atribuir uma viatura.</p></div></div>
    <form className="mission-form" onSubmit={submit}><div className="form-section"><label>Descrição da ocorrência<textarea value={description} aria-invalid={!!errors.description} onChange={event => setDescription(event.target.value)} rows={4} />{errors.description && <span className="field-error">{errors.description}</span>}</label></div>
      <div className="form-section"><h2>Localização</h2><LocationPicker latitude={latitude} longitude={longitude} errors={errors} onChange={(lat, lon) => { setLatitude(lat); setLongitude(lon) }} /></div>
      {message && <div className="form-message" role="alert">{message}</div>}<div className="form-actions"><Link className="secondary-action" to="/missions">Cancelar</Link><button className="primary-action" disabled={submitting} type="submit">{submitting ? 'Salvando...' : 'Criar missão'}</button></div>
    </form>
  </main></OperationalShell>
}
