import { useEffect, useState } from 'react'
import './App.css'
import { Icon, StatCard } from './components/DashboardUI'
import { HostDetailPanel } from './components/HostDetailPanel'
import { OverviewPanel } from './components/OverviewPanel'
import { Sidebar, Topbar, type DashboardView } from './components/Navigation'
import { useDashboardData } from './hooks/useDashboardData'
import { API_BASE_URL, monitoringApi } from './lib/api'
import { diskAverage, formatBytes, formatRelative, isOnline, networkRate, percent } from './lib/format'
import type { AppCheck, AppHealth, Container, Period, Snapshot } from './types/metrics'

function App() {
  const { machines, snapshots, loading, error, lastUpdated, refresh } = useDashboardData()
  const [selectedId, setSelectedId] = useState('')
  const [period, setPeriod] = useState<Period>('24h')
  const [history, setHistory] = useState<Snapshot[]>([])
  const [containers, setContainers] = useState<Container[]>([])
  const [appHealth, setAppHealth] = useState<AppHealth | null>(null)
  const [appHistory, setAppHistory] = useState<AppCheck[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState('')
  const [view, setView] = useState<DashboardView>('overview')

  useEffect(() => {
    if (!machines.length) { setSelectedId(''); return }
    if (!machines.some((host) => host.machine_id === selectedId)) setSelectedId(machines[0].machine_id)
  }, [machines, selectedId])

  useEffect(() => {
    if (!selectedId) return
    const controller = new AbortController()
    const hours = period === '1h' ? 1 : period === '24h' ? 24 : 168
    const start = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString()
    const query = `?start_time=${encodeURIComponent(start)}&limit=100&offset=0`
    setHistory([])
    setContainers([])
    setAppHealth(null)
    setAppHistory([])
    setDetailLoading(true)
    setDetailError('')
    Promise.all([
      monitoringApi.history(selectedId, query, controller.signal),
      monitoringApi.containers(selectedId, controller.signal),
      monitoringApi.applicationHealth(selectedId, controller.signal),
      monitoringApi.applicationHistory(selectedId, query, controller.signal),
    ]).then(([metricHistory, containerData, health, healthHistory]) => {
      setHistory(metricHistory.items.slice().reverse())
      setContainers(containerData.items)
      setAppHealth(health)
      setAppHistory(healthHistory.items)
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setDetailError(cause instanceof Error ? cause.message : 'Could not load host details')
    }).finally(() => { if (!controller.signal.aborted) setDetailLoading(false) })
    return () => controller.abort()
  }, [selectedId, period])

  const selected = machines.find((host) => host.machine_id === selectedId) ?? null
  const latest = selectedId ? snapshots[selectedId] ?? null : null
  const onlineCount = machines.filter(isOnline).length
  const currentSnapshots = machines.map((host) => snapshots[host.machine_id]).filter((snapshot): snapshot is Snapshot => snapshot != null)
  const fleetAverage = (key: 'cpu_usage' | 'memory_usage') => {
    const values = currentSnapshots.map((snapshot) => snapshot[key]).filter((value): value is number => value != null)
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null
  }
  const fleetDisks = currentSnapshots.map(diskAverage).filter((value): value is number => value != null)
  const fleetDiskAverage = fleetDisks.length ? fleetDisks.reduce((sum, value) => sum + value, 0) / fleetDisks.length : null
  const networkValues = currentSnapshots.map(networkRate).filter((value): value is number => value != null)
  const fleetNetwork = networkValues.reduce((sum, value) => sum + value, 0)
  const selectHost = (host: (typeof machines)[number]) => { setSelectedId(host.machine_id); setView('hosts') }
  const summaryIsFleet = view === 'overview'
  const networkSummary = summaryIsFleet
    ? (currentSnapshots.length ? `${formatBytes(fleetNetwork)}/s` : '—')
    : (networkRate(latest) == null ? '—' : `${formatBytes(networkRate(latest))}/s`)

  return <div className="app-shell">
    <Sidebar view={view} machines={machines} selectedId={selectedId} onlineCount={onlineCount} loading={loading} onView={setView} onSelectHost={selectHost} />
    <main className="main-content">
      <Topbar view={view} title={selected?.hostname || 'Host details'} lastUpdated={lastUpdated} onRefresh={() => { void refresh() }} />
      <div className="page-wrap">
        <div className="page-heading">
          <div><div className="eyebrow">MONITORING / {view === 'overview' ? 'SYSTEM OVERVIEW' : 'HOST DETAILS'}</div><h1>{view === 'overview' ? 'System overview' : (selected?.hostname || 'Host overview')}</h1><p>{view === 'overview' ? 'A real-time view of your infrastructure health.' : `${selected?.operating_system ?? 'Host'}${selected?.os_version ? ` · ${selected.os_version}` : ''}${selected?.architecture ? ` · ${selected.architecture}` : ''}`}</p></div>
          <div className="heading-tools">{view === 'hosts' && selected && <span className={`host-state ${isOnline(selected) ? 'state-online' : 'state-offline'}`}><span className="status-dot" />{isOnline(selected) ? 'Online' : 'Offline'}</span>}<label className="period-select"><span className="sr-only">History period</span><select value={period} onChange={(event) => setPeriod(event.target.value as Period)}><option value="1h">Last hour</option><option value="24h">Last 24 hours</option><option value="7d">Last 7 days</option></select></label></div>
        </div>

        {error && <div className="notice error-notice"><strong>Couldn’t reach the monitoring API.</strong><span>{error}</span><button onClick={() => { void refresh() }}>Try again</button><small>API: {API_BASE_URL}</small></div>}
        {loading && machines.length === 0 && !error && <div className="loading-panel"><span className="spinner" />Connecting to your monitoring server…</div>}
        {!loading && machines.length === 0 && !error && <div className="empty-panel"><div className="empty-icon"><Icon name="server" size={25} /></div><h2>No monitored hosts yet</h2><p>Once an agent sends its first metrics payload, the host will appear here.</p><span>Waiting for agent data</span></div>}

        {machines.length > 0 && <>
          <section className="stat-grid" aria-label="Infrastructure summary">
            <StatCard label="Monitored hosts" value={`${onlineCount} / ${machines.length}`} note={`${machines.length - onlineCount} offline`} icon="server" tone="violet" />
            <StatCard label="CPU utilization" value={percent(summaryIsFleet ? fleetAverage('cpu_usage') : latest?.cpu_usage)} note={summaryIsFleet ? `Average across ${currentSnapshots.length} hosts` : latest?.cpu_timestamp ? `Updated ${formatRelative(latest.cpu_timestamp)}` : 'No recent reading'} icon="activity" tone="blue" />
            <StatCard label="Memory usage" value={percent(summaryIsFleet ? fleetAverage('memory_usage') : latest?.memory_usage)} note={summaryIsFleet ? 'Average across reporting hosts' : latest ? `${formatBytes(latest.memory_used_bytes)} of ${formatBytes(latest.memory_total_bytes)}` : 'No recent reading'} icon="pulse" tone="teal" />
            <StatCard label="Disk utilization" value={percent(summaryIsFleet ? fleetDiskAverage : diskAverage(latest))} note={summaryIsFleet ? 'Average mounted filesystem usage' : `${latest?.disks.length ?? 0} mount points`} icon="server" tone="orange" />
            <StatCard label="Network throughput" value={networkSummary} note={summaryIsFleet ? 'Combined host traffic' : 'Inbound + outbound'} icon="grid" tone="orange" />
          </section>

          {view === 'overview' ? <OverviewPanel machines={machines} snapshots={snapshots} selected={selected} latest={latest} onChooseHost={selectHost} onOpenDetails={() => setView('hosts')} /> : selected && <HostDetailPanel latest={latest} history={history} containers={containers} appHealth={appHealth} appHistory={appHistory} loading={detailLoading} error={detailError} period={period} />}
          <footer className="page-footer"><span>Northstar Monitoring</span><span>Data refreshes every 30 seconds · Online if seen within 2 minutes</span></footer>
        </>}
      </div>
    </main>
  </div>
}

export default App
