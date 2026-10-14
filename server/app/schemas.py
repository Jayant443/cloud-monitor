from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict, Field, field_validator

class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")

class TimestampedModel(FlexibleModel):
    timestamp: datetime | None = None

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() != timedelta(0)
        ):
            raise ValueError("timestamp must include a UTC timezone")
        return value

class CPUReading(TimestampedModel):
    cpu_usage: float | None = Field(default=None, ge=0)
    collection_error: str | None = None

class MemoryReading(TimestampedModel):
    memory_usage: float | None = Field(default=None, ge=0, le=100)
    used_bytes: int | None = Field(default=None, ge=0)
    available_bytes: int | None = Field(default=None, ge=0)
    total_bytes: int | None = Field(default=None, ge=0)
    collection_error: str | None = None

class DiskMountReading(FlexibleModel):
    mount_point: str
    usage_percent: float | None = Field(default=None, ge=0, le=100)
    used_bytes: int | None = Field(default=None, ge=0)
    free_bytes: int | None = Field(default=None, ge=0)
    total_bytes: int | None = Field(default=None, ge=0)
    collection_error: str | None = None

class DiskReading(TimestampedModel):
    mounts: list[DiskMountReading] = Field(default_factory=list)
    collection_error: str | None = None

class NetworkReading(TimestampedModel):
    bytes_sent: int | None = Field(default=None, ge=0)
    bytes_received: int | None = Field(default=None, ge=0)
    bytes_sent_per_second: float | None = Field(default=None, ge=0)
    bytes_received_per_second: float | None = Field(default=None, ge=0)
    collection_error: str | None = None

class ContainerReadingItem(TimestampedModel):
    container_id: str | None = None
    name: str | None = None
    image: str | None = None
    status: str | None = None
    cpu_usage_percent: float | None = Field(default=None, ge=0)
    memory_usage_bytes: int | None = Field(default=None, ge=0)
    memory_limit_bytes: int | None = Field(default=None, ge=0)
    network_received_bytes: int | None = Field(default=None, ge=0)
    network_transmitted_bytes: int | None = Field(default=None, ge=0)
    block_read_bytes: int | None = Field(default=None, ge=0)
    block_write_bytes: int | None = Field(default=None, ge=0)
    restart_count: int | None = Field(default=None, ge=0)
    uptime_seconds: float | None = Field(default=None, ge=0)
    exit_code: int | None = None
    health_status: str | None = None
    collection_errors: list[str] = Field(default_factory=list)

class ContainerReading(TimestampedModel):
    containers: list[ContainerReadingItem] = Field(default_factory=list)
    collection_errors: list[str] = Field(default_factory=list)
    collection_error: str | None = None

class HostIdentityReading(TimestampedModel):
    machine_id: str | None = None
    hostname: str | None = None
    operating_system: str | None = None
    os_version: str | None = None
    architecture: str | None = None
    ip_addresses: list[str] = Field(default_factory=list)
    collection_errors: list[str] = Field(default_factory=list)
    collection_error: str | None = None

class ApplicationEndpointReading(TimestampedModel):
    name: str
    response_status: int | None = None
    response_time_seconds: float | None = Field(default=None, ge=0)
    available: bool | None = None
    error: str | None = None

class ApplicationHealthReading(TimestampedModel):
    endpoints: list[ApplicationEndpointReading] = Field(default_factory=list)
    collection_error: str | None = None

class ProcessReadingItem(FlexibleModel):
    pid: int
    process_name: str | None = None
    cpu_percent: float | None = Field(default=None, ge=0)
    memory_usage_bytes: int | None = Field(default=None, ge=0)
    status: str | None = None
    collection_error: str | None = None

class ProcessReading(TimestampedModel):
    enabled: bool = False
    processes: list[ProcessReadingItem] = Field(default_factory=list)
    collection_errors: list[str] = Field(default_factory=list)
    collection_error: str | None = None

class RecentCollectorError(FlexibleModel):
    timestamp: datetime
    error: str

class CollectorHealth(FlexibleModel):
    last_successful_collection: datetime | None = None
    last_collection_duration_seconds: float | None = Field(default=None, ge=0)
    consecutive_failures: int = Field(default=0, ge=0)
    recent_errors: list[RecentCollectorError] = Field(default_factory=list)

