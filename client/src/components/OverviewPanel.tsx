import { diskAverage, formatRelative, isOnline, percent } from '../lib/format'
import type { HostSnapshots } from '../lib/api'
import type { Machine, Snapshot } from '../types/metrics'
import { EmptyInline, Icon, MetricInline } from './DashboardUI'
import { HostResourceCard } from './HostResourceCard'

export function OverviewPanel({ machines, snapshots, resourceHost, resourceSnap, onChooseHost, onOpenDetails, onOpenResource }: {
  machines: Machine[]
  snapshots: HostSnapshots
  resourceHost: Machine | null
  resourceSnap: Snapshot | null
  onChooseHost: (host: Machine) => void
  onOpenDetails: () => void
  onOpenResource: () => void
}) {
  return <>
    <section className="panel host-panel">
      <div className="panel-title-row"><div><div className="section-kicker">INFRASTRUCTURE</div><h2>Monitored hosts</h2></div><button className="text-button" onClick={onOpenDetails}>View selected host <Icon name="arrow" size={15} /></button></div>
      {machines.length ? <div className="table-scroll"><table><thead><tr><th>HOST</th><th>STATUS</th><th>OPERATING SYSTEM</th><th>CPU</th><th>MEMORY</th><th>LAST SEEN</th><th /></tr></thead><tbody>
        {machines.map((host) => {
          const snapshot = snapshots[host.machine_id]
          return <tr key={host.machine_id} className="host-row" onClick={() => onChooseHost(host)} tabIndex={0} onKeyDown={(event) => { if (event.key === 'Enter') onChooseHost(host) }}>
            <td><div className="host-cell"><span className="host-avatar"><Icon name="server" size={17} /></span><span><strong>{host.hostname || host.machine_id.slice(0, 16)}</strong><small>{host.machine_id}</small></span></div></td>
            <td><span className={`status-pill ${isOnline(host) ? 'online-pill' : 'offline-pill'}`}><span className="status-dot" />{isOnline(host) ? 'Online' : 'Offline'}</span></td>
            <td><span className="os-name">{host.operating_system || 'Unknown'}{host.os_version ? ` ${host.os_version}` : ''}</span></td>
            <td><MetricInline value={snapshot?.cpu_usage ?? null} /></td><td><MetricInline value={snapshot?.memory_usage ?? null} /></td>
            <td className="muted-cell">{formatRelative(host.last_seen_at)}</td><td><Icon name="chevron" size={16} /></td>
          </tr>
        })}
      </tbody></table></div> : <EmptyInline text="No monitored hosts have been added yet." />}
    </section>
    {resourceHost && <section className="overview-lower">
      <HostResourceCard host={resourceHost} snap={resourceSnap} kicker="LATEST HOST" actionLabel="Open host details" onAction={onOpenResource} />
      <div className="panel latest-panel"><div className="panel-title-row compact"><div><div className="section-kicker">LATEST SAMPLE</div><h3>Resource snapshot</h3></div><span className="sample-time">{resourceSnap?.collected_at ? formatRelative(resourceSnap.collected_at) : 'No data'}</span></div><div className="latest-metrics"><div><span>Disk use</span><strong>{percent(diskAverage(resourceSnap))}</strong></div><div><span>Containers</span><strong>{resourceSnap?.containers.length ?? 0}</strong></div><div><span>App checks</span><strong>{resourceSnap?.application_health.length ?? 0}</strong></div></div><div className="disk-bars">{resourceSnap?.disks.slice(0, 3).map((disk) => <div className="disk-line" key={`${disk.mount_point}-${disk.id}`}><div><span>{disk.mount_point}</span><strong>{percent(disk.usage_percent)}</strong></div><div className="progress-track"><span style={{ width: `${Math.min(disk.usage_percent ?? 0, 100)}%` }} /></div></div>)}</div></div>
    </section>}
  </>
}
