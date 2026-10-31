import type { Tokens, User } from './types'

export type ApiErrorDetails = Record<string, unknown> | null

function safeValue(value: unknown, depth = 0): unknown {
  if (depth > 3) return null
  if (typeof value === 'string') return value.slice(0, 500)
  if (typeof value === 'number' || typeof value === 'boolean' || value === null) return value
  if (Array.isArray(value)) return value.slice(0, 20).map(item => safeValue(item, depth + 1))
  if (typeof value !== 'object') return null
  return Object.fromEntries(Object.entries(value).slice(0, 30).map(([key, item]) => [key, safeValue(item, depth + 1)]))
}

function safeDetails(value: unknown): ApiErrorDetails {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return safeValue(value) as Record<string, unknown>
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message = 'Não foi possível concluir a solicitação.',
    public readonly details: ApiErrorDetails = null,
  ) { super(message) }
}

async function parse(response: Response): Promise<unknown> {
  if (response.status === 204) return null
  try { return await response.json() as unknown } catch { return null }
}

export class ApiClient {
  private tokens: Tokens | null = null
  private renewal: Promise<string> | null = null
  private generation = 0
  constructor(private readonly onSessionLost: () => void) {}
  getAccess = () => this.tokens?.access ?? null
  clear = () => { this.generation++; this.tokens = null; this.renewal = null }

  async login(email: string, password: string): Promise<User> {
    const response = await fetch('/api/v1/auth/login/', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }), redirect: 'error',
    })
    const data = await parse(response)
    if (!response.ok) throw new ApiError(response.status, response.status === 401 ? 'E-mail ou senha inválidos.' : 'Não foi possível entrar. Tente novamente.')
    if (!data || typeof data !== 'object' || !('access' in data) || !('refresh' in data)
        || typeof data.access !== 'string' || typeof data.refresh !== 'string') throw new ApiError(0)
    const attempt = ++this.generation
    this.tokens = { access: data.access, refresh: data.refresh }
    try {
      const user = await this.request<User>('/api/v1/auth/me/')
      if (attempt !== this.generation) throw new ApiError(401)
      if (!user.is_active || (user.role !== 'ADMIN' && user.role !== 'OPERADOR')) throw new ApiError(403, 'Seu usuário não possui acesso às operações.')
      return user
    } catch (error) { if (attempt === this.generation) this.clear(); throw error }
  }

  refresh = async (): Promise<string> => {
    if (this.renewal) return this.renewal
    const refresh = this.tokens?.refresh
    const attempt = this.generation
    if (!refresh) throw new ApiError(401)
    const renewal = (async () => {
      try {
        const response = await fetch('/api/v1/auth/refresh/', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh }), redirect: 'error',
        })
        const data = await parse(response)
        if (!response.ok || !data || typeof data !== 'object' || !('access' in data) || typeof data.access !== 'string') throw new ApiError(401)
        if (attempt !== this.generation || !this.tokens) throw new ApiError(401)
        this.tokens = { ...this.tokens, access: data.access }
        return data.access
      } catch (error) {
        if (attempt === this.generation) { this.clear(); this.onSessionLost() }
        throw error
      }
    })()
    this.renewal = renewal
    try { return await renewal } finally { if (this.renewal === renewal) this.renewal = null }
  }

  async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    if (!path.startsWith('/api/')) throw new ApiError(0)
    const makeRequest = async (access: string) => {
      const headers = new Headers(options.headers)
      headers.set('Authorization', `Bearer ${access}`)
      return fetch(path, { ...options, headers, redirect: 'error' })
    }
    const access = this.getAccess()
    if (!access) throw new ApiError(401)
    const generation = this.generation
    let response = await makeRequest(access)
    if (response.status === 401) {
      const next = this.getAccess() !== access ? this.getAccess() : await this.refresh()
      if (!next || generation !== this.generation) throw new ApiError(401)
      response = await makeRequest(next)
      if (response.status === 401 && generation === this.generation) { this.clear(); this.onSessionLost() }
    }
    const data = await parse(response)
    if (!response.ok) throw new ApiError(response.status, undefined, safeDetails(data))
    return data as T
  }
}
