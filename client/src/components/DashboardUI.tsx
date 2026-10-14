import { formatBytes, percent } from '../lib/format'
import { useRef, useState } from 'react'
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

export function StatCard({ label, value, note, sub, icon, tone }: { label: string; value: string; note: string; sub?: string; icon: IconName; tone: string }) {
  return <article className="stat-card"><div className={`stat-icon ${tone}`}><Icon name={icon} /></div><span className="stat-label">{label}</span><strong className="stat-value">{value}</strong>{sub && <span className="stat-host">{sub}</span>}<span className="stat-note">{note}</span></article>
}

export function Sparkline({ values, labels, color, unit = '%', tall = false, interactive = false, zeroBased = false, axes = false }: { values: (number | null)[]; labels?: string[]; color: string; unit?: string; tall?: boolean; interactive?: boolean; zeroBased?: boolean; axes?: boolean }) {
  const valid = values.filter((value): value is number => value != null && Number.isFinite(value))
  const [hover, setHover] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  if (!valid.length) return <div className="chart-empty">No history in this period</div>
  const width = 500, height = tall ? 300 : 128, pad = 8
  const min = zeroBased ? 0 : Math.min(...valid)
  const max = Math.max(...valid)
  const domainMax = zeroBased && unit === '%' ? 100 : max
  const span = domainMax - min || Math.max(Math.abs(domainMax) * 0.12, 1)
  const xFor = (index: number) => pad + (index / Math.max(1, values.length - 1)) * (width - pad * 2)
  const yFor = (value: number) =>
    Math.max(0, Math.min(height, height - pad - ((value - min) / span) * (height - pad * 2)))
  const points = values.map((value, index) => value == null ? null : `${xFor(index)},${yFor(value)}`).filter((value): value is string => value !== null)
  const path = points.map((point, index) => `${index ? 'L' : 'M'}${point}`).join(' ')
  const last = points[points.length - 1]?.split(',').map(Number)
  const display = valid[valid.length - 1]
  const formatValue = (value: number | null) =>
    value == null ? 'No data' : unit === '%' ? percent(value) : `${formatBytes(value)}/s`
  const handleMove = (event: React.MouseEvent<SVGRectElement>) => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect || values.length < 1) return
    const x = ((event.clientX - rect.left) / rect.width) * width
    const index = Math.round(((x - pad) / (width - pad * 2)) * (values.length - 1))
    setHover(Math.max(0, Math.min(values.length - 1, index)))
  }
  const hoverValue = hover == null ? null : values[hover]
  const hoverX = hover == null ? null : xFor(hover)
  const hoverY = hoverValue == null ? null : yFor(hoverValue)
  const tipLeft = hoverX == null ? 0 : Math.max(12, Math.min(88, (hoverX / width) * 100))
  const tipTop = hoverY == null ? 0 : (hoverY / height) * 100
  const lastX = last ? (last[0] / width) * 100 : null
  const lastY = last ? (last[1] / height) * 100 : null

  const showAxes = axes && (unit === '%' || max > 0)
  const tickValues = showAxes
    ? unit === '%'
      ? [0, 25, 50, 75, 100]
      : [0, max * 0.25, max * 0.5, max * 0.75, max]
    : []
  const formatTick = (tick: number) =>
    unit === '%' ? `${tick.toFixed(tick >= 10 ? 0 : 1)}%` : formatBytes(tick)
  const bottomPct = (tick: number) => (((tick - min) / span) * (height - pad * 2) + pad) / height * 100
  const midLabel = labels?.[Math.floor((labels.length - 1) / 2)] ?? (values.length > 2 ? `Sample ${Math.floor(values.length / 2) + 1}` : null)
  const stage = <div className="spark-stage">
    <svg ref={svgRef} className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img" aria-label={`Metric history, latest ${display}${unit}`}>
      {showAxes
        ? tickValues.slice(1).map((tick) => <line key={tick} x1="0" x2={width} y1={yFor(tick)} y2={yFor(tick)} className="chart-gridline" />)
        : [0.25, 0.5, 0.75].map((fraction) => <line key={fraction} x1="0" x2={width} y1={height * fraction} y2={height * fraction} className="chart-gridline" />)}
      <path d={path} fill="none" stroke={color} strokeWidth="3" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
      {interactive && hoverX != null && hoverY != null &&
        <line x1={hoverX} x2={hoverX} y1={0} y2={height} className="spark-crosshair" />}
      {interactive && <rect x={0} y={0} width={width} height={height} fill="transparent" style={{ cursor: 'crosshair' }} onMouseMove={handleMove} onMouseLeave={() => setHover(null)} />}
    </svg>
    {lastX != null && lastY != null && <span className="spark-dot" style={{ left: `${lastX}%`, top: `${lastY}%`, background: color }} />}
    {interactive && hoverX != null && hoverY != null && <span className="spark-dot spark-dot-hover" style={{ left: `${(hoverX / width) * 100}%`, top: `${(hoverY / height) * 100}%`, background: color }} />}
    {interactive && hover != null && <div className={`spark-tip${tipTop < 30 ? ' spark-tip-below' : ''}`} style={{ left: `${tipLeft}%`, top: `${tipTop}%` }}><strong>{formatValue(hoverValue ?? null)}</strong><span>{labels?.[hover] ?? `Sample ${hover + 1}`}</span></div>}
  </div>
  return <div className="spark-wrap">
    {showAxes ? <div className="spark-framed">
      <div className="spark-yaxis" aria-hidden="true">{tickValues.slice().reverse().map((tick) => <span key={tick} style={{ bottom: `${bottomPct(tick)}%` }}>{formatTick(tick)}</span>)}</div>
      <div className="spark-main">{stage}
        <div className="spark-xaxis" aria-hidden="true"><span>{labels?.[0] ?? 'Older'}</span>{midLabel && <span>{midLabel}</span>}<span>{labels?.[labels.length - 1] ?? 'Now'}</span></div>
      </div>
    </div> : stage}
    <div className="chart-foot"><span>{values.length > 1 ? 'Older' : 'Latest sample'}</span><span>{values.length > 1 ? 'Now' : ''}</span></div>
  </div>
}

