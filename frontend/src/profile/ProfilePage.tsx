import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import type { PasswordPayload, ProfilePayload } from '../api/profile'
import { useAuth } from '../auth/AuthContext'
import { OperationalShell } from '../layout/OperationalShell'

function apiMessage(error: unknown, fallback: string) {
  if (!(error instanceof ApiError)) return fallback
  if (error.status === 401) return 'Sua sessão expirou. Entre novamente.'
  if (error.status === 403) return 'Seu usuário não possui autorização para esta operação.'
  if (error.details) {
    for (const key of ['current_password', 'new_password', 'new_password_confirmation', 'first_name', 'last_name', 'non_field_errors']) {
      const value = error.details[key]
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0]
      if (typeof value === 'string') return value
    }
  }
  return fallback
}

function PasswordInput({ id, label, value, visible, onChange, onToggle }: { id: string; label: string; value: string; visible: boolean; onChange: (value: string) => void; onToggle: () => void }) {
  return <label htmlFor={id}>{label}<span className="password-control"><input id={id} type={visible ? 'text' : 'password'} autoComplete={id === 'current-password' ? 'current-password' : 'new-password'} value={value} onChange={event => onChange(event.target.value)} required /><button type="button" onClick={onToggle} aria-label={`${visible ? 'Ocultar' : 'Mostrar'} ${label.toLowerCase()}`} aria-pressed={visible}>{visible ? 'Ocultar' : 'Mostrar'}</button></span></label>
}

export function ProfilePage() {
  const { user, updateProfile, changePassword, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [firstName, setFirstName] = useState(user?.first_name ?? '')
  const [lastName, setLastName] = useState(user?.last_name ?? '')
  const [profilePending, setProfilePending] = useState(false)
  const [profileMessage, setProfileMessage] = useState('')
  const [profileError, setProfileError] = useState('')
  const profileSending = useRef(false)
  const [passwords, setPasswords] = useState<PasswordPayload>({ current_password: '', new_password: '', new_password_confirmation: '' })
  const [visible, setVisible] = useState({ current: false, next: false, confirmation: false })
  const [passwordPending, setPasswordPending] = useState(false)
  const [passwordError, setPasswordError] = useState('')
  const passwordSending = useRef(false)

  useEffect(() => { setFirstName(user?.first_name ?? ''); setLastName(user?.last_name ?? '') }, [user?.first_name, user?.last_name])

  async function submitProfile(event: FormEvent) {
    event.preventDefault(); if (profileSending.current) return
    profileSending.current = true; setProfilePending(true); setProfileMessage(''); setProfileError('')
    const payload: ProfilePayload = { first_name: firstName, last_name: lastName }
    try { await updateProfile(payload); setProfileMessage('Perfil atualizado com sucesso.') }
    catch (error) { setProfileError(apiMessage(error, 'Não foi possível atualizar o perfil.')) }
    finally { profileSending.current = false; setProfilePending(false) }
  }

  async function submitPassword(event: FormEvent) {
    event.preventDefault(); if (passwordSending.current) return
    setPasswordError('')
    if (passwords.new_password !== passwords.new_password_confirmation) { setPasswordError('A confirmação da nova senha não confere.'); return }
    if (passwords.current_password === passwords.new_password) { setPasswordError('A nova senha deve ser diferente da senha atual.'); return }
    passwordSending.current = true; setPasswordPending(true)
    try {
      await changePassword(passwords)
      setPasswords({ current_password: '', new_password: '', new_password_confirmation: '' })
      logout()
      navigate('/login', { replace: true, state: { passwordChanged: true, from: location.pathname } })
    } catch (error) { setPasswordError(apiMessage(error, 'Não foi possível alterar a senha.')) }
    finally { passwordSending.current = false; setPasswordPending(false) }
  }

  const role = user?.role === 'ADMIN' ? 'Administrador' : 'Operador'
  return <OperationalShell section="PERFIL"><main id="main-content" className="content profile-content" tabIndex={-1}>
    <div className="page-heading"><div><p className="eyebrow">CONTA <span> / </span> PERFIL</p><h1>Seu perfil<span>.</span></h1><p>Consulte sua identidade operacional e mantenha seus dados pessoais atualizados.</p></div></div>
    <div className="profile-grid"><section className="profile-card" aria-labelledby="personal-title"><div className="profile-card-heading"><div><p className="eyebrow">INFORMAÇÕES PESSOAIS</p><h2 id="personal-title">Dados da conta</h2></div><span className="account-id">ID #{user?.id}</span></div>
      <form onSubmit={submitProfile}><div className="profile-form-grid"><label htmlFor="first-name">Nome<input id="first-name" value={firstName} onChange={event => setFirstName(event.target.value)} maxLength={150} /></label><label htmlFor="last-name">Sobrenome<input id="last-name" value={lastName} onChange={event => setLastName(event.target.value)} maxLength={150} /></label></div>
        <div className="readonly-grid"><div><span>E-mail</span><strong>{user?.email || 'Não informado'}</strong><small>Somente leitura</small></div><div><span>Papel operacional</span><strong>{role}</strong><small>Somente leitura</small></div><div><span>Usuário</span><strong>{user?.username}</strong><small>Identificação da conta</small></div></div>
        {profileError && <div className="form-message" role="alert">{profileError}</div>}{profileMessage && <div className="success-message" role="status">{profileMessage}</div>}
        <div className="form-actions"><button className="primary-action" type="submit" disabled={profilePending}>{profilePending ? 'Salvando...' : 'Salvar alterações'}</button></div></form>
    </section>
    <section className="profile-card" aria-labelledby="password-title"><div className="profile-card-heading"><div><p className="eyebrow">SEGURANÇA DA CONTA</p><h2 id="password-title">Alterar senha</h2></div></div><p className="profile-help">Após a alteração, sua sessão será encerrada e você deverá entrar novamente.</p>
      <form onSubmit={submitPassword} className="password-form"><PasswordInput id="current-password" label="Senha atual" value={passwords.current_password} visible={visible.current} onChange={value => setPasswords(current => ({ ...current, current_password: value }))} onToggle={() => setVisible(current => ({ ...current, current: !current.current }))} />
        <PasswordInput id="new-password" label="Nova senha" value={passwords.new_password} visible={visible.next} onChange={value => setPasswords(current => ({ ...current, new_password: value }))} onToggle={() => setVisible(current => ({ ...current, next: !current.next }))} />
        <PasswordInput id="new-password-confirmation" label="Confirmar nova senha" value={passwords.new_password_confirmation} visible={visible.confirmation} onChange={value => setPasswords(current => ({ ...current, new_password_confirmation: value }))} onToggle={() => setVisible(current => ({ ...current, confirmation: !current.confirmation }))} />
        {passwordError && <div className="form-message" role="alert">{passwordError}</div>}<div className="form-actions"><button className="primary-action" type="submit" disabled={passwordPending}>{passwordPending ? 'Alterando...' : 'Alterar senha'}</button></div></form>
    </section></div>
  </main></OperationalShell>
}
