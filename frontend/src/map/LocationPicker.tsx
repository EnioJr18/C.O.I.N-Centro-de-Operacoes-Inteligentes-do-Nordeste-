import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'

function point(latitude: string, longitude: string): [number, number] | null {
  if (!latitude.trim() || !longitude.trim()) return null
  const lat = Number(latitude)
  const lon = Number(longitude)
  return Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? [lat, lon] : null
}

export function LocationPicker({ latitude, longitude, onChange, errors = {} }: {
  latitude: string
  longitude: string
  onChange: (latitude: string, longitude: string) => void
  errors?: { latitude?: string; longitude?: string }
}) {
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<L.Map | null>(null)
  const marker = useRef<L.Marker | null>(null)
  const change = useRef(onChange)
  const [mapUnavailable, setMapUnavailable] = useState(false)
  change.current = onChange

  useEffect(() => {
    if (!container.current) return
    let instance: L.Map | null = null
    try {
      instance = L.map(container.current, { zoomControl: false }).setView([-9.5, -36.8], 6)
      L.control.zoom({ position: 'bottomright' }).addTo(instance)
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      }).on('tileerror', () => setMapUnavailable(true)).addTo(instance)
      instance.on('click', event => change.current(String(Number(event.latlng.lat.toFixed(6))), String(Number(event.latlng.lng.toFixed(6)))))
      map.current = instance
    } catch {
      instance?.remove()
      setMapUnavailable(true)
    }
    return () => { marker.current?.remove(); marker.current = null; instance?.remove(); map.current = null }
  }, [])

  useEffect(() => {
    const instance = map.current
    const selected = point(latitude, longitude)
    if (!instance || !selected) { marker.current?.remove(); marker.current = null; return }
    if (!marker.current) {
      const icon = L.divIcon({ className: '', html: '<span class="location-marker">●</span>', iconSize: [30, 30], iconAnchor: [15, 15] })
      marker.current = L.marker(selected, { icon, keyboard: false }).addTo(instance)
    } else marker.current.setLatLng(selected)
  }, [latitude, longitude])

  return <div className="location-fieldset"><div className="coordinate-grid">
    <label>Latitude<input aria-invalid={!!errors.latitude} inputMode="decimal" value={latitude} onChange={event => onChange(event.target.value, longitude)} placeholder="-9.000000" />{errors.latitude && <span className="field-error">{errors.latitude}</span>}</label>
    <label>Longitude<input aria-invalid={!!errors.longitude} inputMode="decimal" value={longitude} onChange={event => onChange(latitude, event.target.value)} placeholder="-35.000000" />{errors.longitude && <span className="field-error">{errors.longitude}</span>}</label>
  </div><div className="location-map-wrap"><div ref={container} className="location-map" aria-label="Selecione a localização da ocorrência no mapa" />
    {mapUnavailable && <div className="location-map-warning" role="status">Mapa indisponível. As coordenadas digitadas continuam válidas.</div>}
  </div><small className="field-help">Clique no mapa ou informe as coordenadas diretamente.</small></div>
}
