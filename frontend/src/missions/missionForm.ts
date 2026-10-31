import { ApiError } from '../api/client'
import type { MissionPayload } from '../api/types'

export interface MissionFormErrors { description?: string; latitude?: string; longitude?: string }

function coordinate(value: string, minimum: number, maximum: number): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= minimum && parsed <= maximum ? parsed : null
}

export function validateMissionForm(description: string, latitude: string, longitude: string): {
  payload: MissionPayload | null
  errors: MissionFormErrors
} {
  const errors: MissionFormErrors = {}
  const cleanDescription = description.trim()
  const lat = coordinate(latitude, -90, 90)
  const lon = coordinate(longitude, -180, 180)
  if (!cleanDescription) errors.description = 'Informe a descrição da ocorrência.'
  if (lat === null) errors.latitude = 'Informe uma latitude entre -90 e 90.'
  if (lon === null) errors.longitude = 'Informe uma longitude entre -180 e 180.'
  return {
    payload: Object.keys(errors).length ? null : { description: cleanDescription, location: { latitude: lat!, longitude: lon! } },
    errors,
  }
}

function firstText(value: unknown): string | null {
  if (typeof value === 'string' && value.trim()) return value.slice(0, 300)
  if (Array.isArray(value)) for (const item of value) { const text = firstText(item); if (text) return text }
  if (value && typeof value === 'object') for (const item of Object.values(value)) { const text = firstText(item); if (text) return text }
  return null
}

export function safeApiMessage(error: unknown): string | null {
  if (!(error instanceof ApiError) || ![400, 404, 409].includes(error.status)) return null
  if (!error.details) return null
  const allowed = ['detail', 'description', 'location', 'non_field_errors', 'required_type', 'requirements']
  for (const field of allowed) {
    const text = firstText(error.details[field])
    if (text) return text
  }
  return null
}