export function ChartCard({ title, detail, values, labels, color, unit, icon }: { title: string; detail: string; values: (number | null)[]; labels?: string[]; color: string; unit?: string; icon: IconName }) {
  const [expanded, setExpanded] = useState(false)
  const valid = values.filter((value): value is number => value != null && Number.isFinite(value))
  const formatValue = (value: number | null) =>
    value == null ? '—' : unit === '%' ? percent(value) : `${formatBytes(value)}/s`
  const latest = valid.length ? valid[valid.length - 1] : null
  const min = valid.length ? Math.min(...valid) : null
  const max = valid.length ? Math.max(...valid) : null
  const avg = valid.length ? valid.reduce((sum, value) => sum + value, 0) / valid.length : null
  const rows = values.map((value, index) => ({ value, label: labels?.[index] ?? `#${index + 1}` }))
    .slice(-12).reverse()
  const latestText = latest == null ? '—' : unit === '%' ? percent(latest) : `${formatBytes(latest)}/s`
  return <article className={`panel chart-card${expanded ? ' expanded' : ''}`}>
    <div className="panel-heading"><div className="chart-heading-icon"><Icon name={icon} /></div><div><h3>{title}</h3><p>{detail}</p></div><div className="chart-latest"><strong>{latestText}</strong></div><button className={`icon-button${expanded ? ' open' : ''}`} title={expanded ? 'Collapse metric history' : 'Expand metric history'} aria-expanded={expanded} aria-label={expanded ? `Collapse ${title} history` : `Expand ${title} history`} onClick={() => setExpanded((open) => !open)}><Icon name="arrow" size={16} /></button></div>
    <Sparkline values={values} color={color} unit={unit} />
    <div className="chart-expand" aria-hidden={!expanded}>
      <div className="chart-expand-inner">
        <Sparkline values={values} labels={labels} color={color} unit={unit} tall interactive zeroBased axes />
        <div className="chart-stats">
          <div><span>Latest</span><strong>{latest == null ? '—' : formatValue(latest)}</strong></div>
          <div><span>Average</span><strong>{avg == null ? '—' : formatValue(avg)}</strong></div>
          <div><span>Minimum</span><strong>{min == null ? '—' : formatValue(min)}</strong></div>
          <div><span>Maximum</span><strong>{max == null ? '—' : formatValue(max)}</strong></div>
        </div>
        {rows.length ? <div className="table-scroll"><table className="chart-history-table"><thead><tr><th>TIME</th><th>VALUE</th></tr></thead><tbody>
          {rows.map((row, index) => <tr key={`${row.label}-${index}`}><td className="muted-cell">{row.label}</td><td>{formatValue(row.value)}</td></tr>)}
        </tbody></table></div> : <div className="chart-empty">No history in this period</div>}
      </div>
    </div>
  </article>
}

export function MetricInline({ value }: { value: number | null }) {
  return <div className="metric-inline"><span className="mini-track"><span style={{ width: `${Math.min(value ?? 0, 100)}%` }} /></span><strong>{percent(value)}</strong></div>
}

export function EmptyInline({ text }: { text: string }) { return <div className="empty-inline">{text}</div> }

export function PanelHeading({ kicker, title, trailing }: { kicker: string; title: string; trailing?: ReactNode }) {
  return <div className="panel-title-row"><div><div className="section-kicker">{kicker}</div><h2>{title}</h2></div>{trailing}</div>
}
