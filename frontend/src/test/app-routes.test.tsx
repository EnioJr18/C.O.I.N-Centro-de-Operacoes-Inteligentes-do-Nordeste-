import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../app/App'

const mocks = vi.hoisted(() => ({ role: 'OPERADOR' as 'OPERADOR' | 'ADMIN' }))
vi.mock('../auth/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({ user: { role: mocks.role }, client: {}, logout: vi.fn() }),
}))
vi.mock('../dashboard/OverviewPage', () => ({ OverviewPage: () => <h1>Resumo</h1> }))
vi.mock('../fleet/OperationsPage', () => ({ OperationsPage: () => <h1>Frota</h1> }))
vi.mock('../missions/MissionsPage', () => ({ MissionsPage: () => <h1>Missões</h1> }))
vi.mock('../missions/MissionFormPage', () => ({ MissionFormPage: () => <h1>Nova missão</h1> }))
vi.mock('../missions/MissionDetailsPage', () => ({ MissionDetailsPage: () => <h1>Detalhes</h1> }))
vi.mock('../missions/DispatchPage', () => ({ DispatchPage: () => <h1>Despacho</h1> }))
vi.mock('../app/ReservedPage', () => ({ ReservedPage: ({ kind }: { kind: string }) => <h1>{kind}</h1> }))
vi.mock('../profile/ProfilePage', () => ({ ProfilePage: () => <h1>Perfil</h1> }))
vi.mock('../users/UsersPage', () => ({ UsersPage: () => <h1>Usuários</h1> }))

beforeEach(() => { mocks.role = 'OPERADOR'; window.history.replaceState({}, '', '/') })

describe('organização das rotas', () => {
  it.each([
    ['/', 'Resumo'], ['/fleet', 'Frota'], ['/missions', 'Missões'], ['/missions/new', 'Nova missão'],
    ['/missions/12', 'Detalhes'], ['/missions/dispatch', 'Despacho'], ['/alerts', 'ALERTAS'], ['/profile', 'Perfil'],
  ])('resolve %s para seu módulo', (path, title) => {
    window.history.replaceState({}, '', path)
    render(<App />)
    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
  })

  it('redireciona OPERADOR que tenta acessar usuários e permite ADMIN', () => {
    window.history.replaceState({}, '', '/users')
    const view = render(<App />)
    expect(screen.getByRole('heading', { name: 'Resumo' })).toBeInTheDocument()
    mocks.role = 'ADMIN'; window.history.replaceState({}, '', '/users'); view.unmount(); render(<App />)
    expect(screen.getByRole('heading', { name: 'Usuários' })).toBeInTheDocument()
  })
})
