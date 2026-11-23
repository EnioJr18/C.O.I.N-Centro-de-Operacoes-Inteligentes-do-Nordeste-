import type { ApiClient } from './client'
import type { Coordinates, FleetUnit, FleetUnitHistory, FleetUnitPayload, Page } from './types'

const fleetPath = '/api/v1/fleet/units/'

export function validCoordinates(point: Coordinates | null): point is Coordinates {
  return !!point && typeof point.latitude === 'number' && Number.isFinite(point.latitude)
    && typeof point.longitude === 'number' && Number.isFinite(point.longitude)
    && Math.abs(point.latitude) <= 90 && Math.abs(point.longitude) <= 180
}

export async function loadFleet(client: ApiClient, signal?: AbortSignal): Promise<FleetUnit[]> {
  const all: FleetUnit[] = []
  const seen = new Set<string>()
  let path: string | null = fleetPath
  while (path) {
    if (seen.has(path) || seen.size >= 1000) throw new Error('Paginação inválida.')
    seen.add(path)
    const page: Page<FleetUnit> = await client.request<Page<FleetUnit>>(path, { signal })
    if (!page || !Array.isArray(page.results)) throw new Error('Resposta de frota inválida.')
    all.push(...page.results)
    if (!page.next) { path = null; continue }
    const next = new URL(page.next, window.location.origin)
    if (next.pathname !== fleetPath || next.username || next.password || next.hash) throw new Error('Paginação inválida.')
    path = next.pathname + next.search
  }
  return all
}

export function getFleetUnit(client: ApiClient, id: number, signal?: AbortSignal) {
  return client.request<FleetUnit>(`${fleetPath}${id}/`, { signal })
}

export function createFleetUnit(client: ApiClient, payload: FleetUnitPayload) {
  return client.request<FleetUnit>(fleetPath, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
}

export function updateFleetUnit(client: ApiClient, id: number, payload: Partial<FleetUnitPayload>) {
  return client.request<FleetUnit>(`${fleetPath}${id}/`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
}

export function startMaintenance(client: ApiClient, id: number) {
  return client.request<FleetUnit>(`${fleetPath}${id}/maintenance/`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
  })
}

export function endMaintenance(client: ApiClient, id: number) {
  return client.request<FleetUnit>(`${fleetPath}${id}/maintenance/`, {
    method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: '{}',
  })
}

export function getFleetUnitHistory(client: ApiClient, id: number, page = 1, signal?: AbortSignal) {
  const suffix = page > 1 ? `?page=${page}` : ''
  return client.request<Page<FleetUnitHistory>>(`${fleetPath}${id}/history/${suffix}`, { signal })
}
