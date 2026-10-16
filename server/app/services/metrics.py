from app.models import (
    ApiKey,
    ApplicationHealthMetric,
    ContainerMetric,
    DiskMountMetric,
    Host,
    HostMetric,
    ProcessMetric,
)
from app.schemas import MetricsPayload
from sqlalchemy.ext.asyncio import AsyncSession

async def persist_metrics(
    session: AsyncSession,
    payload: MetricsPayload,
    api_key: ApiKey | None = None,
) -> HostMetric:
    machine_id = payload.host.machine_id
    host = None
    if machine_id:
        host = await session.get(Host, machine_id)
        if host is None:
            host = Host(
                machine_id=machine_id,
                first_seen_at=payload.timestamp,
                last_seen_at=payload.timestamp,
            )
            session.add(host)
        # Last-report-wins ownership: a report authenticated with a stored
        # API key claims the host for that key. Env-fallback reports (no
        # stored key) leave ownership untouched.
        if api_key is not None:
            host.owner_key_id = api_key.id
        host.hostname = payload.host.hostname
        host.operating_system = payload.host.operating_system
        host.os_version = payload.host.os_version
        host.architecture = payload.host.architecture
        host.ip_addresses = payload.host.ip_addresses
        host.last_seen_at = payload.timestamp

    metric = HostMetric(
        machine_id=machine_id,
        collected_at=payload.timestamp,
        cpu_timestamp=payload.cpu.timestamp,
        cpu_usage=payload.cpu.cpu_usage,
        cpu_collection_error=payload.cpu.collection_error,
        memory_timestamp=payload.memory.timestamp,
        memory_usage=payload.memory.memory_usage,
        memory_used_bytes=payload.memory.used_bytes,
        memory_available_bytes=payload.memory.available_bytes,
        memory_total_bytes=payload.memory.total_bytes,
        memory_collection_error=payload.memory.collection_error,
        disk_timestamp=payload.disk.timestamp,
        disk_collection_error=payload.disk.collection_error,
        network_timestamp=payload.network.timestamp,
        network_bytes_sent=payload.network.bytes_sent,
        network_bytes_received=payload.network.bytes_received,
        network_bytes_sent_per_second=payload.network.bytes_sent_per_second,
        network_bytes_received_per_second=payload.network.bytes_received_per_second,
        network_collection_error=payload.network.collection_error,
        container_collection_errors=payload.containers.collection_errors,
        application_health_collection_error=payload.application_health.collection_error,
        process_timestamp=payload.processes.timestamp,
        process_enabled=payload.processes.enabled,
        process_collection_errors=payload.processes.collection_errors,
        process_collection_error=payload.processes.collection_error,
        agent_health=payload.agent_health.model_dump(mode="json"),
        disks=[],
        containers=[],
        application_health=[],
        processes=[],
    )
    session.add(metric)
    await session.flush()

    metric.disks.extend(
        DiskMountMetric(
            sampled_at=payload.disk.timestamp or payload.timestamp,
            mount_point=mount.mount_point,
            usage_percent=mount.usage_percent,
            used_bytes=mount.used_bytes,
            free_bytes=mount.free_bytes,
            total_bytes=mount.total_bytes,
            collection_error=mount.collection_error,
        )
        for mount in payload.disk.mounts
    )
    container_timestamp = payload.containers.timestamp or payload.timestamp
    metric.containers.extend(
        ContainerMetric(
            sampled_at=container.timestamp or container_timestamp,
            container_id=container.container_id,
            name=container.name,
            image=container.image,
            status=container.status,
            cpu_usage_percent=container.cpu_usage_percent,
            memory_usage_bytes=container.memory_usage_bytes,
            memory_limit_bytes=container.memory_limit_bytes,
            network_received_bytes=container.network_received_bytes,
            network_transmitted_bytes=container.network_transmitted_bytes,
            block_read_bytes=container.block_read_bytes,
            block_write_bytes=container.block_write_bytes,
            restart_count=container.restart_count,
            uptime_seconds=container.uptime_seconds,
            exit_code=container.exit_code,
            health_status=container.health_status,
            collection_errors=container.collection_errors,
        )
        for container in payload.containers.containers
    )
    application_timestamp = payload.application_health.timestamp or payload.timestamp
    metric.application_health.extend(
        ApplicationHealthMetric(
            sampled_at=endpoint.timestamp or application_timestamp,
            endpoint_name=endpoint.name,
            response_status=endpoint.response_status,
            response_time_seconds=endpoint.response_time_seconds,
            available=endpoint.available,
            error=endpoint.error,
        )
        for endpoint in payload.application_health.endpoints
    )
    if payload.application_health.collection_error and not payload.application_health.endpoints:
        metric.application_health.append(
            ApplicationHealthMetric(
                sampled_at=application_timestamp,
                error=payload.application_health.collection_error,
            )
        )
    process_timestamp = payload.processes.timestamp or payload.timestamp
    metric.processes.extend(
        ProcessMetric(
            sampled_at=process_timestamp,
            pid=item.pid,
            process_name=item.process_name,
            cpu_percent=item.cpu_percent,
            memory_usage_bytes=item.memory_usage_bytes,
            status=item.status,
            collection_error=item.collection_error,
        )
        for item in payload.processes.processes
    )
    return metric
