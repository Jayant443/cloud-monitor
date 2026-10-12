import { formatBytes, percent } from '../lib/format'
import type { ReactNode } from 'react'

export type IconName = 'grid' | 'server' | 'activity' | 'box' | 'pulse' | 'refresh' | 'arrow' | 'chevron'

const iconPaths: Record<IconName, string> = {
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z',
  server: 'M4 4h16v6H4zM4 14h16v6H4zM7 7h.01M7 17h.01M11 7h6M11 17h6',
  activity: 'M3 12h4l3-8 4 16 3-8h4',
  box: 'm12 3 9 5-9 5-9-5 9-5ZM3 8v8l9 5 9-5V8M12 13v8',
  pulse: 'M4 12a8 8 0 1 0 16 0 8 8 0 0 0-16 0Zm8-4v4l3 2',
  refresh: 'M20 7v5h-5M4 17v-5h5m10-2a7 7 0 0 0-12-3L4 12m16 0-3 5a7 7 0 0 1-12-3',
  arrow: 'M5 12h14m-6-6 6 6-6 6',
  chevron: 'm9 18 6-6-6-6',
}

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={iconPaths[name]} /></svg>
}

export function StatCard({ label, value, note, icon, tone }: { label: string; value: string; note: string; icon: IconName; tone: string }) {
  return <article className="stat-card"><div className={`stat-icon ${tone}`}><Icon name={icon} /></div><span className="stat-label">{label}</span><strong className="stat-value">{value}</strong><span className="stat-note">{note}</span></article>
}

export function Sparkline({ values, color, unit = '%' }: { values: (number | null)[]; color: string; unit?: string }) {
  const valid = values.filter((value): value is number => value != null && Number.isFinite(value))
  if (!valid.length) return <div className="chart-empty">No history in this period</div>
  const width = 500, height = 128, pad = 8
  const min = Math.min(...valid), max = Math.max(...valid)
  const span = max - min || Math.max(Math.abs(max) * 0.12, 1)
  const points = values.map((value, index) => value == null ? null : `${pad + (index / Math.max(1, values.length - 1)) * (width - pad * 2)},${height - pad - ((value - min) / span) * (height - pad * 2)}`).filter((value): value is string => value !== null)
  const path = points.map((point, index) => `${index ? 'L' : 'M'}${point}`).join(' ')
  const last = points[points.length - 1]?.split(',').map(Number)
  const display = valid[valid.length - 1]
  return <div className="spark-wrap">
    <div className="chart-current"><strong>{unit === '%' ? percent(display) : `${formatBytes(display)}/s`}</strong><span>latest</span></div>
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`Metric history, latest ${display}${unit}`}>
      {[0.25, 0.5, 0.75].map((fraction) => <line key={fraction} x1="0" x2={width} y1={height * fraction} y2={height * fraction} className="chart-gridline" />)}
      <path d={path} fill="none" stroke={color} strokeWidth="3" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
      {last && <circle cx={last[0]} cy={last[1]} r="4" fill={color} />}
    </svg>
    <div className="chart-foot"><span>{values.length > 1 ? 'Older' : 'Latest sample'}</span><span>{values.length > 1 ? 'Now' : ''}</span></div>
  </div>
}

export function ChartCard({ title, detail, values, color, unit, icon }: { title: string; detail: string; values: (number | null)[]; color: string; unit?: string; icon: IconName }) {
  return <article className="panel chart-card"><div className="panel-heading"><div className="chart-heading-icon"><Icon name={icon} /></div><div><h3>{title}</h3><p>{detail}</p></div><button className="icon-button" title="Metric history"><Icon name="arrow" size={16} /></button></div><Sparkline values={values} color={color} unit={unit} /></article>
}

export function MetricInline({ value }: { value: number | null }) {
  return <div className="metric-inline"><span className="mini-track"><span style={{ width: `${Math.min(value ?? 0, 100)}%` }} /></span><strong>{percent(value)}</strong></div>
}

export function EmptyInline({ text }: { text: string }) { return <div className="empty-inline">{text}</div> }

export function PanelHeading({ kicker, title, trailing }: { kicker: string; title: string; trailing?: ReactNode }) {
  return <div className="panel-title-row"><div><div className="section-kicker">{kicker}</div><h2>{title}</h2></div>{trailing}</div>
}
