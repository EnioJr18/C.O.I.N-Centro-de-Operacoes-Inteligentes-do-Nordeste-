export type Role = 'ADMIN' | 'OPERADOR' | null
export type UnitStatus = 'AVAILABLE' | 'BUSY' | 'MAINTENANCE'
export type UnitType = 'USB' | 'USA' | 'UR'
export type MissionStatus = 'Pendente' | 'Em Andamento' | 'Concluída' | 'Cancelada'
export interface Coordinates { latitude: number; longitude: number }
export interface User { id: number; username: string; first_name: string; last_name: string; email: string; is_active: boolean; role: Role }
export interface Tokens { access: string; refresh: string }
export interface FleetUnit {
  id: number; name: string; license_plate: string; unit_type: UnitType
  current_location: Coordinates | null; status: UnitStatus; capabilities: Record<string, unknown>
  created_at: string; updated_at: string
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Mission {
  id: number; description: string; location: Coordinates; status: MissionStatus
  assigned_unit: FleetUnit | null; created_at: string; updated_at: string
}
export interface MissionHistory {
  id: number; status: MissionStatus; notes: string | null; timestamp: string
}
export interface MissionPayload { description: string; location: Coordinates }
export interface DispatchPayload extends MissionPayload { required_type?: UnitType }
export interface DispatchResult { mission: Mission; dispatched_unit: FleetUnit; distance_meters: number }
export interface DispatchEvent {
  event_id: string; schema_version: 1; occurred_at: string; action: 'DISPATCH'
  unit_id: number; unit_name: string; new_status: UnitStatus; mission_id: number; lat: number; lon: number
}
