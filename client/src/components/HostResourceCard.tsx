import { diskAverage, formatBytes, networkRate, percent } from '../lib/format'
import type { Machine, Snapshot } from '../types/metrics'
import { Icon } from './DashboardUI'

export function HostResourceCard({ host, snap, kicker, actionLabel, onAction }: {
  host: Machine | null
  snap: Snapshot | null
  kicker: string
  actionLabel?: string
  onAction?: () => void
}) {
  if (!host) return null
  const netRate = snap ? networkRate(snap) : null
  return <div className="panel selected-host-card">
    <div className="section-kicker">{kicker}</div>
    <div className="selected-host-title"><span className="host-avatar large"><Icon name="server" size={20} /></span><div><h3>{host.hostname || host.machine_id}</h3><p>{host.machine_id}</p></div></div>
    <div className="resource-rows">
      <div className="resource-row"><div><span>CPU usage</span><strong>{percent(snap?.cpu_usage)}</strong></div><div className="progress-track"><span style={{ width: `${Math.min(snap?.cpu_usage ?? 0, 100)}%` }} /></div></div>
      <div className="resource-row"><div><span>Memory usage</span><strong>{percent(snap?.memory_usage)}</strong></div><div className="progress-track"><span style={{ width: `${Math.min(snap?.memory_usage ?? 0, 100)}%` }} /></div><small>{snap ? `${formatBytes(snap.memory_used_bytes)} of ${formatBytes(snap.memory_total_bytes)}` : 'No recent reading'}</small></div>
      <div className="resource-row"><div><span>Disk utilization</span><strong>{percent(diskAverage(snap))}</strong></div><div className="progress-track"><span style={{ width: `${Math.min(diskAverage(snap) ?? 0, 100)}%` }} /></div><small>{snap?.disks.length ?? 0} mount points</small></div>
      <div className="resource-row"><div><span>Network throughput</span><strong>{netRate == null ? '—' : `${formatBytes(netRate)}/s`}</strong></div><small>Inbound + outbound</small></div>
    </div>
    {actionLabel && onAction && <button className="primary-button" onClick={onAction}>{actionLabel} <Icon name="arrow" size={16} /></button>}
  </div>
}
