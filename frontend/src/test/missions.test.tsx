import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ApiError } from '../api/client'
import type { Mission } from '../api/types'

const mocks = vi.hoisted(() => ({ client: {}, list: vi.fn(), get: vi.fn(), history: vi.fn(), create: vi.fn(), dispatch: vi.fn(), complete: vi.fn(), cancel: vi.fn() }))
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ client: mocks.client, user: { username: 'op', first_name: '', role: 'OPERADOR' }, logout: vi.fn() }) }))
vi.mock('../api/missions', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/missions')>()
  return { ...actual, listMissions: mocks.list, getMission: mocks.get, getMissionHistory: mocks.history, createMission: mocks.create, dispatchEmergency: mocks.dispatch, completeMission: mocks.complete, cancelMission: mocks.cancel }
})
vi.mock('../map/LocationPicker', () => ({ LocationPicker: ({ latitude, longitude, onChange, errors = {} }: { latitude: string; longitude: string; onChange: (lat: string, lon: string) => void; errors?: { latitude?: string; longitude?: string } }) => <div>
  <label>Latitude<input value={latitude} onChange={event => onChange(event.target.value, longitude)} /></label>{errors.latitude && <span>{errors.latitude}</span>}
  <label>Longitude<input value={longitude} onChange={event => onChange(latitude, event.target.value)} /></label>{errors.longitude && <span>{errors.longitude}</span>}
</div> }))

import { MissionsPage } from '../missions/MissionsPage'
import { MissionDetailsPage } from '../missions/MissionDetailsPage'
import { MissionFormPage } from '../missions/MissionFormPage'
import { DispatchPage } from '../missions/DispatchPage'

const unit = { id: 3, name: 'Alfa 03', license_plate: 'AAA-0003', unit_type: 'USA' as const, current_location: { latitude: -9, longitude: -35 }, status: 'BUSY' as const, capabilities: {}, created_at: '', updated_at: '' }
const mission: Mission = { id: 7, description: 'Atendimento urgente', location: { latitude: -9, longitude: -35 }, status: 'Pendente', assigned_unit: null, created_at: '2026-10-31T12:00:00Z', updated_at: '2026-10-31T12:00:00Z' }
const renderRoute = (element: React.ReactNode, path = '/missions', route = '/missions') => render(<MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={element} /><Route path="/missions/:missionId" element={<div>Destino detalhe</div>} /></Routes></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks() })

