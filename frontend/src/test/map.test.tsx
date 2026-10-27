import { render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import type { FleetUnit } from '../api/types'

const mocks = vi.hoisted(() => {
  const marker = { addTo: vi.fn(), on: vi.fn(), remove: vi.fn(), setLatLng: vi.fn(), setIcon: vi.fn(), getElement: vi.fn(() => null) }
  marker.addTo.mockReturnValue(marker)
  const map = { setView: vi.fn(), fitBounds: vi.fn(), remove: vi.fn() }
  map.setView.mockReturnValue(map)
  return { marker, map, createMap: vi.fn(() => map), createMarker: vi.fn(() => marker) }
})
vi.mock('leaflet', () => ({ default: {
  map: mocks.createMap,
  control: { zoom: () => ({ addTo: vi.fn() }) },
  tileLayer: () => ({ on: () => ({ addTo: vi.fn() }) }),
  marker: mocks.createMarker,
  divIcon: vi.fn(() => ({})),
  latLngBounds: vi.fn(points => points),
} }))
import { FleetMap } from '../map/FleetMap'

const base: FleetUnit = { id: 1, name: 'Alfa', license_plate: 'AAA', unit_type: 'USB', status: 'AVAILABLE', current_location: { latitude: -9, longitude: -35 }, capabilities: {}, created_at: '', updated_at: '' }
beforeEach(() => { vi.clearAllMocks() })

it('cria marcadores apenas para coordenadas válidas e mantém a posição ao mudar status', () => {
  const units = [base, { ...base, id: 2, current_location: null }, { ...base, id: 3, current_location: { latitude: 91, longitude: -35 } }]
  const view = render(<FleetMap units={units} selected={null} onSelect={vi.fn()} />)
  expect(mocks.createMarker).toHaveBeenCalledTimes(1)
  expect(mocks.createMarker).toHaveBeenCalledWith([-9, -35], expect.anything())
  view.rerender(<FleetMap units={[{ ...base, status: 'BUSY' }]} selected={1} onSelect={vi.fn()} />)
  expect(mocks.marker.setLatLng).toHaveBeenLastCalledWith([-9, -35])
  expect(mocks.marker.setIcon).toHaveBeenCalled()
  view.unmount()
  expect(mocks.map.remove).toHaveBeenCalledOnce()
})

it('mostra falha do mapa sem ocultar a lista operacional', () => {
  mocks.createMap.mockImplementationOnce(() => { throw new Error('Mapa indisponível') })
  render(<><FleetMap units={[]} selected={null} onSelect={vi.fn()} /><div>Lista de unidades</div></>)
  expect(screen.getByRole('status')).toHaveTextContent('Mapa indisponível')
  expect(screen.getByText('Lista de unidades')).toBeInTheDocument()
})
