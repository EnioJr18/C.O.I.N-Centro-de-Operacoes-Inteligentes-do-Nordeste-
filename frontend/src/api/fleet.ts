import type { ApiClient } from './client'
import type { Coordinates, FleetUnit, Page } from './types'

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
