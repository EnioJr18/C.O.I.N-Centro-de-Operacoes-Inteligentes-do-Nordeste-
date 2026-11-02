import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { ApiError } from '../api/client'
import type { ManagedUser } from '../api/types'
import { UsersPage } from '../users/UsersPage'

const mocks = vi.hoisted(() => ({
  client: { request: vi.fn() },
  user: { id: 1, username: 'admin', first_name: 'Ana', last_name: 'Admin', email: 'admin@example.com', is_active: true, is_superuser: false, role: 'ADMIN' as const, date_joined: '2026-10-01T12:00:00Z' },
}))
const current: ManagedUser = mocks.user
const operator: ManagedUser = { id: 2, username: 'operator', first_name: 'Bia', last_name: 'Silva', email: 'bia@example.com', is_active: true, is_superuser: false, role: 'OPERADOR', date_joined: '2026-10-02T12:00:00Z' }
const root: ManagedUser = { id: 3, username: 'root', first_name: '', last_name: '', email: 'root@example.com', is_active: true, is_superuser: true, role: 'ADMIN', date_joined: '2026-10-03T12:00:00Z' }
const request = vi.fn()
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user: mocks.user, client: mocks.client, logout: vi.fn() }) }))

function LocationProbe() { const location = useLocation(); return <output data-testid="location">{location.search}</output> }
function renderPage(entry = '/users') { return render(<MemoryRouter initialEntries={[entry]}><LocationProbe /><Routes><Route path="/users" element={<UsersPage />} /></Routes></MemoryRouter>) }
const page = { count: 3, next: null, previous: null, results: [current, operator, root] }

beforeEach(() => {
  request.mockReset(); mocks.client.request = request
  request.mockImplementation(async (path: string, options?: RequestInit) => {
    if (options?.method === 'POST' && path === '/api/v1/auth/users/') return { ...operator, id: 9, username: 'newop', email: 'new@example.com' }
    if (path.endsWith('/role/')) return { ...operator, role: 'ADMIN' }
    if (path.endsWith('/activate/')) return { ...operator, is_active: true }
    if (path.endsWith('/deactivate/')) return { ...operator, is_active: false }
    if (path === '/api/v1/auth/users/2/' && options?.method === 'PATCH') return { ...operator, first_name: 'Nova' }
    if (path === '/api/v1/auth/users/1/') return current
    if (path === '/api/v1/auth/users/2/') return operator
    if (path === '/api/v1/auth/users/3/') return root
    return page
  })
})

