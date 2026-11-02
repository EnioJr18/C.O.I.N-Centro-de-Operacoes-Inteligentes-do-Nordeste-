import type { ApiClient } from './client'
import type { ManagedUser, Page, Role } from './types'

export interface UserFilters {
  page?: number
  search?: string
  role?: Exclude<Role, null>
  isActive?: boolean
  ordering?: 'date_joined' | '-date_joined' | 'username' | '-username' | 'first_name' | '-first_name' | 'last_name' | '-last_name'
}
export interface CreateUserPayload { username: string; email: string; first_name: string; last_name: string; password: string }
export interface UpdateUserPayload { first_name?: string; last_name?: string }

export function userListPath(filters: UserFilters = {}) {
  const params = new URLSearchParams()
  if (filters.search) params.set('search', filters.search)
  if (filters.role) params.set('role', filters.role)
  if (filters.isActive !== undefined) params.set('is_active', String(filters.isActive))
  if (filters.ordering) params.set('ordering', filters.ordering)
  if (filters.page && filters.page > 1) params.set('page', String(filters.page))
  const query = params.toString()
  return `/api/v1/auth/users/${query ? `?${query}` : ''}`
}

export function listUsers(client: ApiClient, filters: UserFilters, signal?: AbortSignal) {
  return client.request<Page<ManagedUser>>(userListPath(filters), { signal })
}
export function getUser(client: ApiClient, id: number) {
  return client.request<ManagedUser>(`/api/v1/auth/users/${id}/`)
}
export function createUser(client: ApiClient, payload: CreateUserPayload) {
  return client.request<ManagedUser>('/api/v1/auth/users/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
}
export function updateUser(client: ApiClient, id: number, payload: UpdateUserPayload) {
  return client.request<ManagedUser>(`/api/v1/auth/users/${id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
}
export function updateUserRole(client: ApiClient, id: number, role: Exclude<Role, null>) {
  return client.request<ManagedUser>(`/api/v1/auth/users/${id}/role/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role }) })
}
export function activateUser(client: ApiClient, id: number) {
  return client.request<ManagedUser>(`/api/v1/auth/users/${id}/activate/`, { method: 'POST' })
}
export function deactivateUser(client: ApiClient, id: number) {
  return client.request<ManagedUser>(`/api/v1/auth/users/${id}/deactivate/`, { method: 'POST' })
}
