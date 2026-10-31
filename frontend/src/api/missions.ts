import type { ApiClient } from './client'
import type { DispatchPayload, DispatchResult, Mission, MissionHistory, MissionPayload, MissionStatus, Page } from './types'

export interface MissionFilters {
  status?: MissionStatus
  createdAfter?: string
  createdBefore?: string
  page?: number
}

export function localDateTimeToIso(value: string): string | undefined {
  if (!value) return undefined
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString()
}

export function missionListPath(filters: MissionFilters = {}): string {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.createdAfter) params.set('created_after', filters.createdAfter)
  if (filters.createdBefore) params.set('created_before', filters.createdBefore)
  if (filters.page && filters.page > 1) params.set('page', String(filters.page))
  const query = params.toString()
  return `/api/v1/missions/${query ? `?${query}` : ''}`
}

export function listMissions(client: ApiClient, filters: MissionFilters = {}, signal?: AbortSignal) {
  return client.request<Page<Mission>>(missionListPath(filters), { signal })
}

export function getMission(client: ApiClient, id: number, signal?: AbortSignal) {
  return client.request<Mission>(`/api/v1/missions/${id}/`, { signal })
}

export function getMissionHistory(client: ApiClient, id: number, page = 1, signal?: AbortSignal) {
  const suffix = page > 1 ? `?page=${page}` : ''
  return client.request<Page<MissionHistory>>(`/api/v1/missions/${id}/history/${suffix}`, { signal })
}

export function createMission(client: ApiClient, payload: MissionPayload) {
  return client.request<Mission>('/api/v1/missions/', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
}

export function dispatchEmergency(client: ApiClient, payload: DispatchPayload) {
  return client.request<DispatchResult>('/api/v1/emergencies/dispatch/', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
}
