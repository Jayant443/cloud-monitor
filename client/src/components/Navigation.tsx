import { formatRelative, hostStatus } from '../lib/format'
import type { AuthUser } from '../lib/auth'
import type { Machine } from '../types/metrics'
import { Icon } from './DashboardUI'

export type DashboardView = 'overview' | 'hosts' | 'alerts' | 'settings'

export function Sidebar({ view, machines, selectedId, onlineCount, loading, alertCount, onView, onSelectHost }: {
  view: DashboardView
  machines: Machine[]
  selectedId: string
  onlineCount: number
  loading: boolean
  alertCount: number
  onView: (view: DashboardView) => void
  onSelectHost: (host: Machine) => void
}) {
  return <aside className="sidebar">
    <button className="brand" onClick={() => onView('overview')}><span>TheMonitor</span></button>
    <div className="side-label">WORKSPACE</div>
    <nav className="side-nav" aria-label="Main navigation">
      <button className={view === 'overview' ? 'active' : ''} onClick={() => onView('overview')}><Icon name="grid" /> Overview</button>
      <button className={view === 'hosts' ? 'active' : ''} onClick={() => onView('hosts')}><Icon name="server" /> Hosts <span className="nav-count">{machines.length}</span></button>
      <button className={view === 'alerts' ? 'active' : ''} onClick={() => onView('alerts')}><Icon name="pulse" /> Alerts {alertCount > 0 && <span className="nav-count">{alertCount}</span>}</button>
      <button className={view === 'settings' ? 'active' : ''} onClick={() => onView('settings')}><Icon name="box" /> Settings</button>
    </nav>
    <div className="side-label host-label">MONITORED HOSTS</div>
    <div className="sidebar-hosts">
      {machines.slice(0, 6).map((host) => <button key={host.machine_id} className={`sidebar-host ${host.machine_id === selectedId ? 'selected' : ''}`} onClick={() => onSelectHost(host)}><span className={`status-dot ${hostStatus(host)}`} /><span className="sidebar-host-name">{host.hostname || host.machine_id.slice(0, 12)}</span></button>)}
      {!loading && machines.length === 0 && <div className="side-empty">No hosts yet</div>}
    </div>
    <div className="sidebar-bottom"><span className="live-indicator" /><div><strong>Agent network</strong><small>{onlineCount} of {machines.length} hosts online</small></div></div>
  </aside>
}

export function Topbar({ view, title, lastUpdated, user, onRefresh, onLogout }: { view: DashboardView; title: string; lastUpdated: Date | null; user: AuthUser | null; onRefresh: () => void; onLogout: () => void }) {
  const initials = (user?.display_name || user?.username || '?').trim().slice(0, 2).toUpperCase()
  return <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><Icon name="chevron" size={14} /><strong>{view === 'overview' ? 'Overview' : title}</strong></div><div className="top-actions"><span className="updated-label"><span className="live-indicator" />Updated {lastUpdated ? formatRelative(lastUpdated.toISOString()) : '—'}</span><button className="refresh-button" onClick={onRefresh} aria-label="Refresh metrics"><Icon name="refresh" size={16} /><span>Refresh</span></button><span className="topbar-user"><span className="avatar" title={user?.username}>{initials}</span><button className="logout-button" onClick={onLogout}>Log out</button></span></div></header>
}
