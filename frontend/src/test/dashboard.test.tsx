import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import type { DashboardSummary } from '../api/types'


const mocks = vi.hoisted(() => ({
  client: {},
  load: vi.fn(),
  logout: vi.fn(),
  socket: { options: null as unknown, stop: vi.fn() },
}))
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ client: mocks.client, logout: mocks.logout, user: { role: 'OPERADOR' } }) }))
vi.mock('../api/dashboard', () => ({ loadDashboardSummary: mocks.load }))
vi.mock('../realtime/fleetSocket', () => ({ FleetSocket: class {
  constructor(options: unknown) { mocks.socket.options = options }
  start() {}
  stop() { mocks.socket.stop() }
} }))

import { OverviewPage } from '../dashboard/OverviewPage'


const summary: DashboardSummary = {
  generated_at: '2026-11-02T23:00:00Z',
  fleet: {
    total: 6, available: 2, availability_percentage: 33.3, with_location: 4, without_location: 2,
    by_status: { AVAILABLE: 2, BUSY: 3, MAINTENANCE: 1 },
  },
  missions: {
    total: 9,
    by_status: { Pendente: 2, 'Em Andamento': 3, Concluída: 3, Cancelada: 1 },
    recent: [
      { id: 9, description: 'Atendimento urgente', status: 'Em Andamento', created_at: '2026-11-02T22:50:00Z', assigned_unit: { id: 3, name: 'Alfa 03' } },
      { id: 8, description: 'Vistoria preventiva', status: 'Pendente', created_at: '2026-11-02T21:50:00Z', assigned_unit: null },
    ],
  },
}
const renderDashboard = () => render(<MemoryRouter><OverviewPage /></MemoryRouter>)


beforeEach(() => {
  mocks.load.mockReset()
  mocks.logout.mockClear()
  mocks.socket.stop.mockClear()
  mocks.socket.options = null
})


describe('dashboard operacional', () => {
  it('renderiza indicadores, distribuição, localização e missões recentes', async () => {
    mocks.load.mockResolvedValue(summary)
    const view = renderDashboard()

    expect(screen.getByText('Carregando indicadores operacionais...')).toBeInTheDocument()
    expect(await screen.findByText('Atendimento urgente')).toBeInTheDocument()
    expect(screen.getByText('33.3% da frota por status')).toBeInTheDocument()
    expect(screen.getByText('Com localização').previousSibling).toHaveTextContent('4')
    expect(screen.getByText('Sem localização').previousSibling).toHaveTextContent('2')
    expect(screen.getByRole('img', { name: 'Disponíveis: 2 de 6' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Atendimento urgente/ })).toHaveAttribute('href', '/missions/9')
    expect(screen.getByText('Alfa 03')).toBeInTheDocument()
    expect(screen.getByText('Sem unidade atribuída')).toBeInTheDocument()
    expect(screen.getByText(/Atualizado em/)).toBeInTheDocument()
    expect(mocks.load).toHaveBeenCalledOnce()
    view.unmount()
    expect(mocks.socket.stop).toHaveBeenCalledOnce()
  })

  it('apresenta erro inicial, retry e estados vazios completos', async () => {
    const empty: DashboardSummary = {
      ...summary,
      fleet: { total: 0, available: 0, availability_percentage: 0, with_location: 0, without_location: 0, by_status: { AVAILABLE: 0, BUSY: 0, MAINTENANCE: 0 } },
      missions: { total: 0, by_status: { Pendente: 0, 'Em Andamento': 0, Concluída: 0, Cancelada: 0 }, recent: [] },
    }
    mocks.load.mockRejectedValueOnce(new Error()).mockResolvedValueOnce(empty)
    renderDashboard()

    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível carregar o resumo operacional')
    fireEvent.click(screen.getByRole('button', { name: /Tentar novamente/ }))
    expect(await screen.findByText('Nenhuma unidade cadastrada.')).toBeInTheDocument()
    expect(screen.getByText('Nenhuma missão registrada.')).toBeInTheDocument()
    expect(screen.getByText('0.0% da frota por status')).toBeInTheDocument()
  })

  it('preserva dados válidos durante atualização manual e após falha', async () => {
    let rejectRefresh: (reason?: unknown) => void = () => undefined
    const refresh = new Promise<DashboardSummary>((_, reject) => { rejectRefresh = reject })
    mocks.load.mockResolvedValueOnce(summary).mockReturnValueOnce(refresh)
    renderDashboard()
    await screen.findByText('Atendimento urgente')

    fireEvent.click(screen.getByRole('button', { name: 'Atualizar dados' }))
    expect(screen.getByRole('button', { name: 'Atualizando…' })).toBeDisabled()
    expect(screen.getByText('Atendimento urgente')).toBeInTheDocument()
    await act(async () => rejectRefresh(new Error('offline')))
    expect(await screen.findByRole('alert')).toHaveTextContent('últimos dados válidos continuam visíveis')
    expect(screen.getByText('Atendimento urgente')).toBeInTheDocument()
  })

  it('recarrega após DISPATCH e reconexão, sem recarga na primeira conexão', async () => {
    mocks.load.mockResolvedValue(summary)
    renderDashboard()
    await screen.findByText('Atendimento urgente')
    const options = mocks.socket.options as { onEvent: () => void; onConnected: () => void }

    act(() => options.onConnected())
    expect(mocks.load).toHaveBeenCalledOnce()
    act(() => options.onEvent())
    await waitFor(() => expect(mocks.load).toHaveBeenCalledTimes(2))
    act(() => options.onConnected())
    await waitFor(() => expect(mocks.load).toHaveBeenCalledTimes(3))
  })
})
