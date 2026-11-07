import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api/client'
import { loadDashboardSummary } from '../api/dashboard'


describe('API do dashboard', () => {
  it('consulta somente o endpoint agregado com o sinal recebido', async () => {
    const request = vi.fn().mockResolvedValue({})
    const client = { request } as unknown as ApiClient
    const controller = new AbortController()

    await loadDashboardSummary(client, controller.signal)

    expect(request).toHaveBeenCalledOnce()
    expect(request).toHaveBeenCalledWith('/api/v1/dashboard/summary/', { signal: controller.signal })
  })
})
