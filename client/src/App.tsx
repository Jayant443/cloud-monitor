import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { AlertsPanel } from './components/AlertsPanel'
import { AuthPage } from './components/AuthPage'
import { Icon, StatCard } from './components/DashboardUI'
import { HostDetailPanel } from './components/HostDetailPanel'
import { HostResourceCard } from './components/HostResourceCard'
import { OverviewPanel } from './components/OverviewPanel'
import { Sidebar, Topbar, type DashboardView } from './components/Navigation'
import { useDashboardData } from './hooks/useDashboardData'
import { API_BASE_URL, alertsApi, monitoringApi } from './lib/api'
import { authApi, getToken, setToken, setUnauthorizedHandler, type AuthUser } from './lib/auth'
import { formatRelative, hostStatus, isOnline } from './lib/format'
import type { AlertItem, AlertRule, AlertSummary } from './types/alerts'
import type { AppCheck, AppHealth, Container, Period, Snapshot } from './types/metrics'

function App() {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authChecked, setAuthChecked] = useState(() => !getToken())
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
  const [refreshKey, setRefreshKey] = useState(0)
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null)
  const [activeAlerts, setActiveAlerts] = useState<AlertItem[]>([])
  const [ackedAlerts, setAckedAlerts] = useState<AlertItem[]>([])
  const [alertHistory, setAlertHistory] = useState<AlertItem[]>([])
  const [alertRules, setAlertRules] = useState<AlertRule[]>([])
  const [alertsLoading, setAlertsLoading] = useState(false)
  const [alertsError, setAlertsError] = useState('')

  const handleLogout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(handleLogout)
    return () => setUnauthorizedHandler(null)
  }, [handleLogout])

  useEffect(() => {
    if (!getToken()) return
    const controller = new AbortController()
    authApi.me(controller.signal).then((me) => {
      if (!controller.signal.aborted) { setUser(me); setAuthChecked(true) }
    }).catch(() => {
      if (!controller.signal.aborted) { setToken(null); setUser(null); setAuthChecked(true) }
    })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (!machines.length) { setSelectedId(''); return }
    if (!machines.some((host) => host.machine_id === selectedId)) setSelectedId(machines[0].machine_id)
  }, [machines, selectedId])

  useEffect(() => {
    setHistory([])
    setContainers([])
    setAppHealth(null)
    setAppHistory([])
    setDetailError('')
  }, [selectedId, period])

  useEffect(() => {
    if (!selectedId) return
    const controller = new AbortController()
    const hours = period === '1h' ? 1 : period === '24h' ? 24 : 168
    const start = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString()
    const query = `?start_time=${encodeURIComponent(start)}&limit=100&offset=0`
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
  }, [selectedId, period, refreshKey])

  const refreshAlerts = useCallback(async (signal?: AbortSignal) => {
    setAlertsLoading(true)
    setAlertsError('')
    try {
      const [summary, active, acked, resolved, rules] = await Promise.all([
        alertsApi.summary(signal),
        alertsApi.active(signal),
        alertsApi.acknowledged(signal),
        alertsApi.history(signal),
        alertsApi.rules(signal),
      ])
      if (signal?.aborted) return
      setAlertSummary(summary)
      setActiveAlerts(active.items)
      setAckedAlerts(acked.items)
      setAlertHistory(resolved.items)
      setAlertRules(rules.items)
    } catch (cause) {
      if (!signal?.aborted) setAlertsError(cause instanceof Error ? cause.message : 'Could not load alerts')
    } finally {
      if (!signal?.aborted) setAlertsLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refreshAlerts(controller.signal)
    return () => controller.abort()
  }, [refreshAlerts, refreshKey])

  // Manual + auto refresh: summary (machines/latest), host details, and alerts together.
  const handleRefreshAll = useCallback(() => {
    void refresh()
    setRefreshKey((key) => key + 1)
  }, [refresh])

  useEffect(() => {
    const timer = window.setInterval(handleRefreshAll, 30_000)
    return () => { window.clearInterval(timer) }
  }, [handleRefreshAll])

  const selected = machines.find((host) => host.machine_id === selectedId) ?? null
  const latest = selectedId ? snapshots[selectedId] ?? null : null
  const onlineCount = machines.filter(isOnline).length
  // Newest added host drives the overview cards (no fleet averaging).
  const newestHost = machines.length
    ? machines.reduce((a, b) => (a.first_seen_at >= b.first_seen_at ? a : b))
    : null
  const newestSnapshot = newestHost ? snapshots[newestHost.machine_id] ?? null : null
  const selectHost = (host: (typeof machines)[number]) => { setSelectedId(host.machine_id); setView('hosts') }

  const heading = view === 'alerts'
    ? { eyebrow: 'MONITORING / ALERTS', title: 'Alerts', sub: 'Active, triaged, and historical alert states.' }
    : view === 'overview'
      ? { eyebrow: 'MONITORING / SYSTEM OVERVIEW', title: 'System overview', sub: 'A real-time view of your infrastructure health.' }
      : { eyebrow: 'MONITORING / HOST DETAILS', title: selected?.hostname || 'Host overview', sub: `${selected?.operating_system ?? 'Host'}${selected?.os_version ? ` · ${selected.os_version}` : ''}${selected?.architecture ? ` · ${selected.architecture}` : ''}` }

  return <div className="app-shell">
    {!authChecked
      ? <div className="auth-wrap"><div className="loading-panel"><span className="spinner" />Checking your session…</div></div>
      : !user
        ? <AuthPage onAuthed={setUser} />
        : <>
    <Sidebar view={view} machines={machines} selectedId={selectedId} onlineCount={onlineCount} loading={loading} alertCount={activeAlerts.length} onView={setView} onSelectHost={selectHost} />
    <main className="main-content">
      <Topbar view={view} title={view === 'alerts' ? 'Alerts' : (selected?.hostname || 'Host details')} lastUpdated={lastUpdated} user={user} onRefresh={handleRefreshAll} onLogout={handleLogout} />
      <div className="page-wrap">
        <div className="page-heading">
          <div><div className="eyebrow">{heading.eyebrow}</div><h1>{heading.title}</h1><p>{heading.sub}</p></div>
          <div className="heading-tools">{view === 'hosts' && selected && (() => {
            const status = hostStatus(selected)
            const label = status === 'online' ? 'Online' : status === 'stale' ? 'Stale' : 'Offline'
            return <span className={`host-state state-${status}`} title={`Last seen ${formatRelative(selected.last_seen_at)}`}><span className="status-dot" />{label} · {formatRelative(selected.last_seen_at)}</span>
          })()}{view !== 'alerts' && <label className="period-select"><span className="sr-only">History period</span><select value={period} onChange={(event) => setPeriod(event.target.value as Period)}><option value="1h">Last hour</option><option value="24h">Last 24 hours</option><option value="7d">Last 7 days</option></select></label>}</div>
        </div>

        {error && <div className="notice error-notice"><strong>Couldn’t reach the monitoring API.</strong><span>{error}</span><button onClick={handleRefreshAll}>Try again</button><small>API: {API_BASE_URL}</small></div>}
        {loading && machines.length === 0 && !error && view !== 'alerts' && <div className="loading-panel"><span className="spinner" />Connecting to your monitoring server…</div>}
        {!loading && machines.length === 0 && !error && view !== 'alerts' && <div className="empty-panel"><div className="empty-icon"><Icon name="server" size={25} /></div><h2>No monitored hosts yet</h2><p>Once an agent sends its first metrics payload, the host will appear here.</p><span>Waiting for agent data</span></div>}

        {view === 'alerts'
          ? <><AlertsPanel summary={alertSummary} active={activeAlerts} acknowledged={ackedAlerts} history={alertHistory} rules={alertRules} loading={alertsLoading} error={alertsError} onChanged={() => { void refreshAlerts() }} />
            <footer className="page-footer"><span>TheMonitor</span><span>Data refreshes every 30 seconds · Online &lt;15s · Stale &lt;30s · Offline after 30s</span></footer></>
          : machines.length > 0 && <>
          {view === 'overview' && <section className="stat-grid" aria-label="Infrastructure summary">
            <StatCard label="Monitored hosts" value={`${onlineCount} / ${machines.length}`} note={`${machines.length - onlineCount} offline`} icon="server" tone="violet" />
          </section>}

          {view === 'overview' ? <OverviewPanel machines={machines} snapshots={snapshots} resourceHost={newestHost} resourceSnap={newestSnapshot} onChooseHost={selectHost} onOpenDetails={() => setView('hosts')} onOpenResource={() => { if (newestHost) selectHost(newestHost) }} /> : selected && <>
            <HostResourceCard host={selected} snap={latest} kicker="HOST RESOURCES" />
            <div style={{ height: 14 }} />
            <HostDetailPanel latest={latest} history={history} containers={containers} appHealth={appHealth} appHistory={appHistory} loading={detailLoading} error={detailError} period={period} />
          </>}
          <footer className="page-footer"><span>TheMonitor</span><span>Data refreshes every 30 seconds · Online &lt;15s · Stale &lt;30s · Offline after 30s</span></footer>
        </>}
      </div>
    </main>
    </>}
  </div>
}

export default App
