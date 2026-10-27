import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, ApiError } from '../api/client'
import { loadFleet, validCoordinates } from '../api/fleet'
import type { FleetUnit } from '../api/types'

const user = { id: 1, username: 'operador', first_name: '', last_name: '', email: 'op@example.com', is_active: true, role: 'OPERADOR' }
const reply = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const unit = (id: number): FleetUnit => ({ id, name: `Unidade ${id}`, license_plate: 'AAA-1234', unit_type: 'USB', status: 'AVAILABLE', current_location: { latitude: -9, longitude: -35 }, capabilities: {}, created_at: '', updated_at: '' })
afterEach(() => vi.unstubAllGlobals())

describe('sessão e cliente HTTP', () => {
  it('autentica com e-mail, consulta me e não envia Bearer no login', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(reply({ access: 'access', refresh: 'refresh' })).mockResolvedValueOnce(reply(user))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient(vi.fn())
    expect(await client.login('op@example.com', 'password')).toEqual(user)
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/auth/login/')
    expect(new Headers(fetcher.mock.calls[0][1].headers).has('Authorization')).toBe(false)
    expect(new Headers(fetcher.mock.calls[1][1].headers).get('Authorization')).toBe('Bearer access')
  })

  it('rejeita credenciais inválidas e papel sem autorização', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(reply({ detail: 'invalid' }, 401))
      .mockResolvedValueOnce(reply({ access: 'a', refresh: 'r' })).mockResolvedValueOnce(reply({ ...user, role: null }))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient(vi.fn())
    await expect(client.login('x@example.com', 'bad')).rejects.toMatchObject({ status: 401 })
    await expect(client.login('x@example.com', 'ok')).rejects.toMatchObject({ status: 403 })
    expect(client.getAccess()).toBeNull()
  })

  it('compartilha uma renovação para 401 simultâneos e repete cada pedido uma vez', async () => {
    let resolveRefresh!: (value: Response) => void
    const refresh = new Promise<Response>(resolve => { resolveRefresh = resolve })
    const fetcher = vi.fn(async (path: string, options: RequestInit) => {
      if (path.endsWith('/login/')) return reply({ access: 'old', refresh: 'refresh' })
      if (path.endsWith('/me/')) return reply(user)
      if (path.endsWith('/refresh/')) return refresh
      return new Headers(options.headers).get('Authorization') === 'Bearer old' ? reply({}, 401) : reply({ ok: true })
    })
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient(vi.fn())
    await client.login('op@example.com', 'password')
    const first = client.request('/api/one/')
    const second = client.request('/api/two/')
    await vi.waitFor(() => expect(fetcher.mock.calls.filter(([path]) => path.endsWith('/refresh/'))).toHaveLength(1))
    resolveRefresh(reply({ access: 'new' }))
    await expect(Promise.all([first, second])).resolves.toEqual([{ ok: true }, { ok: true }])
    expect(fetcher.mock.calls.filter(([path]) => path === '/api/one/')).toHaveLength(2)
    expect(fetcher.mock.calls.filter(([path]) => path === '/api/two/')).toHaveLength(2)
  })

  it('não renova em 403 e encerra sessão após segunda resposta 401', async () => {
    const lost = vi.fn()
    const fetcher = vi.fn().mockResolvedValueOnce(reply({ access: 'a', refresh: 'r' })).mockResolvedValueOnce(reply(user))
      .mockResolvedValueOnce(reply({}, 403)).mockResolvedValueOnce(reply({}, 401))
      .mockResolvedValueOnce(reply({ access: 'b' })).mockResolvedValueOnce(reply({}, 401))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient(lost)
    await client.login('op@example.com', 'password')
    await expect(client.request('/api/denied/')).rejects.toBeInstanceOf(ApiError)
    expect(fetcher.mock.calls.filter(([path]) => path.endsWith('/refresh/'))).toHaveLength(0)
    await expect(client.request('/api/protected/')).rejects.toMatchObject({ status: 401 })
    expect(fetcher.mock.calls.filter(([path]) => path === '/api/protected/')).toHaveLength(2)
    expect(lost).toHaveBeenCalledOnce()
    expect(client.getAccess()).toBeNull()
  })

  it('limpa a sessão em erro de refresh e no logout local', async () => {
    const lost = vi.fn()
    const fetcher = vi.fn().mockResolvedValueOnce(reply({ access: 'a', refresh: 'r' })).mockResolvedValueOnce(reply(user)).mockResolvedValueOnce(reply({}, 401))
    vi.stubGlobal('fetch', fetcher)
    const client = new ApiClient(lost)
    await client.login('op@example.com', 'password')
    await expect(client.refresh()).rejects.toBeDefined()
    expect(lost).toHaveBeenCalledOnce()
    expect(client.getAccess()).toBeNull()
    client.clear()
    expect(client.getAccess()).toBeNull()
  })
})

describe('frota', () => {
  it('lê mais de 20 unidades e reconstrói next na origem confiável', async () => {
    const request = vi.fn().mockResolvedValueOnce({ count: 21, next: 'https://untrusted.example/api/v1/fleet/units/?page=2', previous: null, results: Array.from({ length: 20 }, (_, i) => unit(i + 1)) })
      .mockResolvedValueOnce({ count: 21, next: null, previous: null, results: [unit(21)] })
    const result = await loadFleet({ request } as unknown as ApiClient)
    expect(result).toHaveLength(21)
    expect(request.mock.calls[1][0]).toBe('/api/v1/fleet/units/?page=2')
    expect(request.mock.calls.every(([path]) => !path.includes('untrusted.example'))).toBe(true)
  })
  it('recusa paginação para um caminho inesperado e valida coordenadas', async () => {
    const request = vi.fn().mockResolvedValue({ next: 'https://untrusted.example/api/admin/', results: [] })
    await expect(loadFleet({ request } as unknown as ApiClient)).rejects.toThrow('Paginação inválida.')
    expect(validCoordinates({ latitude: -9, longitude: -35 })).toBe(true)
    expect(validCoordinates(null)).toBe(false)
    expect(validCoordinates({ latitude: 91, longitude: -35 })).toBe(false)
    expect(validCoordinates({ latitude: NaN, longitude: -35 })).toBe(false)
  })
})
