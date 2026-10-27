import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import type { FleetUnit, UnitStatus } from '../api/types'
import { validCoordinates } from '../api/fleet'

const symbols: Record<UnitStatus, string> = { AVAILABLE: '+', BUSY: '●', MAINTENANCE: '×' }
function markerIcon(status: UnitStatus, selected: boolean) {
  const safeStatus: UnitStatus = Object.hasOwn(symbols, status) ? status : 'MAINTENANCE'
  return L.divIcon({ className: '', html: `<span class="map-marker marker-${safeStatus.toLowerCase()}${selected ? ' selected' : ''}">${symbols[safeStatus]}</span>`, iconSize: [34, 34], iconAnchor: [17, 17] })
}

export function FleetMap({ units, selected, onSelect, loading = false, hasError = false }: { units: FleetUnit[]; selected: number | null; onSelect: (id: number) => void; loading?: boolean; hasError?: boolean }) {
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const [mapError, setMapError] = useState(false)
  const markers = useRef(new Map<number, L.Marker>())
  const select = useRef(onSelect)
  const fittedIds = useRef('')
  select.current = onSelect

  useEffect(() => {
    if (!container.current) return
    let instance: L.Map | null = null
    try {
      instance = L.map(container.current, { zoomControl: false }).setView([-9.5, -36.8], 6)
      L.control.zoom({ position: 'bottomright' }).addTo(instance)
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).on('tileerror', () => setMapError(true)).addTo(instance)
      map.current = instance
    } catch {
      instance?.remove()
      instance = null
      setMapError(true)
    }
    return () => { instance?.remove(); map.current = null; markers.current.clear(); fittedIds.current = '' }
  }, [])

  useEffect(() => {
    const instance = map.current
    if (!instance) return
    const visible = units.filter(unit => validCoordinates(unit.current_location))
    const ids = new Set(visible.map(unit => unit.id))
    for (const [id, marker] of markers.current) if (!ids.has(id)) { marker.remove(); markers.current.delete(id) }
    const points: L.LatLngExpression[] = []
    for (const unit of visible) {
      const location = unit.current_location!
      const point: L.LatLngExpression = [location.latitude, location.longitude]
      points.push(point)
      let marker = markers.current.get(unit.id)
      if (!marker) {
        marker = L.marker(point, { icon: markerIcon(unit.status, selected === unit.id), title: unit.name, keyboard: true }).addTo(instance)
        marker.on('click', () => select.current(unit.id))
        markers.current.set(unit.id, marker)
      } else {
        marker.setLatLng(point)
        marker.setIcon(markerIcon(unit.status, selected === unit.id))
        marker.getElement()?.setAttribute('title', unit.name)
      }
    }
    const idsKey = [...ids].sort((a, b) => a - b).join(',')
    if (idsKey !== fittedIds.current && points.length) {
      if (points.length === 1) instance.setView(points[0], 13)
      else instance.fitBounds(L.latLngBounds(points), { padding: [35, 35], maxZoom: 13 })
    } else if (!points.length && fittedIds.current) {
      instance.setView([-9.5, -36.8], 6)
    }
    fittedIds.current = idsKey
  }, [units, selected])

  const located = units.filter(unit => validCoordinates(unit.current_location)).length
  return <div className="map-wrap"><div ref={container} className="map-canvas" aria-label="Mapa interativo das viaturas" />
    {mapError && <div className="map-empty" role="status">Mapa indisponível ou incompleto. A lista de unidades continua disponível.</div>}
    {!mapError && located === 0 && <div className="map-empty">{loading ? 'Carregando localizações...' : hasError ? 'Não foi possível carregar as localizações.' : 'Nenhuma viatura com localização disponível.'}</div>}
    <div className="map-key" aria-label="Legenda do mapa"><span><b className="key-dot available" /> Disponível</span><span><b className="key-dot busy" /> Em atendimento</span><span><b className="key-dot maintenance" /> Manutenção</span></div>
  </div>
}
