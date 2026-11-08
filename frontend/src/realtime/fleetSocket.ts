import type { ApiClient } from '../api/client'
import type { DispatchEvent, FleetEvent, MissionStatus, MissionTransitionEvent, UnitStatus } from '../api/types'

export type ConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected'
const statuses: UnitStatus[] = ['AVAILABLE', 'BUSY', 'MAINTENANCE']

const missionStatuses: MissionStatus[] = ['Pendente', 'Em Andamento', 'Concluída', 'Cancelada']

function parseDispatchValue(value: unknown): DispatchEvent | null {
    if (!value || typeof value !== 'object') return null
    const e = value as Record<string, unknown>
    if (e.schema_version !== 1 || e.action !== 'DISPATCH' || typeof e.event_id !== 'string' || !e.event_id
      || typeof e.occurred_at !== 'string' || Number.isNaN(Date.parse(e.occurred_at))
      || typeof e.unit_id !== 'number' || !Number.isInteger(e.unit_id)
      || typeof e.mission_id !== 'number' || !Number.isInteger(e.mission_id)
      || typeof e.unit_name !== 'string' || !statuses.includes(e.new_status as UnitStatus)
      || typeof e.lat !== 'number' || !Number.isFinite(e.lat) || Math.abs(e.lat) > 90
      || typeof e.lon !== 'number' || !Number.isFinite(e.lon) || Math.abs(e.lon) > 180) return null
    return e as unknown as DispatchEvent
}

function parseMissionTransitionValue(value: unknown): MissionTransitionEvent | null {
  if (!value || typeof value !== 'object') return null
  const e = value as Record<string, unknown>
  if (e.schema_version !== 1
    || !['MISSION_COMPLETED', 'MISSION_CANCELLED'].includes(e.action as string)
    || typeof e.event_id !== 'string' || !e.event_id
    || typeof e.occurred_at !== 'string' || Number.isNaN(Date.parse(e.occurred_at))
    || typeof e.mission_id !== 'number' || !Number.isInteger(e.mission_id)
    || !missionStatuses.includes(e.mission_previous_status as MissionStatus)
    || !missionStatuses.includes(e.mission_new_status as MissionStatus)) return null

  const completed = e.action === 'MISSION_COMPLETED'
  if (completed && (e.mission_previous_status !== 'Em Andamento' || e.mission_new_status !== 'Concluída')) return null
  if (!completed && (!['Pendente', 'Em Andamento'].includes(e.mission_previous_status as string)
    || e.mission_new_status !== 'Cancelada')) return null

  const noUnit = e.unit_id === null && e.unit_previous_status === null && e.unit_new_status === null
  const unitTransition = typeof e.unit_id === 'number' && Number.isInteger(e.unit_id)
    && statuses.includes(e.unit_previous_status as UnitStatus)
    && statuses.includes(e.unit_new_status as UnitStatus)
    && ((e.unit_previous_status === 'BUSY' && e.unit_new_status === 'AVAILABLE')
      || (e.unit_previous_status === 'MAINTENANCE' && e.unit_new_status === 'MAINTENANCE'))
  if ((!completed && e.mission_previous_status === 'Pendente' && !noUnit)
    || ((completed || e.mission_previous_status === 'Em Andamento') && !unitTransition)) return null
  return e as unknown as MissionTransitionEvent
}

export function parseDispatchEvent(raw: string): DispatchEvent | null {
  try { return parseDispatchValue(JSON.parse(raw)) } catch { return null }
}

export function parseFleetEvent(raw: string): FleetEvent | null {
  try {
    const value: unknown = JSON.parse(raw)
    return parseDispatchValue(value) || parseMissionTransitionValue(value)
  } catch { return null }
}

interface Options {
  client: ApiClient
  onState: (state: ConnectionState) => void
  onEvent: (event: FleetEvent) => void
  onConnected: () => void
  onForbidden: () => void
}

export class FleetSocket {
  private socket: WebSocket | null = null
  private timer: ReturnType<typeof setTimeout> | null = null
  private stopped = true
  private attempts = 0
  private quickAuthFailures = 0
  private openedAt = 0
  private seen = new Set<string>()
  constructor(private readonly options: Options) {}

  start() { if (!this.stopped) return; this.stopped = false; this.connect() }
  stop() {
    this.stopped = true
    if (this.timer) clearTimeout(this.timer)
    this.timer = null
    const socket = this.socket
    this.socket = null
    if (socket) { socket.onopen = null; socket.onmessage = null; socket.onclose = null; socket.onerror = null; socket.close() }
    this.options.onState('disconnected')
  }
  private connect() {
    const token = this.options.client.getAccess()
    if (this.stopped || !token) return
    this.options.onState(this.attempts ? 'reconnecting' : 'connecting')
    const url = new URL('/ws/fleet/', window.location.href)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(url.toString(), ['coin.v1', `coin.jwt.${token}`])
    this.socket = socket
    socket.onopen = () => {
      if (this.stopped || this.socket !== socket) return
      if (socket.protocol !== 'coin.v1') { socket.close(1002); return }
      this.openedAt = Date.now()
      this.options.onState('connected')
      this.options.onConnected()
    }
    socket.onmessage = (message) => {
      if (this.stopped || this.socket !== socket || typeof message.data !== 'string') return
      const event = parseFleetEvent(message.data)
      if (!event || this.seen.has(event.event_id)) return
      this.seen.add(event.event_id)
      if (this.seen.size > 500) this.seen.delete(this.seen.values().next().value!)
      this.options.onEvent(event)
    }
    socket.onerror = () => { /* onclose controls retries; never log credentials. */ }
    socket.onclose = (event) => {
      if (this.stopped || this.socket !== socket) return
      this.socket = null
      const stable = this.openedAt > 0 && Date.now() - this.openedAt >= 30000
      if (stable) { this.attempts = 0; this.quickAuthFailures = 0 }
      this.openedAt = 0
      if (event.code === 4403) { this.stop(); this.options.onForbidden(); return }
      if (event.code === 4401) {
        if (!stable && ++this.quickAuthFailures > 1) { this.stop(); this.options.onForbidden(); return }
        this.options.onState('reconnecting')
        if (this.options.client.getAccess() && this.options.client.getAccess() !== token) { this.connect(); return }
        void this.options.client.refresh().then(() => { if (!this.stopped) this.connect() }).catch(() => { if (!this.stopped) { this.stop(); this.options.onForbidden() } })
        return
      }
      this.scheduleReconnect()
    }
  }
  private scheduleReconnect() {
    if (this.stopped) return
    if (++this.attempts > 8) { this.options.onState('disconnected'); return }
    this.options.onState('reconnecting')
    const delay = Math.min(1000 * 2 ** (this.attempts - 1), 30000) * (0.8 + Math.random() * 0.4)
    this.timer = setTimeout(() => { this.timer = null; this.connect() }, delay)
  }
}
