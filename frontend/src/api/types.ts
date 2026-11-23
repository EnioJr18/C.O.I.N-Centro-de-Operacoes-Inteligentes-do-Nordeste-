export type Role = 'ADMIN' | 'OPERADOR' | null
export type UnitStatus = 'AVAILABLE' | 'BUSY' | 'MAINTENANCE'
export type UnitType = 'USB' | 'USA' | 'UR'
export type MissionStatus = 'Pendente' | 'Em Andamento' | 'Concluída' | 'Cancelada'
export interface Coordinates { latitude: number; longitude: number }
export interface User { id: number; username: string; first_name: string; last_name: string; email: string; is_active: boolean; role: Role }
export interface ManagedUser extends User { is_superuser: boolean; date_joined: string }
export interface Tokens { access: string; refresh: string }
export interface FleetUnit {
  id: number; name: string; license_plate: string; unit_type: UnitType
  current_location: Coordinates | null; status: UnitStatus; capabilities: Record<string, unknown>
  created_at: string; updated_at: string
}
export interface FleetUnitPayload {
  name: string; license_plate: string; unit_type: UnitType
  current_location?: Coordinates | null; capabilities?: Record<string, unknown>
}
export interface FleetUnitHistory {
  id: number
  action: 'UNIT_CREATED' | 'UNIT_UPDATED' | 'UNIT_MAINTENANCE_STARTED' | 'UNIT_MAINTENANCE_ENDED'
  previous_status: UnitStatus | null; new_status: UnitStatus | null
  changed_fields: string[]; request_id: string; created_at: string
  actor: Pick<User, 'id' | 'username' | 'first_name' | 'last_name'>
}
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Mission {
  id: number; description: string; location: Coordinates; status: MissionStatus
  assigned_unit: FleetUnit | null; created_at: string; updated_at: string
}
export interface MissionHistory {
  id: number; status: MissionStatus; notes: string | null; timestamp: string
  actor: Pick<User, 'id' | 'username' | 'first_name' | 'last_name'> | null
}
export interface MissionPayload { description: string; location: Coordinates }
export interface DispatchPayload extends MissionPayload { required_type?: UnitType }
export interface DispatchResult { mission: Mission; dispatched_unit: FleetUnit; distance_meters: number }
export interface DispatchEvent {
  event_id: string; schema_version: 1; occurred_at: string; action: 'DISPATCH'
  unit_id: number; unit_name: string; new_status: UnitStatus; mission_id: number; lat: number; lon: number
}
export interface MissionTransitionEvent {
  event_id: string; schema_version: 1; occurred_at: string
  action: 'MISSION_COMPLETED' | 'MISSION_CANCELLED'
  mission_id: number; mission_previous_status: MissionStatus; mission_new_status: MissionStatus
  unit_id: number | null; unit_previous_status: UnitStatus | null; unit_new_status: UnitStatus | null
}
export interface UnitMaintenanceEvent {
  event_id: string; schema_version: 1; occurred_at: string
  action: 'UNIT_MAINTENANCE_STARTED' | 'UNIT_MAINTENANCE_ENDED'
  unit_id: number; unit_name: string
  unit_previous_status: 'AVAILABLE' | 'MAINTENANCE'
  unit_new_status: 'AVAILABLE' | 'MAINTENANCE'
}
export type FleetEvent = DispatchEvent | MissionTransitionEvent | UnitMaintenanceEvent
export interface DashboardRecentMission {
  id: number; description: string; status: MissionStatus; created_at: string
  assigned_unit: Pick<FleetUnit, 'id' | 'name'> | null
}
export interface DashboardFleetSummary {
  total: number; available: number; availability_percentage: number
  with_location: number; without_location: number; by_status: Record<UnitStatus, number>
}
export interface DashboardMissionSummary {
  total: number; by_status: Record<MissionStatus, number>; recent: DashboardRecentMission[]
}
export interface DashboardSummary {
  generated_at: string; fleet: DashboardFleetSummary; missions: DashboardMissionSummary
}
