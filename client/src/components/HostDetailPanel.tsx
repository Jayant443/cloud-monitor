import { dateLabel, diskAverage, formatBytes, formatRelative, networkRate, percent } from '../lib/format'
import type { AppCheck, AppHealth, Container, Period, Snapshot } from '../types/metrics'
import { ChartCard, EmptyInline, Icon } from './DashboardUI'

export function HostDetailPanel({ latest, history, containers, appHealth, appHistory, loading, error, period }: {
  latest: Snapshot | null
  history: Snapshot[]
  containers: Container[]
  appHealth: AppHealth | null
  appHistory: AppCheck[]
  loading: boolean
  error: string
  period: Period
}) {
  const series = {
    cpu: history.map((sample) => sample.cpu_usage),
    memory: history.map((sample) => sample.memory_usage),
    disk: history.map((sample) => diskAverage(sample)),
    network: history.map((sample) => networkRate(sample)),
  }
  const timeLabels = history.map((sample) => dateLabel(sample.collected_at))
  const healthy = appHealth?.items.filter((check) => check.available === true).length ?? 0
  const appCount = appHealth?.items.length ?? 0
  return <>
    {error && <div className="notice error-notice detail-notice"><strong>Some host details could not be loaded.</strong><span>{error}</span></div>}
    {loading && <div className="detail-loading"><span className="spinner" />Loading host detail…</div>}
    <section className="chart-grid">
      <ChartCard title="CPU utilization" detail="Host processor usage" values={series.cpu} labels={timeLabels} color="#e8e8e8" icon="activity" />
      <ChartCard title="Memory usage" detail="Used memory percentage" values={series.memory} labels={timeLabels} color="#20a88b" icon="pulse" />
      <ChartCard title="Disk utilization" detail="Average across mounted filesystems" values={series.disk} labels={timeLabels} color="#e49a42" icon="server" />
      <ChartCard title="Network throughput" detail="Inbound + outbound" values={series.network} labels={timeLabels} color="#4989dd" unit="bytes" icon="grid" />
    </section>
    <section className="detail-grid">
      <div className="panel detail-panel"><div className="panel-title-row"><div><div className="section-kicker">LATEST READINGS</div><h2>Disk filesystems</h2></div><span className="count-badge">{latest?.disks.length ?? 0}</span></div>
        {latest?.disks.length ? <div className="mount-list">{latest.disks.map((disk) => <div className="mount-row" key={`${disk.mount_point}-${disk.id}`}><div className="mount-info"><span className="mount-name">{disk.mount_point}</span><span>{formatBytes(disk.used_bytes)} used of {formatBytes(disk.total_bytes)}</span></div><strong>{percent(disk.usage_percent)}</strong><div className="progress-track"><span style={{ width: `${Math.min(disk.usage_percent ?? 0, 100)}%` }} /></div></div>)}</div> : <EmptyInline text="No disk readings available." />}
      </div>
      <div className="panel detail-panel"><div className="panel-title-row"><div><div className="section-kicker">APPLICATION PROBES</div><h2>Application health</h2></div><span className={`health-summary ${appCount && healthy === appCount ? 'good' : healthy ? 'partial' : ''}`}>{appCount ? `${healthy}/${appCount} up` : 'No checks'}</span></div>
        {appHealth?.collection_error && <div className="inline-error">{appHealth.collection_error}</div>}
        {appCount ? <div className="health-list">{appHealth?.items.map((check) => <div className="health-row" key={check.id}><span className={`health-mark ${check.available === true ? 'good' : check.available === false ? 'bad' : 'unknown'}`} /><div className="health-name"><strong>{check.endpoint_name || 'Unnamed endpoint'}</strong><span>{check.error || (check.response_status ? `HTTP ${check.response_status}` : 'No response status')}</span></div><strong className="response-time">{check.response_time_seconds == null ? '—' : `${(check.response_time_seconds * 1000).toFixed(0)} ms`}</strong></div>)}</div> : <EmptyInline text="No application health checks reported." />}
        {appHistory.length > 0 && <div className="history-note">{appHistory.length} health observations in selected period · latest {appHealth?.sampled_at ? formatRelative(appHealth.sampled_at) : '—'}</div>}
      </div>
    </section>
    <section className="panel detail-panel container-panel"><div className="panel-title-row"><div><div className="section-kicker">DOCKER</div><h2>Containers</h2></div><span className="count-badge">{containers.length}</span></div>
      {containers.length ? <div className="table-scroll"><table><thead><tr><th>CONTAINER</th><th>STATUS</th><th>CPU</th><th>MEMORY</th><th>RESTARTS</th><th>HEALTH</th></tr></thead><tbody>{containers.map((container) => <tr key={`${container.container_id}-${container.sampled_at}`}><td><div className="container-name"><span className="container-icon"><Icon name="box" size={16} /></span><span><strong>{container.name || container.container_id?.slice(0, 12) || 'Unknown'}</strong><small>{container.image || container.container_id || 'Image unavailable'}</small></span></div></td><td><span className={`container-status ${container.status === 'running' ? 'running' : ''}`}><span className="status-dot" />{container.status || 'Unknown'}</span></td><td>{percent(container.cpu_usage_percent)}</td><td>{formatBytes(container.memory_usage_bytes)}{container.memory_limit_bytes ? <small className="cell-sub"> / {formatBytes(container.memory_limit_bytes)}</small> : null}</td><td>{container.restart_count ?? '—'}</td><td><span className={`health-text ${container.health_status === 'healthy' ? 'good-text' : container.health_status === 'unhealthy' ? 'bad-text' : ''}`}>{container.health_status || 'No check'}</span></td></tr>)}</tbody></table></div> : <EmptyInline text="No Docker containers were reported for this host." />}
    </section>
    <section className="panel detail-panel container-panel"><div className="panel-title-row"><div><div className="section-kicker">PROCESSES</div><h2>Monitored processes</h2></div><span className="count-badge">{latest?.processes.length ?? 0}</span></div>
      {latest && !latest.process_enabled ? <EmptyInline text="Process monitoring is disabled for this host." /> : latest?.process_collection_error ? <div className="inline-error">{latest.process_collection_error}</div> : null}
      {latest?.process_collection_errors.length ? <div className="inline-error">{latest.process_collection_errors.join(', ')}</div> : null}
      {latest?.processes.length ? <div className="table-scroll"><table><thead><tr><th>PID</th><th>PROCESS</th><th>CPU</th><th>MEMORY</th><th>STATUS</th></tr></thead><tbody>{latest.processes.map((proc) => <tr key={`${proc.pid}-${proc.id}`}><td>{proc.pid}</td><td><strong>{proc.process_name || 'Unknown'}</strong>{proc.collection_error ? <small className="cell-sub"> {proc.collection_error}</small> : null}</td><td>{percent(proc.cpu_percent)}</td><td>{formatBytes(proc.memory_usage_bytes)}</td><td>{proc.status || '—'}</td></tr>)}</tbody></table></div> : latest?.process_enabled ? <EmptyInline text="No processes reported for this host." /> : null}
    </section>
    <section className="panel detail-panel history-panel"><div className="panel-title-row"><div><div className="section-kicker">TIME SERIES</div><h2>Recent metric samples</h2></div><span className="period-chip">{period === '1h' ? '1 hour' : period === '24h' ? '24 hours' : '7 days'}</span></div>
      {history.length ? <div className="table-scroll"><table><thead><tr><th>TIMESTAMP</th><th>CPU</th><th>MEMORY</th><th>DISK AVG.</th><th>NETWORK RATE</th></tr></thead><tbody>{history.slice(-12).reverse().map((sample) => <tr key={`${sample.id}-${sample.collected_at}`}><td>{dateLabel(sample.collected_at)}</td><td>{percent(sample.cpu_usage)}</td><td>{percent(sample.memory_usage)} <small className="cell-sub">{formatBytes(sample.memory_used_bytes)}</small></td><td>{percent(diskAverage(sample))}</td><td>{networkRate(sample) == null ? '—' : `${formatBytes(networkRate(sample))}/s`}</td></tr>)}</tbody></table></div> : !loading && <EmptyInline text="No metric history for this period." />}
    </section>
  </>
}
