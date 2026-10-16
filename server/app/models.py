from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    and_,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, foreign, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_users_username", "username"),
        Index("ix_users_email", "email"),
    )

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255))
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_api_keys_prefix", "key_prefix"),)

class Host(Base):
    __tablename__ = "hosts"

    machine_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    hostname: Mapped[str | None] = mapped_column(String(255))
    operating_system: Mapped[str | None] = mapped_column(String(128))
    os_version: Mapped[str | None] = mapped_column(String(512))
    architecture: Mapped[str | None] = mapped_column(String(128))
    ip_addresses: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    owner_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("api_keys.id", ondelete="SET NULL")
    )

    __table_args__ = (Index("ix_hosts_last_seen_at", "last_seen_at"),)

    metrics: Mapped[list["HostMetric"]] = relationship(back_populates="host")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="host")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric: Mapped[str] = mapped_column(String(128), nullable=False)
    condition: Mapped[str] = mapped_column(String(24), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    evaluation_interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    consecutive_breaches_required: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "evaluation_interval_seconds > 0",
            name="ck_alert_rules_positive_evaluation_interval",
        ),
        CheckConstraint(
            "consecutive_breaches_required >= 1",
            name="ck_alert_rules_positive_consecutive_breaches",
        ),
        Index("ix_alert_rules_enabled_metric", "enabled", "metric"),
    )

    alerts: Mapped[list["Alert"]] = relationship(back_populates="rule")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="RESTRICT"), nullable=False
    )
    machine_id: Mapped[str] = mapped_column(
        ForeignKey("hosts.machine_id", ondelete="RESTRICT"), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="host", server_default="host"
    )
    resource_key: Mapped[str] = mapped_column(
        String(1024), nullable=False, default="", server_default=""
    )
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'acknowledged', 'resolved')",
            name="ck_alerts_valid_status",
        ),
        Index("ix_alerts_machine_triggered_at", "machine_id", "triggered_at"),
        Index("ix_alerts_rule_triggered_at", "rule_id", "triggered_at"),
        Index("ix_alerts_status_triggered_at", "status", "triggered_at"),
        Index(
            "uq_alerts_active_rule_machine_resource",
            "rule_id",
            "machine_id",
            "resource_key",
            unique=True,
            postgresql_where=text("status IN ('active', 'acknowledged')"),
        ),
    )

    rule: Mapped[AlertRule] = relationship(back_populates="alerts")
    host: Mapped[Host] = relationship(back_populates="alerts")


class AlertEvaluationState(Base):
    """Per (rule, machine, resource) consecutive-breach counter.

    Persisted so transient过滤 survives restarts and works
    across multiple backend instances (combined with advisory locks).
    """

    __tablename__ = "alert_evaluation_state"

    rule_id: Mapped[int] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"), primary_key=True
    )
    machine_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    resource_key: Mapped[str] = mapped_column(String(1024), primary_key=True, default="")
    consecutive_breaches: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_observed_value: Mapped[float | None] = mapped_column(Float)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_alert_eval_state_rule", "rule_id"),)

class HostMetric(Base):
    __tablename__ = "host_metrics"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # Keep this nullable: the agent schema permits identity collection failures.
    machine_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosts.machine_id", ondelete="SET NULL"), nullable=True
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True, nullable=False, index=True)
    cpu_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cpu_usage: Mapped[float | None] = mapped_column(Float)
    cpu_collection_error: Mapped[str | None] = mapped_column(Text)

    memory_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    memory_usage: Mapped[float | None] = mapped_column(Float)
    memory_used_bytes: Mapped[int | None] = mapped_column(BigInteger)
    memory_available_bytes: Mapped[int | None] = mapped_column(BigInteger)
    memory_total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    memory_collection_error: Mapped[str | None] = mapped_column(Text)

    disk_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disk_collection_error: Mapped[str | None] = mapped_column(Text)

    network_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    network_bytes_sent: Mapped[int | None] = mapped_column(BigInteger)
    network_bytes_received: Mapped[int | None] = mapped_column(BigInteger)
    network_bytes_sent_per_second: Mapped[float | None] = mapped_column(Float)
    network_bytes_received_per_second: Mapped[float | None] = mapped_column(Float)
    network_collection_error: Mapped[str | None] = mapped_column(Text)

    container_collection_errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    application_health_collection_error: Mapped[str | None] = mapped_column(Text)

    process_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    process_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    process_collection_errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    process_collection_error: Mapped[str | None] = mapped_column(Text)

    agent_health: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_host_metrics_machine_time", "machine_id", "collected_at"),
    )

    host: Mapped[Host | None] = relationship(back_populates="metrics")
    disks: Mapped[list["DiskMountMetric"]] = relationship(
        back_populates="host_metric",
        cascade="all, delete-orphan",
        primaryjoin=lambda: and_(
            HostMetric.id == foreign(DiskMountMetric.host_metric_id),
            HostMetric.collected_at == foreign(DiskMountMetric.host_metric_collected_at),
        ),
    )
    containers: Mapped[list["ContainerMetric"]] = relationship(
        back_populates="host_metric",
        cascade="all, delete-orphan",
        primaryjoin=lambda: and_(
            HostMetric.id == foreign(ContainerMetric.host_metric_id),
            HostMetric.collected_at == foreign(ContainerMetric.host_metric_collected_at),
        ),
    )
    application_health: Mapped[list["ApplicationHealthMetric"]] = relationship(
        back_populates="host_metric",
        cascade="all, delete-orphan",
        primaryjoin=lambda: and_(
            HostMetric.id == foreign(ApplicationHealthMetric.host_metric_id),
            HostMetric.collected_at == foreign(ApplicationHealthMetric.host_metric_collected_at),
        ),
    )
    processes: Mapped[list["ProcessMetric"]] = relationship(
        back_populates="host_metric",
        cascade="all, delete-orphan",
        primaryjoin=lambda: and_(
            HostMetric.id == foreign(ProcessMetric.host_metric_id),
            HostMetric.collected_at == foreign(ProcessMetric.host_metric_collected_at),
        ),
    )