describe('lista e detalhes de missões', () => {
  it('lista, filtra, pagina e representa vazio e falha', async () => {
    mocks.list.mockResolvedValueOnce({ count: 21, next: '/api/v1/missions/?page=2', previous: null, results: [mission] })
      .mockResolvedValueOnce({ count: 21, next: null, previous: '/api/v1/missions/', results: [{ ...mission, id: 8 }] })
      .mockResolvedValueOnce({ count: 0, next: null, previous: null, results: [] })
    renderRoute(<MissionsPage />)
    expect(await screen.findByText('Atendimento urgente')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Próxima/ }))
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(mocks.client, expect.objectContaining({ page: 2 }), expect.any(AbortSignal)))
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'Concluída' } })
    fireEvent.submit(screen.getByRole('button', { name: 'Aplicar filtros' }).closest('form')!)
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(mocks.client, expect.objectContaining({ status: 'Concluída', page: 1 }), expect.any(AbortSignal)))
    expect(await screen.findByText('Nenhuma missão encontrada.')).toBeInTheDocument()
  })

  it('valida intervalo de filtros antes da API', async () => {
    mocks.list.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    renderRoute(<MissionsPage />); await screen.findByText('Nenhuma missão encontrada.')
    fireEvent.change(screen.getByLabelText('Criadas a partir de'), { target: { value: '2026-10-31T14:00' } })
    fireEvent.change(screen.getByLabelText('Criadas até'), { target: { value: '2026-10-31T13:00' } })
    fireEvent.click(screen.getByRole('button', { name: 'Aplicar filtros' }))
    expect(screen.getByRole('alert')).toHaveTextContent('data inicial')
  })

  it('exibe falha de consulta e permite tentar novamente', async () => {
    mocks.list.mockRejectedValueOnce(new TypeError('network')).mockResolvedValueOnce({ count: 0, next: null, previous: null, results: [] })
    renderRoute(<MissionsPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível carregar as missões')
    fireEvent.click(screen.getByRole('button', { name: /Tentar novamente/ }))
    expect(await screen.findByText('Nenhuma missão encontrada.')).toBeInTheDocument()
    expect(mocks.list).toHaveBeenCalledTimes(2)
  })

  it('mostra missão sem unidade e histórico paginado', async () => {
    mocks.get.mockResolvedValue(mission)
    mocks.history.mockResolvedValue({ count: 21, next: '/api/v1/missions/7/history/?page=2', previous: null, results: [{ id: 1, status: 'Pendente', notes: null, timestamp: mission.created_at, actor: null }] })
    renderRoute(<MissionDetailsPage />, '/missions/7', '/missions/:missionId')
    expect(await screen.findByText('Nenhuma unidade foi atribuída a esta missão.')).toBeInTheDocument()
    expect(screen.getByText('Sem observações.')).toBeInTheDocument()
    expect(screen.getByText('Operador: Não identificado')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Próxima/ }))
    await waitFor(() => expect(mocks.history).toHaveBeenLastCalledWith(mocks.client, 7, 2, expect.any(AbortSignal)))
  })

  it('rejeita identificador inválido sem consultar a API', () => {
    renderRoute(<MissionDetailsPage />, '/missions/inválida', '/missions/:missionId')
    expect(screen.getByRole('alert')).toHaveTextContent('Identificador de missão inválido')
    expect(mocks.get).not.toHaveBeenCalled(); expect(mocks.history).not.toHaveBeenCalled()
  })
})

