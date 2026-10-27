import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from './AuthContext'

export function LoginPage() {
  const { login, user } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  if (user) return <Navigate to="/" replace />
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!email.trim() || !password) { setError('Informe seu e-mail e sua senha.'); return }
    setPending(true); setError('')
    try { await login(email.trim(), password) }
    catch (err) { setError(err instanceof ApiError ? err.message : 'Não foi possível conectar ao servidor.') }
    finally { setPending(false) }
  }
  return <main className="login-shell">
    <div className="login-brand"><span className="brand-symbol">✳</span> C.O.I.N. <span className="brand-tag">CENTRO DE OPERAÇÕES</span></div>
    <div className="login-grid"><section className="login-intro"><p className="eyebrow">CENTRO DE OPERAÇÕES INTELIGENTES</p><h1>Informação certa.<br /><span>No momento certo.</span></h1><p>Acompanhe a disponibilidade das unidades e mantenha a operação em movimento.</p><div className="login-rule" /><p className="login-caption">PLATAFORMA OPERACIONAL · NORDESTE</p></section>
      <section className="login-card"><div className="card-topline"><span>ACESSO RESTRITO</span><span>01 / 01</span></div><h2>Bem-vindo de volta</h2><p>Entre com suas credenciais para acessar o centro de operações.</p><form onSubmit={submit}>
        <label htmlFor="email">E-mail</label><input id="email" type="email" autoComplete="username" placeholder="seu@email.com" value={email} onChange={e => setEmail(e.target.value)} required />
        <label htmlFor="password">Senha</label><input id="password" type="password" autoComplete="current-password" placeholder="Sua senha" value={password} onChange={e => setPassword(e.target.value)} required />
        {error && <p role="alert" className="error-text">{error}</p>}
        <button className="primary-button" type="submit" disabled={pending}>{pending ? 'Entrando...' : 'Acessar operações'} <span aria-hidden="true">↗</span></button>
      </form><p className="login-note">A sessão é encerrada ao atualizar ou fechar esta página.</p></section>
    </div><footer className="login-footer">C.O.I.N. <span>INFORMAÇÃO PARA QUEM ESTÁ EM CAMPO</span></footer>
  </main>
}