class AgentHealthReading(TimestampedModel):
    collectors: dict[str, CollectorHealth] = Field(default_factory=dict)

class MetricsPayload(TimestampedModel):
    timestamp: datetime
    cpu: CPUReading
    memory: MemoryReading
    disk: DiskReading
    network: NetworkReading
    containers: ContainerReading
    host: HostIdentityReading
    application_health: ApplicationHealthReading
    processes: ProcessReading
    agent_health: AgentHealthReading

    @field_validator("timestamp")
    @classmethod
    def payload_timestamp_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("timestamp must include a UTC timezone")
        return value

class MetricsAccepted(FlexibleModel):
    status: str = "accepted"

class HealthResponse(FlexibleModel):
    status: str = "ok"
    timestamp: datetime

class ValidationIssue(FlexibleModel):
    loc: list[str | int]
    msg: str
    type: str

class ValidationErrorResponse(FlexibleModel):
    detail: list[ValidationIssue]

class DatabaseReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

class MachineResponse(DatabaseReadModel):
    machine_id: str
    hostname: str | None
    operating_system: str | None
    os_version: str | None
    architecture: str | None
    ip_addresses: list[str]
    first_seen_at: datetime
    last_seen_at: datetime

class MachineListResponse(FlexibleModel):
    items: list[MachineResponse]
    total: int
    limit: int
    offset: int

class DiskMetricResponse(DatabaseReadModel):
    id: int
    sampled_at: datetime
    mount_point: str
    usage_percent: float | None
    used_bytes: int | None
    free_bytes: int | None
    total_bytes: int | None
    collection_error: str | None

class ContainerMetricResponse(DatabaseReadModel):
    id: int
    sampled_at: datetime | None
    container_id: str | None
    name: str | None
    image: str | None
    status: str | None
    cpu_usage_percent: float | None
    memory_usage_bytes: int | None
    memory_limit_bytes: int | None
    network_received_bytes: int | None
    network_transmitted_bytes: int | None
    block_read_bytes: int | None
    block_write_bytes: int | None
    restart_count: int | None
    uptime_seconds: float | None
    exit_code: int | None
    health_status: str | None
    collection_errors: list[str]

class ApplicationHealthMetricResponse(DatabaseReadModel):
    id: int
    sampled_at: datetime | None
    endpoint_name: str | None
    response_status: int | None
    response_time_seconds: float | None
    available: bool | None
    error: str | None

class ProcessMetricResponse(DatabaseReadModel):
    id: int
    sampled_at: datetime | None
    pid: int
    process_name: str | None
    cpu_percent: float | None
    memory_usage_bytes: int | None
    status: str | None
    collection_error: str | None

class MetricSnapshotResponse(DatabaseReadModel):
    id: int
    machine_id: str | None
    collected_at: datetime
    cpu_timestamp: datetime | None
    cpu_usage: float | None
    cpu_collection_error: str | None
    memory_timestamp: datetime | None
    memory_usage: float | None
    memory_used_bytes: int | None
    memory_available_bytes: int | None
    memory_total_bytes: int | None
    memory_collection_error: str | None
    disk_timestamp: datetime | None
    disk_collection_error: str | None
    disks: list[DiskMetricResponse]
    network_timestamp: datetime | None
    network_bytes_sent: int | None
    network_bytes_received: int | None
    network_bytes_sent_per_second: float | None
    network_bytes_received_per_second: float | None
    network_collection_error: str | None
    container_collection_errors: list[str]
    containers: list[ContainerMetricResponse]
    application_health_collection_error: str | None
    application_health: list[ApplicationHealthMetricResponse]
    process_timestamp: datetime | None = None
    process_enabled: bool = False
    process_collection_errors: list[str] = Field(default_factory=list)
    process_collection_error: str | None = None
    agent_health: dict | None = None
    processes: list[ProcessMetricResponse] = Field(default_factory=list)

class LatestMetricsResponse(FlexibleModel):
    machine_id: str
    metrics: MetricSnapshotResponse | None

class MetricHistoryResponse(FlexibleModel):
    machine_id: str
    items: list[MetricSnapshotResponse]
    total: int
    limit: int
    offset: int

