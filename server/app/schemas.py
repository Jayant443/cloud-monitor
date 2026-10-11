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
