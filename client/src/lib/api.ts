import type { AppHealth, AppHistory, Container, History, Latest, Machine, Page, Snapshot } from '../types/metrics'

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

export type HostSnapshots = Record<string, Snapshot | null>