describe('operações de escrita', () => {
  function fillValid() {
    fireEvent.change(screen.getByLabelText(/^Descrição da ocorrência/), { target: { value: '  Ocorrência  ' } })
    fireEvent.change(screen.getByLabelText(/^Latitude/), { target: { value: '-9' } })
    fireEvent.change(screen.getByLabelText(/^Longitude/), { target: { value: '-35' } })
  }

  it('valida criação e bloqueia submissões duplicadas até a confirmação', async () => {
    let resolve!: (value: Mission) => void
    mocks.create.mockReturnValue(new Promise<Mission>(done => { resolve = done }))
    const view = renderRoute(<MissionFormPage />, '/missions/new', '/missions/new')
    fireEvent.click(screen.getByRole('button', { name: 'Criar missão' }))
    expect(screen.getByText('Informe a descrição da ocorrência.')).toBeInTheDocument()
    fillValid()
    const form = view.container.querySelector('form')!
    fireEvent.submit(form); fireEvent.submit(form)
    expect(mocks.create).toHaveBeenCalledOnce()
    expect(mocks.create).toHaveBeenCalledWith(mocks.client, { description: 'Ocorrência', location: { latitude: -9, longitude: -35 } })
    resolve(mission)
    expect(await screen.findByText('Destino detalhe')).toBeInTheDocument()
  })

  it('confirma despacho real e exibe viatura e distância', async () => {
    mocks.dispatch.mockResolvedValue({ mission: { ...mission, status: 'Em Andamento', assigned_unit: unit }, dispatched_unit: unit, distance_meters: 1520 })
    renderRoute(<DispatchPage />, '/missions/dispatch', '/missions/dispatch'); fillValid()
    fireEvent.change(screen.getByLabelText('Tipo de unidade (opcional)'), { target: { value: 'USA' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar despacho' }))
    expect(await screen.findByText('DESPACHO CONFIRMADO PELA API')).toBeInTheDocument()
    expect(screen.getByText('Alfa 03')).toBeInTheDocument(); expect(screen.getByText('1,52 km')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Despacho confirmado' })).toBeDisabled()
    expect(mocks.dispatch).toHaveBeenCalledWith(mocks.client, expect.objectContaining({ required_type: 'USA' }))
  })

  it.each([
    [404, 'Nenhuma viatura elegível está disponível.'],
    [409, 'Viatura não está disponível.'],
    [400, 'Latitude deve estar entre -90 e 90.'],
  ])('trata erro estruturado %s com mensagem segura', async (status, detail) => {
    mocks.dispatch.mockRejectedValue(new ApiError(status, undefined, { detail }))
    renderRoute(<DispatchPage />, '/missions/dispatch', '/missions/dispatch'); fillValid(); fireEvent.click(screen.getByRole('button', { name: 'Confirmar despacho' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(mocks.dispatch).toHaveBeenCalledOnce()
  })

  it('não repete despacho após falha de rede e sinaliza resultado indeterminado', async () => {
    mocks.dispatch.mockRejectedValue(new TypeError('network'))
    renderRoute(<DispatchPage />, '/missions/dispatch', '/missions/dispatch'); fillValid(); fireEvent.click(screen.getByRole('button', { name: 'Confirmar despacho' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Resultado indeterminado')
    expect(mocks.dispatch).toHaveBeenCalledOnce()
  })

  it('confirma conclusão, atualiza a missão e impede submissão duplicada', async () => {
    const active = { ...mission, status: 'Em Andamento' as const, assigned_unit: unit }
    let resolve!: (value: Mission) => void
    mocks.get.mockResolvedValue(active)
    mocks.history.mockResolvedValue({ count: 1, next: null, previous: null, results: [{ id: 1, status: 'Em Andamento', notes: null, timestamp: mission.created_at, actor: { id: 1, username: 'op', first_name: 'Ana', last_name: 'Lima' } }] })
    mocks.complete.mockReturnValue(new Promise<Mission>(done => { resolve = done }))
    renderRoute(<MissionDetailsPage />, '/missions/7', '/missions/:missionId')
    const trigger = await screen.findByRole('button', { name: 'Concluir missão' })
    fireEvent.click(trigger)
    const dialog = screen.getByRole('dialog', { name: 'Concluir missão?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    const confirm = screen.getByRole('button', { name: 'Confirmar conclusão' })
    expect(confirm).toHaveFocus()
    fireEvent.click(confirm); fireEvent.click(confirm)
    expect(mocks.complete).toHaveBeenCalledOnce()
    resolve({ ...active, status: 'Concluída', assigned_unit: { ...unit, status: 'AVAILABLE' } })
    expect(await screen.findByText('Missão concluída com sucesso.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Concluir missão' })).not.toBeInTheDocument()
    expect(screen.getByText('Operador: Ana Lima')).toBeInTheDocument()
  })

  it('cancela com motivo opcional e restaura foco ao fechar com Escape', async () => {
    mocks.get.mockResolvedValue(mission)
    mocks.history.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    mocks.cancel.mockResolvedValue({ ...mission, status: 'Cancelada' })
    renderRoute(<MissionDetailsPage />, '/missions/7', '/missions/:missionId')
    const trigger = await screen.findByRole('button', { name: 'Cancelar missão' })
    fireEvent.click(trigger)
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    await waitFor(() => expect(trigger).toHaveFocus())
    fireEvent.click(trigger)
    fireEvent.change(screen.getByLabelText(/Motivo do cancelamento/), { target: { value: '  Sem acesso  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar cancelamento' }))
    await waitFor(() => expect(mocks.cancel).toHaveBeenCalledWith(mocks.client, 7, '  Sem acesso  '))
    expect(await screen.findByText('Missão cancelada com sucesso.')).toBeInTheDocument()
  })

  it('preserva dados após conflito e oferece reconciliação', async () => {
    const active = { ...mission, status: 'Em Andamento' as const, assigned_unit: unit }
    mocks.get.mockResolvedValue(active)
    mocks.history.mockResolvedValue({ count: 0, next: null, previous: null, results: [] })
    mocks.complete.mockRejectedValue(new ApiError(409, undefined, { detail: 'Conflito' }))
    renderRoute(<MissionDetailsPage />, '/missions/7', '/missions/:missionId')
    fireEvent.click(await screen.findByRole('button', { name: 'Concluir missão' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar conclusão' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('alterada por outra operação')
    expect(screen.getByText('Atendimento urgente')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Atualizar dados/ }))
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2))
  })
})
