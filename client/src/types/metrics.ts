export type Machine = {
  machine_id: string
  hostname: string | null
  operating_system: string | null
  os_version: string | null
  architecture: string | null
  ip_addresses: string[]
  first_seen_at: string
  last_seen_at: string
}

export type Page<T> = { items: T[]; total: number; limit: number; offset: number }

export type Disk = {
  id: number
  sampled_at: string
  mount_point: string
  usage_percent: number | null
  used_bytes: number | null
  free_bytes: number | null
  total_bytes: number | null
  collection_error: string | null
}

export type Container = {
  id: number
  machine_id: string | null
  host_metric_id: number
  sampled_at: string
  container_id: string | null
  name: string | null
  image: string | null
  status: string | null
  cpu_usage_percent: number | null
  memory_usage_bytes: number | null
  memory_limit_bytes: number | null
  network_received_bytes: number | null
  network_transmitted_bytes: number | null
  block_read_bytes: number | null
  block_write_bytes: number | null
  restart_count: number | null
  uptime_seconds: number | null
  exit_code: number | null
  health_status: string | null
  collection_errors: string[]
}

export type AppCheck = {
  id: number
  sampled_at: string | null
  endpoint_name: string | null
  response_status: number | null
  response_time_seconds: number | null
  available: boolean | null
  error: string | null
}

export type Snapshot = {
  id: number
  machine_id: string | null
  collected_at: string
  cpu_timestamp: string | null
  cpu_usage: number | null
  cpu_collection_error: string | null
  memory_timestamp: string | null
  memory_usage: number | null
  memory_used_bytes: number | null
  memory_available_bytes: number | null
  memory_total_bytes: number | null
  memory_collection_error: string | null
  disk_timestamp: string | null
  disk_collection_error: string | null
  disks: Disk[]
  network_timestamp: string | null
  network_bytes_sent: number | null
  network_bytes_received: number | null
  network_bytes_sent_per_second: number | null
  network_bytes_received_per_second: number | null
  network_collection_error: string | null
  container_collection_errors: string[]
  containers: Container[]
  application_health_collection_error: string | null
  application_health: AppCheck[]
}

export type Latest = { machine_id: string; metrics: Snapshot | null }
export type History = Page<Snapshot> & { machine_id: string }
export type AppHealth = { machine_id: string; sampled_at: string | null; collection_error: string | null; items: AppCheck[] }
export type AppHistory = Page<AppCheck> & { machine_id: string }
export type Period = '1h' | '24h' | '7d'
