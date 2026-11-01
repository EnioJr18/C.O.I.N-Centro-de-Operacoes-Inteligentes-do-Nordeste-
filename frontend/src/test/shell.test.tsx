import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { OperationalShell } from '../layout/OperationalShell'
import { ReservedPage } from '../app/ReservedPage'

const mocks = vi.hoisted(() => ({
  logout: vi.fn(),
  user: { id: 1, username: 'ana', first_name: 'Ana', last_name: 'Silva', email: 'ana@coin.local', is_active: true, role: 'OPERADOR' as 'OPERADOR' | 'ADMIN' },
}))
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user: mocks.user, logout: mocks.logout, client: {} }) }))

beforeEach(() => { mocks.logout.mockClear(); mocks.user.role = 'OPERADOR'; document.body.style.overflow = '' })

function renderShell(path = '/') {
  return render(<MemoryRouter initialEntries={[path]}><OperationalShell section="VISÃO GERAL"><main id="main-content">Conteúdo</main></OperationalShell></MemoryRouter>)
}

describe('shell operacional', () => {
  it('organiza navegação, marca a rota ativa e oculta administração do OPERADOR', () => {
    renderShell('/fleet')
    expect(screen.getAllByRole('link', { name: 'Frota' })[0]).toHaveAttribute('aria-current', 'page')
    expect(screen.getAllByRole('link', { name: 'Visão geral' })[0]).not.toHaveAttribute('aria-current')
    expect(screen.queryByRole('link', { name: 'Usuários' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Pular para o conteúdo principal' })).toHaveAttribute('href', '#main-content')
  })

  it('exibe a área administrativa somente para ADMIN', () => {
    mocks.user.role = 'ADMIN'
    renderShell()
    expect(screen.getByRole('navigation', { name: 'Administração' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Usuários' })).toHaveAttribute('href', '/users')
  })

  it('abre drawer acessível, bloqueia rolagem e fecha com Escape devolvendo o foco', async () => {
    renderShell()
    const opener = screen.getByRole('button', { name: 'Abrir menu' })
    fireEvent.click(opener)
    const dialog = screen.getByRole('dialog', { name: 'Menu principal' })
    expect(dialog).toBeInTheDocument()
    expect(document.body.style.overflow).toBe('hidden')
    fireEvent.keyDown(dialog, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'Menu principal' })).not.toBeInTheDocument()
    await vi.waitFor(() => expect(opener).toHaveFocus())
    expect(document.body.style.overflow).toBe('')
  })

  it('mostra dados seguros no menu de conta, navega ao perfil e reutiliza logout', () => {
    renderShell()
    fireEvent.click(screen.getByRole('button', { name: /Ana Silva/ }))
    const menu = screen.getByRole('menu')
    expect(within(menu).getByText('ana@coin.local')).toBeInTheDocument()
    expect(within(menu).getByText('Operador')).toBeInTheDocument()
    expect(within(menu).getByRole('menuitem', { name: /Ver perfil/ })).toHaveAttribute('href', '/profile')
    fireEvent.click(within(menu).getByRole('menuitem', { name: /Sair da sessão/ }))
    expect(mocks.logout).toHaveBeenCalledOnce()
  })
})

describe('módulos reservados', () => {
  it.each([
    ['ALERTAS', 'Central de alertas'],
    ['USUÁRIOS', 'Administração de usuários'],
  ] as const)('identifica %s como módulo em preparação sem ação fictícia', (kind, title) => {
    render(<MemoryRouter><ReservedPage kind={kind} /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: `${title}.` })).toBeInTheDocument()
    expect(screen.getByText('MÓDULO EM PREPARAÇÃO')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voltar à visão geral' })).toHaveAttribute('href', '/')
  })
})
