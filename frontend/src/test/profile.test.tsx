import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ApiError } from '../api/client'
import { ProfilePage } from '../profile/ProfilePage'

const user = { id: 7, username: 'ana', first_name: 'Ana', last_name: 'Silva', email: 'ana@coin.local', is_active: true, role: 'OPERADOR' as const }
const mocks = vi.hoisted(() => ({ updateProfile: vi.fn(), changePassword: vi.fn(), logout: vi.fn() }))
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ user, client: {}, ...mocks }) }))

function renderProfile() {
  return render(<MemoryRouter initialEntries={['/profile']}><Routes><Route path="/profile" element={<ProfilePage />} /><Route path="/login" element={<div>Login novamente</div>} /></Routes></MemoryRouter>)
}

beforeEach(() => { mocks.updateProfile.mockReset(); mocks.changePassword.mockReset(); mocks.logout.mockReset(); mocks.updateProfile.mockResolvedValue(user); mocks.changePassword.mockResolvedValue(undefined) })
afterEach(() => vi.restoreAllMocks())

describe('perfil', () => {
  it('renderiza identidade e mantém e-mail e papel somente leitura', () => {
    renderProfile()
    expect(screen.getByLabelText('Nome')).toHaveValue('Ana')
    expect(screen.getByLabelText('Sobrenome')).toHaveValue('Silva')
    expect(screen.getByText('ana@coin.local')).toBeInTheDocument()
    expect(screen.getAllByText('Operador')).toHaveLength(2)
    expect(screen.queryByLabelText('E-mail')).not.toBeInTheDocument()
  })

  it('envia somente nome e sobrenome, mostra loading e bloqueia submissão duplicada', async () => {
    let resolve!: (value: typeof user) => void
    mocks.updateProfile.mockReturnValue(new Promise(done => { resolve = done }))
    const view = renderProfile()
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: 'Beatriz' } })
    fireEvent.change(screen.getByLabelText('Sobrenome'), { target: { value: 'Costa' } })
    const form = screen.getByRole('button', { name: 'Salvar alterações' }).closest('form')!
    fireEvent.submit(form); fireEvent.submit(form)
    expect(mocks.updateProfile).toHaveBeenCalledOnce()
    expect(mocks.updateProfile).toHaveBeenCalledWith({ first_name: 'Beatriz', last_name: 'Costa' })
    expect(screen.getByRole('button', { name: 'Salvando...' })).toBeDisabled()
    resolve({ ...user, first_name: 'Beatriz', last_name: 'Costa' })
    expect(await screen.findByRole('status')).toHaveTextContent('Perfil atualizado com sucesso')
    view.unmount()
  })

  it('apresenta erro estruturado da API sem dados sensíveis', async () => {
    mocks.updateProfile.mockRejectedValue(new ApiError(400, undefined, { first_name: ['Nome inválido.'] }))
    renderProfile()
    fireEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Nome inválido.')
  })
})

describe('alteração de senha', () => {
  function fill(current = 'OldPassword123', next = 'NewPassword123', confirmation = next) {
    fireEvent.change(screen.getByLabelText('Senha atual'), { target: { value: current } })
    fireEvent.change(screen.getByLabelText('Nova senha'), { target: { value: next } })
    fireEvent.change(screen.getByLabelText('Confirmar nova senha'), { target: { value: confirmation } })
  }

  it('valida confirmação e diferença antes da API', async () => {
    renderProfile(); fill('SamePassword123', 'SamePassword123', 'OtherPassword123')
    fireEvent.click(screen.getByRole('button', { name: 'Alterar senha' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('confirmação')
    expect(mocks.changePassword).not.toHaveBeenCalled()
    fill('SamePassword123', 'SamePassword123', 'SamePassword123')
    fireEvent.click(screen.getByRole('button', { name: 'Alterar senha' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('diferente')
    expect(mocks.changePassword).not.toHaveBeenCalled()
  })

  it('mostra e oculta senhas com controles acessíveis', () => {
    renderProfile()
    const input = screen.getByLabelText('Senha atual')
    expect(input).toHaveAttribute('type', 'password')
    fireEvent.click(screen.getByRole('button', { name: 'Mostrar senha atual' }))
    expect(input).toHaveAttribute('type', 'text')
    fireEvent.click(screen.getByRole('button', { name: 'Ocultar senha atual' }))
    expect(input).toHaveAttribute('type', 'password')
  })

  it('envia o contrato, impede duplicação, encerra sessão e redireciona', async () => {
    let resolve!: () => void
    mocks.changePassword.mockReturnValue(new Promise<void>(done => { resolve = done }))
    renderProfile(); fill()
    const form = screen.getByRole('button', { name: 'Alterar senha' }).closest('form')!
    fireEvent.submit(form); fireEvent.submit(form)
    expect(mocks.changePassword).toHaveBeenCalledOnce()
    expect(mocks.changePassword).toHaveBeenCalledWith({ current_password: 'OldPassword123', new_password: 'NewPassword123', new_password_confirmation: 'NewPassword123' })
    expect(screen.getByRole('button', { name: 'Alterando...' })).toBeDisabled()
    resolve()
    expect(await screen.findByText('Login novamente')).toBeInTheDocument()
    expect(mocks.logout).toHaveBeenCalledOnce()
  })

  it('mostra erro seguro do backend e mantém a sessão', async () => {
    mocks.changePassword.mockRejectedValue(new ApiError(400, undefined, { current_password: ['Senha atual incorreta.'] }))
    renderProfile(); fill()
    fireEvent.click(screen.getByRole('button', { name: 'Alterar senha' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Senha atual incorreta.')
    expect(mocks.logout).not.toHaveBeenCalled()
  })

  it('não usa armazenamento persistente nem registra senhas', async () => {
    const local = vi.spyOn(Storage.prototype, 'setItem')
    const logger = vi.spyOn(console, 'log').mockImplementation(() => undefined)
    renderProfile(); fill(); fireEvent.click(screen.getByRole('button', { name: 'Alterar senha' }))
    await screen.findByText('Login novamente')
    expect(local).not.toHaveBeenCalled()
    expect(logger).not.toHaveBeenCalled()
  })
})
