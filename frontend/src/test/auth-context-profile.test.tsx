import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from '../auth/AuthContext'

const original = { id: 1, username: 'ana', first_name: 'Ana', last_name: 'Silva', email: 'ana@coin.local', is_active: true, role: 'OPERADOR' }
const updated = { ...original, first_name: 'Beatriz', last_name: 'Costa' }
const reply = (data: unknown, status = 200) => new Response(status === 204 ? null : JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })

function Harness() {
  const { user, login, updateProfile } = useAuth()
  if (!user) return <button onClick={() => void login('ana@coin.local', 'Password123')}>Entrar</button>
  return <><span>{user.first_name} {user.last_name}</span><button onClick={() => void updateProfile({ first_name: 'Beatriz', last_name: 'Costa' })}>Atualizar</button></>
}

afterEach(() => vi.unstubAllGlobals())

it('AuthContext atualiza a identidade em memória com a resposta do PATCH sem novo GET', async () => {
  const fetcher = vi.fn(async (path: string, options?: RequestInit) => {
    if (path.endsWith('/login/')) return reply({ access: 'access', refresh: 'refresh' })
    if (path.endsWith('/me/') && options?.method === 'PATCH') return reply(updated)
    if (path.endsWith('/me/')) return reply(original)
    return reply({}, 404)
  })
  vi.stubGlobal('fetch', fetcher)
  render(<AuthProvider><Harness /></AuthProvider>)
  fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))
  expect(await screen.findByText('Ana Silva')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Atualizar' }))
  expect(await screen.findByText('Beatriz Costa')).toBeInTheDocument()
  expect(fetcher.mock.calls.filter(([path]) => path.endsWith('/me/'))).toHaveLength(2)
  expect(fetcher.mock.calls.filter(([, options]) => options?.method === 'PATCH')).toHaveLength(1)
})
