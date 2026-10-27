import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api/client'
import { FleetSocket, parseDispatchEvent } from '../realtime/fleetSocket'

class FakeSocket {
  static instances: FakeSocket[] = []
  protocol = 'coin.v1'
  onopen: (() => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  close = vi.fn()
  constructor(public url: string, public protocols: string[]) { FakeSocket.instances.push(this) }
}
const event = { event_id: 'event-1', schema_version: 1, occurred_at: '2026-10-27T12:30:00Z', action: 'DISPATCH', unit_id: 7, unit_name: 'Alfa', new_status: 'BUSY', mission_id: 3, lat: -9, lon: -35 }
function setup() {
  FakeSocket.instances = []
  vi.stubGlobal('WebSocket', FakeSocket)
  const client = { getAccess: vi.fn(() => 'access-token'), refresh: vi.fn(async () => 'new-token') } as unknown as ApiClient
  const options = { client, onState: vi.fn(), onEvent: vi.fn(), onConnected: vi.fn(), onForbidden: vi.fn() }
  const socket = new FleetSocket(options)
  socket.start()
  return { socket, options }
}
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('WebSocket da frota', () => {
  it('abre com protocolos corretos, sem token na URL ou logs; valida e deduplica eventos', () => {
    const log = vi.spyOn(console, 'log')
    const error = vi.spyOn(console, 'error')
    const { socket, options } = setup()
    const ws = FakeSocket.instances[0]
    expect(ws.url).toContain('/ws/fleet/')
    expect(ws.url).not.toContain('access-token')
    expect(ws.protocols).toEqual(['coin.v1', 'coin.jwt.access-token'])
    ws.onopen?.()
    ws.onmessage?.({ data: JSON.stringify(event) })
    ws.onmessage?.({ data: JSON.stringify(event) })
    ws.onmessage?.({ data: JSON.stringify({ ...event, schema_version: 2, event_id: 'other' }) })
    ws.onmessage?.({ data: '{' })
    expect(options.onEvent).toHaveBeenCalledOnce()
    expect(options.onConnected).toHaveBeenCalledOnce()
    expect(log).not.toHaveBeenCalled()
    expect(error).not.toHaveBeenCalled()
    socket.stop()
    expect(ws.close).toHaveBeenCalledOnce()
  })

  it('renova uma vez após expiração e encerra ao receber revogação', async () => {
    const { socket, options } = setup()
    FakeSocket.instances[0].onopen?.()
    FakeSocket.instances[0].onclose?.({ code: 4401 })
    await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(2))
    expect(options.client.refresh).toHaveBeenCalledOnce()
    FakeSocket.instances[1].onopen?.()
    expect(options.onConnected).toHaveBeenCalledTimes(2)
    FakeSocket.instances[1].onclose?.({ code: 4403 })
    expect(options.onForbidden).toHaveBeenCalledOnce()
    socket.stop()
  })

  it('reconecta com backoff e cancela temporizador no encerramento', async () => {
    vi.useFakeTimers()
    vi.spyOn(Math, 'random').mockReturnValue(0.5)
    const { socket, options } = setup()
    FakeSocket.instances[0].onclose?.({ code: 1006 })
    expect(options.onState).toHaveBeenLastCalledWith('reconnecting')
    await vi.advanceTimersByTimeAsync(999)
    expect(FakeSocket.instances).toHaveLength(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(FakeSocket.instances).toHaveLength(2)
    FakeSocket.instances[1].onopen?.()
    expect(options.onConnected).toHaveBeenCalledOnce()
    FakeSocket.instances[1].onclose?.({ code: 1011 })
    socket.stop()
    await vi.advanceTimersByTimeAsync(10000)
    expect(FakeSocket.instances).toHaveLength(2)
  })

  it('rejeita eventos inválidos e status desconhecidos', () => {
    expect(parseDispatchEvent(JSON.stringify({ ...event, new_status: 'UNKNOWN' }))).toBeNull()
    expect(parseDispatchEvent(JSON.stringify({ ...event, lat: 91 }))).toBeNull()
    expect(parseDispatchEvent(JSON.stringify({ ...event, schema_version: 2 }))).toBeNull()
  })

  it('não aceita protocolo negociado incorreto e limita expirações consecutivas', async () => {
    const { socket, options } = setup()
    const first = FakeSocket.instances[0]
    first.protocol = 'unexpected'
    first.onopen?.()
    expect(first.close).toHaveBeenCalledWith(1002)
    first.onclose?.({ code: 4401 })
    await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(2))
    FakeSocket.instances[1].onopen?.()
    FakeSocket.instances[1].onclose?.({ code: 4401 })
    expect(options.onForbidden).toHaveBeenCalledOnce()
    expect(options.client.refresh).toHaveBeenCalledOnce()
    socket.stop()
  })
})
