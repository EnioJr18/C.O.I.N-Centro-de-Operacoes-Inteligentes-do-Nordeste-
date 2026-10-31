import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { useState } from 'react'

const mocks = vi.hoisted(() => {
  const marker = { addTo: vi.fn(), remove: vi.fn(), setLatLng: vi.fn() }; marker.addTo.mockReturnValue(marker)
  const handlers: Record<string, (event: { latlng: { lat: number; lng: number } }) => void> = {}
  const map = { setView: vi.fn(), remove: vi.fn(), on: vi.fn((name: string, handler: typeof handlers[string]) => { handlers[name] = handler }) }; map.setView.mockReturnValue(map)
  return { marker, map, handlers, createMap: vi.fn(() => map), createMarker: vi.fn(() => marker), tileError: null as null | (() => void) }
})
vi.mock('leaflet', () => ({ default: {
  map: mocks.createMap,
  control: { zoom: () => ({ addTo: vi.fn() }) },
  tileLayer: () => ({ on: (_name: string, callback: () => void) => { mocks.tileError = callback; return { addTo: vi.fn() } } }),
  marker: mocks.createMarker,
  divIcon: vi.fn(() => ({})),
} }))
import { LocationPicker } from '../map/LocationPicker'

function ControlledPicker() {
  const [latitude, setLatitude] = useState('')
  const [longitude, setLongitude] = useState('')
  return <LocationPicker latitude={latitude} longitude={longitude} onChange={(lat, lon) => { setLatitude(lat); setLongitude(lon) }} />
}

beforeEach(() => { vi.clearAllMocks(); mocks.tileError = null; for (const key of Object.keys(mocks.handlers)) delete mocks.handlers[key] })

it('sincroniza clique no mapa e edição manual sem converter vazio em zero', () => {
  render(<ControlledPicker />)
  act(() => mocks.handlers.click({ latlng: { lat: -9.1234564, lng: -35.9876544 } }))
  expect(screen.getByLabelText('Latitude')).toHaveValue('-9.123456')
  expect(screen.getByLabelText('Longitude')).toHaveValue('-35.987654')
  expect(mocks.createMarker).toHaveBeenCalledWith([-9.123456, -35.987654], expect.anything())
  fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '' } })
  expect(screen.getByLabelText('Latitude')).toHaveValue('')
  expect(mocks.marker.remove).toHaveBeenCalled()
})

it('mantém os campos utilizáveis quando mapa ou tiles falham', () => {
  mocks.createMap.mockImplementationOnce(() => { throw new Error('mapa indisponível') })
  render(<ControlledPicker />)
  expect(screen.getByRole('status')).toHaveTextContent('coordenadas digitadas continuam válidas')
  fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '-9' } })
  fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '-35' } })
  expect(screen.getByLabelText('Latitude')).toHaveValue('-9')
  expect(screen.getByLabelText('Longitude')).toHaveValue('-35')
})

it('avisa sobre falha de tiles sem bloquear as coordenadas', () => {
  render(<ControlledPicker />)
  act(() => mocks.tileError?.())
  expect(screen.getByRole('status')).toHaveTextContent('coordenadas digitadas continuam válidas')
  expect(screen.getByLabelText('Latitude')).toBeEnabled()
})
