export type AlertMetric =
  | 'cpu_usage'
  | 'memory_usage'
  | 'disk_usage'
  | 'host_inactivity_seconds'
  | 'container_stopped'
  | 'app_health_failed'

export type AlertCondition = 'gt' | 'gte' | 'lt' | 'lte'
export type AlertSeverity = 'critical' | 'warning' | 'info'
export type AlertStatus = 'active' | 'acknowledged' | 'resolved'

export type AlertRule = {
  id: number
  name: string
  metric: string
  condition: string
  threshold: number
  evaluation_interval_seconds: number
  severity: string
  enabled: boolean
  consecutive_breaches_required: number
  last_evaluated_at: string | null
  created_at: string
  updated_at: string
  active_alert_count: number
}

export type AlertRulePage = { items: AlertRule[]; total: number; limit: number; offset: number }

export type AlertItem = {
  id: number
  rule_id: number
  machine_id: string
  resource_type: string
  resource_key: string
  observed_value: number
  status: string
  triggered_at: string
  resolved_at: string | null
  rule_name: string | null
  rule_metric: string | null
  rule_severity: string | null
}

export type AlertPage = { items: AlertItem[]; total: number; limit: number; offset: number }

export type AlertSummary = { active: number; acknowledged: number; critical_active: number }
