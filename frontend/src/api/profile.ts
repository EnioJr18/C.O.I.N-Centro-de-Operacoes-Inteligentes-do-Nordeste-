import type { ApiClient } from './client'
import type { User } from './types'

export interface ProfilePayload { first_name: string; last_name: string }
export interface PasswordPayload { current_password: string; new_password: string; new_password_confirmation: string }

export function updateCurrentUser(client: ApiClient, payload: ProfilePayload) {
  return client.request<User>('/api/v1/auth/me/', {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
}

export function changeCurrentPassword(client: ApiClient, payload: PasswordPayload) {
  return client.request<null>('/api/v1/auth/me/password/', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })
}
