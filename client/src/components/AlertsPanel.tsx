import { useState } from 'react'
import { alertsApi } from '../lib/api'
import { formatRelative } from '../lib/format'
import type { AlertItem, AlertRule } from '../types/alerts'
import { EmptyInline } from './DashboardUI'

function severityClass(severity: string | null) {
  if (severity === 'critical') return 'bad-text'
  if (severity === 'warning') return 'partial'
  return ''
}

function resourceLabel(alert: AlertItem) {
  if (alert.resource_type === 'host' || !alert.resource_key) return alert.machine_id.slice(0, 16)
  return `${alert.resource_type}:${alert.resource_key.slice(0, 40)}`
}

export function AlertsPanel({ summary, active, acknowledged, history, rules, loading, error, onChanged }: {
  summary: { active: number; acknowledged: number; critical_active: number } | null
  active: AlertItem[]
  acknowledged: AlertItem[]
  history: AlertItem[]
  rules: AlertRule[]
  loading: boolean
  error: string
  onChanged: () => void
}) {
  const [formError, setFormError] = useState('')
  const [name, setName] = useState('High CPU usage')
  const [metric, setMetric] = useState('cpu_usage')
  const [condition, setCondition] = useState('gte')
  const [threshold, setThreshold] = useState('80')
  const [interval, setInterval] = useState('60')
  const [severity, setSeverity] = useState('warning')
  const [consecutive, setConsecutive] = useState('2')
  const [busy, setBusy] = useState(false)

  const submitRule = async () => {
    setFormError('')
    setBusy(true)
    try {
      await alertsApi.createRule({
        name: name.trim(),
        metric,
        condition,
        threshold: Number(threshold),
        evaluation_interval_seconds: Number(interval),
        severity,
        enabled: true,
        consecutive_breaches_required: Number(consecutive),
      })
      onChanged()
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : 'Could not create rule')
    } finally {
      setBusy(false)
    }
  }

  const act = async (fn: () => Promise<unknown>) => {
    setFormError('')
    try {
      await fn()
      onChanged()
    } catch (cause) {
      setFormError(cause instanceof Error ? cause.message : 'Action failed')
    }
  }

  return <>
    {error && <div className="notice error-notice"><strong>Couldn’t load alerts.</strong><span>{error}</span></div>}
    {formError && <div className="inline-error">{formError}</div>}
    {loading && active.length === 0 && rules.length === 0 && !error && <div className="detail-loading"><span className="spinner" />Loading alerts…</div>}

    <section className="stat-grid" aria-label="Alert summary">
      <div className="panel selected-host-card"><div className="section-kicker">ACTIVE ALERTS</div><h3>{summary?.active ?? active.length}</h3><span>{summary?.critical_active ?? 0} critical</span></div>
      <div className="panel selected-host-card"><div className="section-kicker">ACKNOWLEDGED</div><h3>{summary?.acknowledged ?? acknowledged.length}</h3><span>Awaiting resolution</span></div>
      <div className="panel selected-host-card"><div className="section-kicker">RESOLVED (RECENT)</div><h3>{history.length}</h3><span>Resolved by you</span></div>
      <div className="panel selected-host-card"><div className="section-kicker">RULES</div><h3>{rules.length}</h3><span>{rules.filter((r) => r.enabled).length} enabled</span></div>
    </section>

    <section className="panel detail-panel container-panel">
      <div className="panel-title-row"><div><div className="section-kicker">NEEDS ATTENTION</div><h2>Active alerts</h2></div><span className="count-badge">{active.length}</span></div>
      {active.length ? <div className="table-scroll"><table><thead><tr><th>SEVERITY</th><th>RULE</th><th>RESOURCE</th><th>OBSERVED</th><th>TRIGGERED</th><th /></tr></thead><tbody>
        {active.map((alert) => <tr key={alert.id}>
          <td><span className={`health-text ${severityClass(alert.rule_severity)}`}>{alert.rule_severity || '—'}</span></td>
          <td><strong>{alert.rule_name || `Rule ${alert.rule_id}`}</strong><small className="cell-sub"> {alert.rule_metric || ''}</small></td>
          <td><small>{resourceLabel(alert)}</small></td>
          <td>{alert.observed_value}</td>
          <td className="muted-cell">{formatRelative(alert.triggered_at)}</td>
          <td><span className="alert-actions"><button className="btn-ack" onClick={() => void act(() => alertsApi.acknowledge(alert.id))}>Acknowledge</button><button className="btn-resolve" onClick={() => void act(() => alertsApi.resolve(alert.id))}>Resolve</button></span></td>
        </tr>)}
      </tbody></table></div> : <EmptyInline text="No active alerts. Rules evaluate in the background every few seconds." />}
    </section>

    {acknowledged.length > 0 && <section className="panel detail-panel container-panel">
      <div className="panel-title-row"><div><div className="section-kicker">TRIAGED</div><h2>Acknowledged</h2></div><span className="count-badge">{acknowledged.length}</span></div>
      <div className="table-scroll"><table><thead><tr><th>RULE</th><th>RESOURCE</th><th>OBSERVED</th><th>TRIGGERED</th><th /></tr></thead><tbody>
        {acknowledged.map((alert) => <tr key={alert.id}>
          <td><strong>{alert.rule_name || `Rule ${alert.rule_id}`}</strong></td>
          <td><small>{resourceLabel(alert)}</small></td>
          <td>{alert.observed_value}</td>
          <td className="muted-cell">{formatRelative(alert.triggered_at)}</td>
          <td><span className="alert-actions"><button className="btn-resolve" onClick={() => void act(() => alertsApi.resolve(alert.id))}>Resolve</button></span></td>
        </tr>)}
      </tbody></table></div>
    </section>}

    <section className="panel detail-panel container-panel">
      <div className="panel-title-row"><div><div className="section-kicker">AUTOMATION</div><h2>Alert rules</h2></div><span className="count-badge">{rules.length}</span></div>
      {rules.length ? <div className="table-scroll"><table><thead><tr><th>RULE</th><th>CONDITION</th><th>EVERY</th><th>STREAK</th><th>STATE</th><th>ACTIVE</th><th /></tr></thead><tbody>
        {rules.map((rule) => <tr key={rule.id}>
          <td><strong>{rule.name}</strong><small className="cell-sub"> {rule.metric} · {rule.severity}</small></td>
          <td><small>{rule.condition} {rule.threshold}</small></td>
          <td><small>{rule.evaluation_interval_seconds}s</small></td>
          <td><small>×{rule.consecutive_breaches_required}</small></td>
          <td>{rule.enabled ? 'Enabled' : 'Disabled'}</td>
          <td>{rule.active_alert_count}</td>
          <td>
            {rule.enabled
              ? <button className="text-button" onClick={() => void act(() => alertsApi.disableRule(rule.id))}>Disable</button>
              : <button className="text-button" onClick={() => void act(() => alertsApi.enableRule(rule.id))}>Enable</button>}
            {' '}<button className="text-button" onClick={() => { if (window.confirm(`Delete rule "${rule.name}" and its alerts?`)) void act(() => alertsApi.deleteRule(rule.id)) }}>Delete</button>
          </td>
        </tr>)}
      </tbody></table></div> : <EmptyInline text="No alert rules yet. Create one below." />}
      <div className="rule-form">
        <div className="rule-form-title"><span className="section-kicker">NEW RULE</span><p>Create a threshold rule. It evaluates in the background and opens one alert per matching resource.</p></div>
        <div className="rule-form-grid">
          <label className="rule-field rule-field-wide"><span>Rule name</span><input value={name} onChange={(e) => setName(e.target.value)} placeholder="High CPU usage" /></label>
          <label className="rule-field"><span>Metric</span><select value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="cpu_usage">cpu_usage %</option>
            <option value="memory_usage">memory_usage %</option>
            <option value="disk_usage">disk_usage %</option>
            <option value="host_inactivity_seconds">host_inactivity_seconds</option>
            <option value="container_stopped">container_stopped</option>
            <option value="app_health_failed">app_health_failed</option>
          </select></label>
          <label className="rule-field"><span>Condition</span><select value={condition} onChange={(e) => setCondition(e.target.value)}>
            <option value="gte">&gt;= (at least)</option>
            <option value="gt">&gt; (above)</option>
            <option value="lte">&lt;= (at most)</option>
            <option value="lt">&lt; (below)</option>
          </select></label>
          <label className="rule-field"><span>Threshold</span><input value={threshold} onChange={(e) => setThreshold(e.target.value)} inputMode="decimal" placeholder="80" /></label>
          <label className="rule-field"><span>Every (seconds)</span><input value={interval} onChange={(e) => setInterval(e.target.value)} inputMode="numeric" placeholder="60" /></label>
          <label className="rule-field"><span>Severity</span><select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="critical">critical</option>
            <option value="warning">warning</option>
            <option value="info">info</option>
          </select></label>
          <label className="rule-field"><span>Streak to fire</span><input value={consecutive} onChange={(e) => setConsecutive(e.target.value)} inputMode="numeric" placeholder="2" /></label>
        </div>
        <div className="rule-form-actions"><span className="rule-form-hint">Example: cpu_usage &gt;= 80 every 60s, streak ×2.</span><button className="primary-button" disabled={busy} onClick={() => void submitRule()}>{busy ? 'Creating…' : 'Create rule'}</button></div>
      </div>
    </section>

    <section className="panel detail-panel history-panel">
      <div className="panel-title-row"><div><div className="section-kicker">HISTORY</div><h2>Recently resolved</h2></div><span className="count-badge">{history.length}</span></div>
      {history.length ? <div className="table-scroll"><table><thead><tr><th>RULE</th><th>RESOURCE</th><th>OBSERVED</th><th>RESOLVED</th></tr></thead><tbody>
        {history.slice(0, 20).map((alert) => <tr key={alert.id}>
          <td><strong>{alert.rule_name || `Rule ${alert.rule_id}`}</strong></td>
          <td><small>{resourceLabel(alert)}</small></td>
          <td>{alert.observed_value}</td>
          <td className="muted-cell">{alert.resolved_at ? formatRelative(alert.resolved_at) : '—'}</td>
        </tr>)}
      </tbody></table></div> : <EmptyInline text="No resolved alerts yet." />}
    </section>
  </>
}
