from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

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

    metrics: Mapped[list["HostMetric"]] = relationship(back_populates="host")

class HostMetric(Base):
    __tablename__ = "host_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    machine_id: Mapped[str | None] = mapped_column(
        ForeignKey("hosts.machine_id", ondelete="SET NULL"), index=True
    )
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

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

    host: Mapped[Host | None] = relationship(back_populates="metrics")
    disks: Mapped[list["DiskMountMetric"]] = relationship(
        back_populates="host_metric", cascade="all, delete-orphan"
    )
    containers: Mapped[list["ContainerMetric"]] = relationship(
        back_populates="host_metric", cascade="all, delete-orphan"
    )
    application_health: Mapped[list["ApplicationHealthMetric"]] = relationship(
        back_populates="host_metric", cascade="all, delete-orphan"
    )

class DiskMountMetric(Base):
    __tablename__ = "disk_mount_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    host_metric_id: Mapped[int] = mapped_column(
        ForeignKey("host_metrics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mount_point: Mapped[str] = mapped_column(String(1024), nullable=False)
    usage_percent: Mapped[float | None] = mapped_column(Float)
    used_bytes: Mapped[int | None] = mapped_column(BigInteger)
    free_bytes: Mapped[int | None] = mapped_column(BigInteger)
    total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    collection_error: Mapped[str | None] = mapped_column(Text)

    host_metric: Mapped[HostMetric] = relationship(back_populates="disks")

class ContainerMetric(Base):
    __tablename__ = "container_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    host_metric_id: Mapped[int] = mapped_column(
        ForeignKey("host_metrics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sampled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    container_id: Mapped[str | None] = mapped_column(String(128), index=True)
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

    host_metric: Mapped[HostMetric] = relationship(back_populates="containers")

class ApplicationHealthMetric(Base):
    __tablename__ = "application_health_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    host_metric_id: Mapped[int] = mapped_column(
        ForeignKey("host_metrics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sampled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    endpoint_name: Mapped[str | None] = mapped_column(String(255), index=True)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_time_seconds: Mapped[float | None] = mapped_column(Float)
    available: Mapped[bool | None] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text)

    host_metric: Mapped[HostMetric] = relationship(back_populates="application_health")