class LatestContainerResponse(DatabaseReadModel):
    machine_id: str | None
    host_metric_id: int
    sampled_at: datetime
    id: int
    container_id: str | None
    name: str | None
    image: str | None
    status: str | None
    cpu_usage_percent: float | None
    memory_usage_bytes: int | None
    memory_limit_bytes: int | None
    network_received_bytes: int | None
    network_transmitted_bytes: int | None
    block_read_bytes: int | None
    block_write_bytes: int | None
    restart_count: int | None
    uptime_seconds: float | None
    exit_code: int | None
    health_status: str | None
    collection_errors: list[str]

class LatestContainerListResponse(FlexibleModel):
    items: list[LatestContainerResponse]
    total: int
    limit: int
    offset: int

class ApplicationHealthResponse(FlexibleModel):
    machine_id: str
    sampled_at: datetime | None
    collection_error: str | None
    items: list[ApplicationHealthMetricResponse]

class ApplicationHealthHistoryResponse(FlexibleModel):
    machine_id: str
    items: list[ApplicationHealthMetricResponse]
    total: int
    limit: int
    offset: int

# ---- Alerting ----

SUPPORTED_ALERT_METRICS = (
    "cpu_usage",
    "memory_usage",
    "disk_usage",
    "host_inactivity_seconds",
    "container_stopped",
    "app_health_failed",
)
SUPPORTED_ALERT_CONDITIONS = ("gt", "gte", "lt", "lte")
SUPPORTED_ALERT_SEVERITIES = ("critical", "warning", "info")
SUPPORTED_ALERT_STATUSES = ("active", "acknowledged", "resolved")

class AlertRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    metric: str = Field(pattern="^(cpu_usage|memory_usage|disk_usage|host_inactivity_seconds|container_stopped|app_health_failed)$")
    condition: str = Field(default="gte", pattern="^(gt|gte|lt|lte)$")
    threshold: float = Field(ge=0)
    evaluation_interval_seconds: int = Field(default=60, ge=10, le=86400)
    severity: str = Field(default="warning", pattern="^(critical|warning|info)$")
    enabled: bool = True
    consecutive_breaches_required: int = Field(default=1, ge=1, le=20)

    @field_validator("threshold")
    @classmethod
    def threshold_range_for_percent_metrics(cls, value: float, info) -> float:
        metric = (info.data or {}).get("metric")
        if metric in {"cpu_usage", "memory_usage", "disk_usage"} and not 0 <= value <= 100:
            raise ValueError("threshold must be between 0 and 100 for usage metrics")
        return value

class AlertRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    metric: str | None = Field(default=None, pattern="^(cpu_usage|memory_usage|disk_usage|host_inactivity_seconds|container_stopped|app_health_failed)$")
    condition: str | None = Field(default=None, pattern="^(gt|gte|lt|lte)$")
    threshold: float | None = Field(default=None, ge=0)
    evaluation_interval_seconds: int | None = Field(default=None, ge=10, le=86400)
    severity: str | None = Field(default=None, pattern="^(critical|warning|info)$")
    enabled: bool | None = None
    consecutive_breaches_required: int | None = Field(default=None, ge=1, le=20)

class AlertRuleResponse(DatabaseReadModel):
    id: int
    name: str
    metric: str
    condition: str
    threshold: float
    evaluation_interval_seconds: int
    severity: str
    enabled: bool
    consecutive_breaches_required: int
    last_evaluated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    active_alert_count: int = 0

class AlertRuleListResponse(FlexibleModel):
    items: list[AlertRuleResponse]
    total: int
    limit: int
    offset: int

class AlertResponse(DatabaseReadModel):
    id: int
    rule_id: int
    machine_id: str
    resource_type: str
    resource_key: str
    observed_value: float
    status: str
    triggered_at: datetime
    resolved_at: datetime | None
    rule_name: str | None = None
    rule_metric: str | None = None
    rule_severity: str | None = None

class AlertListResponse(FlexibleModel):
    items: list[AlertResponse]
    total: int
    limit: int
    offset: int

class AlertSummaryResponse(FlexibleModel):
    active: int
    acknowledged: int
    critical_active: int
