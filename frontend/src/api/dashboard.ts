import type { ApiClient } from './client'
import type { DashboardSummary } from './types'


export function loadDashboardSummary(client: ApiClient, signal?: AbortSignal) {
  return client.request<DashboardSummary>('/api/v1/dashboard/summary/', { signal })
}
