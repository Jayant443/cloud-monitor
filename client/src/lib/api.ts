import type { AppHealth, AppHistory, Container, History, Latest, Machine, Page, Snapshot } from '../types/metrics'
import type { AlertItem, AlertPage, AlertRule, AlertRulePage, AlertSummary } from '../types/alerts'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    signal,
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const body = await response.json() as { detail?: string | { msg: string }[] }
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail.map((issue) => issue.msg).join(', ')
    } catch { /* response was not JSON */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

async function mutate<T>(path: string, method: 'POST' | 'PATCH' | 'DELETE', body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    signal,
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (response.status === 204) return undefined as T
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const payload = await response.json() as { detail?: string | { msg: string }[] }
      if (typeof payload.detail === 'string') detail = payload.detail
      else if (Array.isArray(payload.detail)) detail = payload.detail.map((issue) => issue.msg).join(', ')
    } catch { /* response was not JSON */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const monitoringApi = {
  hosts: (signal?: AbortSignal) => api<Page<Machine>>('/api/machines?limit=100&offset=0', signal),
  latest: (machineId: string, signal?: AbortSignal) =>
    api<Latest>(`/api/machines/${encodeURIComponent(machineId)}/metrics/latest`, signal),
  history: (machineId: string, query: string, signal?: AbortSignal) =>
    api<History>(`/api/machines/${encodeURIComponent(machineId)}/metrics/history${query}`, signal),
  containers: (machineId: string, signal?: AbortSignal) =>
    api<Page<Container>>(`/api/containers/latest?machine_id=${encodeURIComponent(machineId)}&limit=100&offset=0`, signal),
  applicationHealth: (machineId: string, signal?: AbortSignal) =>
    api<AppHealth>(`/api/machines/${encodeURIComponent(machineId)}/application-health/latest`, signal),
  applicationHistory: (machineId: string, query: string, signal?: AbortSignal) =>
    api<AppHistory>(`/api/machines/${encodeURIComponent(machineId)}/application-health/history${query}`, signal),
  latestForHost: (machine: Machine, signal?: AbortSignal) =>
    api<Latest>(`/api/machines/${encodeURIComponent(machine.machine_id)}/metrics/latest`, signal),
}

export const alertsApi = {
  rules: (signal?: AbortSignal) =>
    api<AlertRulePage>('/api/alert-rules?limit=100&offset=0', signal),
  createRule: (body: Record<string, unknown>, signal?: AbortSignal) =>
    mutate<AlertRule>('/api/alert-rules', 'POST', body, signal),
  updateRule: (id: number, body: Record<string, unknown>, signal?: AbortSignal) =>
    mutate<AlertRule>(`/api/alert-rules/${id}`, 'PATCH', body, signal),
  enableRule: (id: number, signal?: AbortSignal) =>
    mutate<AlertRule>(`/api/alert-rules/${id}/enable`, 'POST', {}, signal),
  disableRule: (id: number, signal?: AbortSignal) =>
    mutate<AlertRule>(`/api/alert-rules/${id}/disable`, 'POST', {}, signal),
  deleteRule: (id: number, signal?: AbortSignal) =>
    mutate<void>(`/api/alert-rules/${id}`, 'DELETE', undefined, signal),
  summary: (signal?: AbortSignal) => api<AlertSummary>('/api/alerts/summary', signal),
  active: (signal?: AbortSignal) =>
    api<AlertPage>('/api/alerts?status=active&limit=100&offset=0', signal),
  acknowledged: (signal?: AbortSignal) =>
    api<AlertPage>('/api/alerts?status=acknowledged&limit=100&offset=0', signal),
  history: (signal?: AbortSignal) =>
    api<AlertPage>('/api/alerts?status=resolved&limit=100&offset=0', signal),
  acknowledge: (id: number, signal?: AbortSignal) =>
    mutate<AlertItem>(`/api/alerts/${id}/acknowledge`, 'POST', {}, signal),
  resolve: (id: number, signal?: AbortSignal) =>
    mutate<AlertItem>(`/api/alerts/${id}/resolve`, 'POST', {}, signal),
}

export type HostSnapshots = Record<string, Snapshot | null>