describe('administração de usuários', () => {
  it('lista dados, superusuário, paginação e mantém filtros na URL', async () => {
    renderPage('/users?search=bia')
    expect(await screen.findByText('Bia Silva')).toBeInTheDocument()
    expect(screen.getByText('SUPERUSUÁRIO')).toBeInTheDocument()
    expect(request.mock.calls[0][0]).toContain('search=bia')
    fireEvent.change(screen.getByLabelText('Papel'), { target: { value: 'OPERADOR' } })
    fireEvent.change(screen.getByLabelText('Situação'), { target: { value: 'false' } })
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }))
    expect(screen.getByTestId('location')).toHaveTextContent('search=bia')
    expect(screen.getByTestId('location')).toHaveTextContent('role=OPERADOR')
    expect(screen.getByTestId('location')).toHaveTextContent('is_active=false')
  })

  it('cria OPERADOR sem enviar confirmação e limpa o diálogo', async () => {
    const storage = vi.spyOn(Storage.prototype, 'setItem')
    const logger = vi.spyOn(console, 'log').mockImplementation(() => undefined)
    renderPage(); await screen.findByText('Bia Silva')
    fireEvent.click(screen.getByRole('button', { name: 'Novo usuário' }))
    const dialog = screen.getByRole('dialog', { name: 'Novo usuário' })
    fireEvent.change(within(dialog).getByLabelText('Nome'), { target: { value: 'Novo' } })
    fireEvent.change(within(dialog).getByLabelText('Sobrenome'), { target: { value: 'Operador' } })
    fireEvent.change(within(dialog).getByLabelText('Username'), { target: { value: 'newop' } })
    fireEvent.change(within(dialog).getByLabelText('E-mail'), { target: { value: 'new@example.com' } })
    fireEvent.change(within(dialog).getByLabelText('Senha inicial'), { target: { value: 'Password123' } })
    fireEvent.change(within(dialog).getByLabelText('Confirmar senha inicial'), { target: { value: 'Password123' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Criar operador' }))
    expect(await screen.findByText(/criado com sucesso/)).toBeInTheDocument()
    const call = request.mock.calls.find(([path, options]) => path === '/api/v1/auth/users/' && options?.method === 'POST')
    expect(JSON.parse(call![1].body)).toEqual({ username: 'newop', email: 'new@example.com', first_name: 'Novo', last_name: 'Operador', password: 'Password123' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(storage).not.toHaveBeenCalled(); expect(logger).not.toHaveBeenCalled()
  })

  it('rejeita confirmação divergente sem enviar a senha', async () => {
    renderPage(); await screen.findByText('Bia Silva')
    fireEvent.click(screen.getByRole('button', { name: 'Novo usuário' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Username'), { target: { value: 'newop' } })
    fireEvent.change(within(dialog).getByLabelText('E-mail'), { target: { value: 'new@example.com' } })
    fireEvent.change(within(dialog).getByLabelText('Senha inicial'), { target: { value: 'Password123' } })
    fireEvent.change(within(dialog).getByLabelText('Confirmar senha inicial'), { target: { value: 'Different123' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Criar operador' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('não confere')
    expect(request.mock.calls.some(([path, options]) => path === '/api/v1/auth/users/' && options?.method === 'POST')).toBe(false)
  })

  it('mantém conta própria e superusuário somente leitura', async () => {
    renderPage(); await screen.findByText('Bia Silva')
    const rootRow = screen.getByText('@root').closest('tr')!
    fireEvent.click(within(rootRow).getByRole('button', { name: 'Ver detalhes' }))
    const dialog = await screen.findByRole('dialog', { name: 'Detalhes do usuário' })
    expect(within(dialog).getByText('Superusuários são somente leitura nesta área.')).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /Promover|Rebaixar|Desativar|Ativar/ })).not.toBeInTheDocument()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Fechar' }))
    const selfRow = screen.getByText('@admin').closest('tr')!
    fireEvent.click(within(selfRow).getByRole('button', { name: 'Ver detalhes' }))
    expect(await screen.findByText('Use a página de perfil para alterar sua própria conta.')).toBeInTheDocument()
  })

  it('edita nomes e exige confirmação para papel e estado', async () => {
    renderPage(); await screen.findByText('Bia Silva')
    const row = screen.getByText('@operator').closest('tr')!
    fireEvent.click(within(row).getByRole('button', { name: 'Ver detalhes' }))
    const details = await screen.findByRole('dialog', { name: 'Detalhes do usuário' })
    fireEvent.change(within(details).getByLabelText('Nome'), { target: { value: 'Nova' } })
    fireEvent.click(within(details).getByRole('button', { name: 'Salvar nomes' }))
    await waitFor(() => expect(request).toHaveBeenCalledWith('/api/v1/auth/users/2/', expect.objectContaining({ method: 'PATCH' })))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Promover para ADMIN' }))
    const confirmation = screen.getByRole('dialog', { name: 'Confirmar operação' })
    expect(confirmation).toHaveTextContent('OPERADOR para ADMIN')
    fireEvent.click(within(confirmation).getByRole('button', { name: 'Confirmar' }))
    await waitFor(() => expect(request).toHaveBeenCalledWith('/api/v1/auth/users/2/role/', expect.objectContaining({ method: 'PATCH' })))
  })

  it('apresenta conflito do último ADMIN e fecha diálogo com Escape', async () => {
    request.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === '/api/v1/auth/users/2/') return { ...operator, role: 'ADMIN' }
      if (path.endsWith('/role/') && options?.method === 'PATCH') throw new ApiError(409, undefined, { detail: 'Não é possível remover o último administrador ativo do sistema.' })
      return page
    })
    renderPage(); await screen.findByText('Bia Silva')
    fireEvent.click(within(screen.getByText('@operator').closest('tr')!).getByRole('button', { name: 'Ver detalhes' }))
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Rebaixar para OPERADOR' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Confirmar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('último administrador ativo')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
