import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api/client'
import {
  createFleetUnit, endMaintenance, getFleetUnitHistory,
  startMaintenance, updateFleetUnit,
} from '../api/fleet'

describe('API administrativa da frota', () => {
  it('usa os métodos e contratos versionados esperados', async () => {
    const request = vi.fn(async () => ({}))
    const client = { request } as unknown as ApiClient
    const payload = { name: 'Alfa', license_plate: 'AAA-0001', unit_type: 'USB' as const, capabilities: {} }
    await createFleetUnit(client, payload)
    await updateFleetUnit(client, 7, { name: 'Bravo' })
    await startMaintenance(client, 7)
    await endMaintenance(client, 7)
    await getFleetUnitHistory(client, 7, 2)
    expect(request).toHaveBeenNthCalledWith(1, '/api/v1/fleet/units/', expect.objectContaining({ method: 'POST' }))
    expect(request).toHaveBeenNthCalledWith(2, '/api/v1/fleet/units/7/', expect.objectContaining({ method: 'PATCH' }))
    expect(request).toHaveBeenNthCalledWith(3, '/api/v1/fleet/units/7/maintenance/', expect.objectContaining({ method: 'POST' }))
    expect(request).toHaveBeenNthCalledWith(4, '/api/v1/fleet/units/7/maintenance/', expect.objectContaining({ method: 'DELETE' }))
    expect(request).toHaveBeenNthCalledWith(5, '/api/v1/fleet/units/7/history/?page=2', expect.any(Object))
  })
})