class DiskMountMetric(Base):
    __tablename__ = "disk_mount_metrics"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    host_metric_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    host_metric_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mount_point: Mapped[str] = mapped_column(String(1024), nullable=False)
    usage_percent: Mapped[float | None] = mapped_column(Float)
    used_bytes: Mapped[int | None] = mapped_column(BigInteger)
    free_bytes: Mapped[int | None] = mapped_column(BigInteger)
    total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    collection_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "ix_disk_mount_metrics_host_metric_time",
            "host_metric_id",
            "host_metric_collected_at",
            "sampled_at",
        ),
    )

    host_metric: Mapped[HostMetric] = relationship(
        back_populates="disks",
        primaryjoin=lambda: and_(
            foreign(DiskMountMetric.host_metric_id) == HostMetric.id,
            foreign(DiskMountMetric.host_metric_collected_at) == HostMetric.collected_at,
        ),
    )

class ContainerMetric(Base):
    __tablename__ = "container_metrics"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    host_metric_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    host_metric_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    container_id: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str | None] = mapped_column(String(255))
    image: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[str | None] = mapped_column(String(64))
    cpu_usage_percent: Mapped[float | None] = mapped_column(Float)
    memory_usage_bytes: Mapped[int | None] = mapped_column(BigInteger)
    memory_limit_bytes: Mapped[int | None] = mapped_column(BigInteger)
    network_received_bytes: Mapped[int | None] = mapped_column(BigInteger)
    network_transmitted_bytes: Mapped[int | None] = mapped_column(BigInteger)
    block_read_bytes: Mapped[int | None] = mapped_column(BigInteger)
    block_write_bytes: Mapped[int | None] = mapped_column(BigInteger)
    restart_count: Mapped[int | None] = mapped_column(Integer)
    uptime_seconds: Mapped[float | None] = mapped_column(Float)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    health_status: Mapped[str | None] = mapped_column(String(64))
    collection_errors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index(
            "ix_container_metrics_host_metric_time",
            "host_metric_id",
            "host_metric_collected_at",
        ),
        Index("ix_container_metrics_container_time", "container_id", "sampled_at"),
    )

    host_metric: Mapped[HostMetric] = relationship(
        back_populates="containers",
        primaryjoin=lambda: and_(
            foreign(ContainerMetric.host_metric_id) == HostMetric.id,
            foreign(ContainerMetric.host_metric_collected_at) == HostMetric.collected_at,
        ),
    )

class ApplicationHealthMetric(Base):
    __tablename__ = "application_health_metrics"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    host_metric_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    host_metric_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    endpoint_name: Mapped[str | None] = mapped_column(String(255))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_time_seconds: Mapped[float | None] = mapped_column(Float)
    available: Mapped[bool | None] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "ix_application_health_metrics_host_metric_time",
            "host_metric_id",
            "host_metric_collected_at",
            "sampled_at",
        ),
        Index("ix_application_health_metrics_endpoint_time", "endpoint_name", "sampled_at"),
    )

    host_metric: Mapped[HostMetric] = relationship(
        back_populates="application_health",
        primaryjoin=lambda: and_(
            foreign(ApplicationHealthMetric.host_metric_id) == HostMetric.id,
            foreign(ApplicationHealthMetric.host_metric_collected_at) == HostMetric.collected_at,
        ),
    )

class ProcessMetric(Base):
    __tablename__ = "process_metrics"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sampled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    host_metric_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    host_metric_collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    process_name: Mapped[str | None] = mapped_column(String(255))
    cpu_percent: Mapped[float | None] = mapped_column(Float)
    memory_usage_bytes: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str | None] = mapped_column(String(64))
    collection_error: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index(
            "ix_process_metrics_host_metric_time",
            "host_metric_id",
            "host_metric_collected_at",
            "sampled_at",
        ),
        Index("ix_process_metrics_pid_time", "pid", "sampled_at"),
    )

    host_metric: Mapped[HostMetric] = relationship(
        back_populates="processes",
        primaryjoin=lambda: and_(
            foreign(ProcessMetric.host_metric_id) == HostMetric.id,
            foreign(ProcessMetric.host_metric_collected_at) == HostMetric.collected_at,
        ),
    )
