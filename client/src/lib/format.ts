import type { Machine, Snapshot } from '../types/metrics'

export const ONLINE_WINDOW_MS = 15 * 1000
export const STALE_WINDOW_MS = 30 * 1000

export type HostStatus = 'online' | 'stale' | 'offline'

export function hostStatus(host: Machine): HostStatus {
  const ageMs = Date.now() - new Date(host.last_seen_at).getTime()
  if (ageMs < ONLINE_WINDOW_MS) return 'online'
  if (ageMs < STALE_WINDOW_MS) return 'stale'
  return 'offline'
}

export function isOnline(host: Machine) {
  return hostStatus(host) !== 'offline'
}

export function formatRelative(value: string | null | undefined) {
  if (!value) return '—'
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

export function formatBytes(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—'
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let size = value / 1024
  let index = 0
  while (size >= 1024 && index < units.length - 1) { size /= 1024; index++ }
  return `${size.toFixed(size >= 100 ? 0 : 1)} ${units[index]}`
}

export function percent(value: number | null | undefined) {
  return value == null ? '—' : `${value.toFixed(1)}%`
}

export function dateLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

export function diskAverage(snapshot: Snapshot | null | undefined) {
  const values = snapshot?.disks.map((disk) => disk.usage_percent).filter((value): value is number => value != null) ?? []
  return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
}

export function networkRate(snapshot: Snapshot | null | undefined) {
  if (!snapshot) return null
  const sent = snapshot.network_bytes_sent_per_second
  const received = snapshot.network_bytes_received_per_second
  return sent == null && received == null ? null : (sent ?? 0) + (received ?? 0)
}
