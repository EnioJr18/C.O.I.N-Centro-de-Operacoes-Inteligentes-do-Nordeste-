import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api/client'
import { createMission, dispatchEmergency, getMissionHistory, localDateTimeToIso, missionListPath } from '../api/missions'

describe('API de missões', () => {
  it('serializa filtros reais, datas com fuso e paginação sem carregar todas as páginas', () => {
    const local = '2026-10-31T08:30'
    const iso = localDateTimeToIso(local)
    expect(iso).toBe(new Date(local).toISOString())
    expect(missionListPath({ status: 'Em Andamento', createdAfter: iso, createdBefore: '2026-10-31T15:00:00.000Z', page: 3 }))
      .toBe(`/api/v1/missions/?status=Em+Andamento&created_after=${encodeURIComponent(iso!)}&created_before=2026-10-31T15%3A00%3A00.000Z&page=3`)
    expect(localDateTimeToIso('')).toBeUndefined()
    expect(localDateTimeToIso('inválida')).toBeUndefined()
  })

  it('usa os contratos de histórico, criação e despacho', async () => {
    const request = vi.fn().mockResolvedValue({})
    const client = { request } as unknown as ApiClient
    await getMissionHistory(client, 9, 2)
    expect(request).toHaveBeenLastCalledWith('/api/v1/missions/9/history/?page=2', { signal: undefined })
    await createMission(client, { description: 'Ocorrência', location: { latitude: -9, longitude: -35 } })
    expect(request.mock.calls.at(-1)?.[0]).toBe('/api/v1/missions/')
    expect(JSON.parse(request.mock.calls.at(-1)?.[1].body as string)).toEqual({ description: 'Ocorrência', location: { latitude: -9, longitude: -35 } })
    await dispatchEmergency(client, { description: 'Urgência', location: { latitude: -9, longitude: -35 }, required_type: 'USA' })
    expect(request.mock.calls.at(-1)?.[0]).toBe('/api/v1/emergencies/dispatch/')
    expect(JSON.parse(request.mock.calls.at(-1)?.[1].body as string)).not.toHaveProperty('requirements')
  })
})
