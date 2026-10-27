import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../app/App'

vi.mock('../fleet/OperationsPage', async () => {
  const { useAuth } = await import('../auth/AuthContext')
  return { OperationsPage: () => { const { logout } = useAuth(); return <div>Área operacional<button onClick={logout}>Sair</button></div> } }
})
const reply = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
beforeEach(() => window.history.pushState({}, '', '/'))
afterEach(() => vi.unstubAllGlobals())

describe('entrada na área operacional', () => {
  it('encaminha visitante anônimo ao login e autentica usuário válido', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(reply({ access: 'token', refresh: 'refresh' }))
      .mockResolvedValueOnce(reply({ id: 1, username: 'operador', first_name: '', last_name: '', email: 'a@example.com', is_active: true, role: 'OPERADOR' }))
    vi.stubGlobal('fetch', fetcher)
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Bem-vindo de volta' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: 'a@example.com' } })
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'password' } })
    fireEvent.click(screen.getByRole('button', { name: /Acessar operações/ }))
    expect(await screen.findByText('Área operacional')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Sair' }))
    expect(await screen.findByRole('heading', { name: 'Bem-vindo de volta' })).toBeInTheDocument()
  })

  it('mostra erro compreensível para credenciais inválidas', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(reply({ detail: 'invalid' }, 401)))
    render(<App />)
    fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: 'a@example.com' } })
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'wrong' } })
    fireEvent.click(screen.getByRole('button', { name: /Acessar operações/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha inválidos')
    expect(screen.queryByText('Área operacional')).not.toBeInTheDocument()
  })
})
