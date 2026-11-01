import { describe, expect, it, vi } from 'vitest'
import type { ApiClient } from '../api/client'
import { changeCurrentPassword, updateCurrentUser } from '../api/profile'

describe('API do perfil', () => {
  it('usa o PATCH de me somente com nomes', async () => {
    const request = vi.fn().mockResolvedValue({})
    const client = { request } as unknown as ApiClient
    await updateCurrentUser(client, { first_name: 'Ana', last_name: 'Silva' })
    expect(request).toHaveBeenCalledWith('/api/v1/auth/me/', expect.objectContaining({ method: 'PATCH' }))
    expect(JSON.parse(request.mock.calls[0][1].body)).toEqual({ first_name: 'Ana', last_name: 'Silva' })
  })

  it('envia as três senhas somente ao endpoint dedicado', async () => {
    const request = vi.fn().mockResolvedValue(null)
    const client = { request } as unknown as ApiClient
    const payload = { current_password: 'CurrentPassword123', new_password: 'NewPassword123', new_password_confirmation: 'NewPassword123' }
    await changeCurrentPassword(client, payload)
    expect(request).toHaveBeenCalledWith('/api/v1/auth/me/password/', expect.objectContaining({ method: 'POST' }))
    expect(JSON.parse(request.mock.calls[0][1].body)).toEqual(payload)
  })
})
