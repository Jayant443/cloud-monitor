import { useCallback, useEffect, useState } from 'react'
import { monitoringApi, type HostSnapshots } from '../lib/api'
import type { Machine } from '../types/metrics'

export function useDashboardData() {
  const [machines, setMachines] = useState<Machine[]>([])
  const [snapshots, setSnapshots] = useState<HostSnapshots>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setError('')
    try {
      const hosts = await monitoringApi.hosts(signal)
      setMachines(hosts.items)
      const latest = await Promise.all(hosts.items.map(async (host) => {
        try {
          const result = await monitoringApi.latestForHost(host, signal)
          return [host.machine_id, result.metrics] as const
        } catch (cause) {
          if (signal?.aborted) throw cause
          return [host.machine_id, null] as const
        }
      }))
      setSnapshots(Object.fromEntries(latest))
      setLastUpdated(new Date())
    } catch (cause) {
      if (!signal?.aborted) setError(cause instanceof Error ? cause.message : 'Could not load monitoring data')
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal)
    const timer = window.setInterval(() => void refresh(), 30_000)
    return () => { controller.abort(); window.clearInterval(timer) }
  }, [refresh])

  return { machines, snapshots, loading, error, lastUpdated, refresh }
}
