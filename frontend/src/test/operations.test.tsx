import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { FleetUnit } from '../api/types'
import { MemoryRouter } from 'react-router-dom'

const mocks = vi.hoisted(() => ({ load: vi.fn(), client: {}, socket: { options: null as unknown, stop: vi.fn() }, logout: vi.fn() }))
vi.mock('../auth/AuthContext', () => ({ useAuth: () => ({ client: mocks.client, user: { username: 'op', role: 'OPERADOR' }, logout: mocks.logout }) }))
vi.mock('../api/fleet', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/fleet')>()
  return { ...actual, loadFleet: mocks.load }
})
vi.mock('../realtime/fleetSocket', () => ({ FleetSocket: class {
  constructor(options: unknown) { mocks.socket.options = options }
  start() {}
  stop() { mocks.socket.stop() }
} }))
vi.mock('../map/FleetMap', () => ({ FleetMap: ({ units, selected, onSelect }: { units: FleetUnit[]; selected: number | null; onSelect: (id: number) => void }) => <div data-testid="map"><span>Selecionada: {selected ?? 'nenhuma'}</span>{units.map(unit => <button key={unit.id} onClick={() => onSelect(unit.id)}>Mapa: {unit.name} {unit.current_location?.latitude ?? 'sem posição'}</button>)}</div> }))
import { OperationsPage } from '../fleet/OperationsPage'
const renderOperations = () => render(<MemoryRouter><OperationsPage /></MemoryRouter>)

const units: FleetUnit[] = [
  { id: 1, name: 'Alfa 01', license_plate: 'AAA-1234', unit_type: 'USB', status: 'AVAILABLE', current_location: { latitude: -9, longitude: -35 }, capabilities: {}, created_at: '', updated_at: '' },
  { id: 2, name: 'Bravo 02', license_plate: 'BBB-1234', unit_type: 'USA', status: 'MAINTENANCE', current_location: null, capabilities: {}, created_at: '', updated_at: '' },
]
beforeEach(() => { mocks.load.mockReset(); mocks.socket.stop.mockClear(); mocks.logout.mockClear() })

describe('área operacional', () => {
  it('mostra frota e sincroniza seleção entre lista e mapa', async () => {
    mocks.load.mockResolvedValue(units)
    const view = renderOperations()
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
    await screen.findByText('Alfa 01')
    expect(screen.getByText('Sem localização')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Alfa 01/, pressed: false }))
    expect(screen.getByText('Selecionada: 1')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Mapa: Bravo 02/ }))
    expect(screen.getByText('Selecionada: 2')).toBeInTheDocument()
    expect(screen.getByText('Localização indisponível')).toBeInTheDocument()
    view.unmount()
    expect(mocks.socket.stop).toHaveBeenCalledOnce()
  })

  it('aplica status do despacho sem mover a unidade para a ocorrência e reconcilia na conexão', async () => {
    mocks.load.mockResolvedValueOnce(units).mockImplementation(() => new Promise(() => {}))
    renderOperations()
    await screen.findByText('Alfa 01')
    const options = mocks.socket.options as { onEvent: (event: unknown) => void; onConnected: () => void }
    act(() => options.onEvent({ unit_id: 1, new_status: 'BUSY', lat: -7, lon: -38 }))
    expect(screen.getByRole('button', { name: /Alfa 01/, pressed: false })).toHaveTextContent('Em atendimento')
    expect(screen.getByRole('button', { name: /Mapa: Alfa 01/ })).toHaveTextContent('-9')
    act(() => options.onConnected())
    await waitFor(() => expect(mocks.load).toHaveBeenCalledTimes(3))
  })

  it('apresenta vazio e erro com tentativa de recuperação', async () => {
    mocks.load.mockRejectedValueOnce(new Error()).mockResolvedValueOnce([])
    renderOperations()
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível carregar a frota')
    fireEvent.click(screen.getByRole('button', { name: /Tentar novamente/ }))
    expect(await screen.findByText('Nenhuma viatura cadastrada.')).toBeInTheDocument()
  })
})
