import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api/client'
import { activateUser, createUser, deactivateUser, updateUser, updateUserRole, userListPath } from '../api/users'

describe('API administrativa de usuários', () => {
  it('serializa somente filtros suportados', () => {
    expect(userListPath({ search: 'Ana', role: 'OPERADOR', isActive: false, ordering: 'username', page: 2 }))
      .toBe('/api/v1/auth/users/?search=Ana&role=OPERADOR&is_active=false&ordering=username&page=2')
  })

  it('usa os contratos de criação, edição, papel e estado', async () => {
    const request = vi.fn().mockResolvedValue({})
    const client = { request } as unknown as ApiClient
    const payload = { username: 'ana', email: 'ana@example.com', first_name: 'Ana', last_name: 'Silva', password: 'Password123' }
    await createUser(client, payload)
    await updateUser(client, 7, { first_name: 'Beatriz' })
    await updateUserRole(client, 7, 'ADMIN')
    await activateUser(client, 7)
    await deactivateUser(client, 7)
    expect(JSON.parse(request.mock.calls[0][1].body)).toEqual(payload)
    expect(request.mock.calls.map(([path, options]) => [path, options?.method])).toEqual([
      ['/api/v1/auth/users/', 'POST'], ['/api/v1/auth/users/7/', 'PATCH'],
      ['/api/v1/auth/users/7/role/', 'PATCH'], ['/api/v1/auth/users/7/activate/', 'POST'],
      ['/api/v1/auth/users/7/deactivate/', 'POST'],
    ])
  })
})
