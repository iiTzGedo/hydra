"""Agent installation and reporting endpoints.

Supports multiple distribution methods:
- binary: Pre-compiled binaries from S3/Garage (default, fastest)
- obs: Bundled source from S3/Garage (Object Storage)
- local: Bundled source from local filesystem

Also provides an event reporting endpoint for agents to emit
notifications about failures and state changes.
"""

import re
from collections.abc import AsyncIterator
from typing import Any, Literal

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from hydra.api.v1 import __version__
from hydra.api.v1.core.deps import CurrentUser, MongoDBDep, RedisDep, StorageServiceDep
from hydra.api.v1.services.install import get_install_service
from hydra.api.v1.services.storage import StorageSource

router = APIRouter(prefix="/agent", tags=["Agent Management"])
logger = structlog.get_logger(__name__)

VERSION_PATTERN = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9]+)?$|^latest$')

SUPPORTED_TARGETS = {
    "hydra-agent-linux-amd64": {"os": "linux", "arch": "amd64", "target": "linux-amd64"},
    "hydra-agent-linux-arm64": {"os": "linux", "arch": "arm64", "target": "linux-arm64"},
    "hydra-agent-linux-armv7": {"os": "linux", "arch": "armv7", "target": "linux-armv7"},
    "hydra-agent-darwin-amd64": {"os": "darwin", "arch": "amd64", "target": "darwin-amd64"},
    "hydra-agent-darwin-arm64": {"os": "darwin", "arch": "arm64", "target": "darwin-arm64"},
    "hydra-agent-freebsd-amd64": {"os": "freebsd", "arch": "amd64", "target": "freebsd-amd64"},
    "hydra-agent-windows-amd64": {"os": "windows", "arch": "amd64", "target": "windows-amd64"},
}


def validate_version(version: str) -> str:
    """Validate version parameter to prevent path traversal.

    Args:
        version: Version string to validate.

    Returns:
        The validated version string.

    Raises:
        HTTPException 400: Invalid version format.
    """
    if not VERSION_PATTERN.match(version):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_VERSION",
                    "message": f"Invalid version format: '{version}'",
                    "details": {"pattern": "X.Y.Z or X.Y.Z-suffix or latest"},
                }
            },
        )
    return version


def is_windows_user_agent(user_agent: str | None) -> bool:
    """Check if the user agent indicates a Windows client.

    Args:
        user_agent: HTTP User-Agent header value.

    Returns:
        True if the user agent indicates Windows (PowerShell, etc.).
    """
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(marker in ua_lower for marker in [
        "powershell",
        "windowspowershell",
        "windows nt",
        "win64",
        "win32",
    ])


@router.get(
    "/install",
    summary="Installation Script",
    description="Returns an installation script for agent deployment. Auto-detects Windows clients via User-Agent and returns PowerShell script.",
    response_class=Response,
    responses={
        200: {
            "description": "Installation script (bash for Unix, PowerShell for Windows)",
            "content": {
                "text/x-shellscript": {},
                "text/plain": {},
            },
        }
    },
)
async def get_install_script(
    request: Request,
    arch: Literal["amd64", "arm64", "armv7"] | None = Query(
        default=None, description="Target architecture (auto-detect if not specified)"
    ),
    os: Literal["linux", "darwin", "freebsd", "windows"] | None = Query(
        default=None, description="Target OS (auto-detect from User-Agent if not specified)"
    ),
    source: StorageSource = Query(
        default=StorageSource.BINARY,
        description="Storage source: binary (pre-compiled), obs (S3 bundles), local (local bundles)",
    ),
    version: str = Query(default="latest", description="Agent version to install"),
) -> Response:
    """Generate and return the agent installation script.

    The API URL in the generated script is derived from the request URL.
    Auto-detects Windows clients and returns PowerShell; otherwise returns bash.

    Args:
        request: HTTP request for URL derivation.
        arch: Target architecture (auto-detect if not specified).
        os: Target OS (auto-detect from User-Agent if not specified).
        source: Storage source for agent distribution.
        version: Agent version to install.

    Returns:
        Installation script appropriate for the target platform.

    Raises:
        HTTPException 400: Binary source not supported for Unix /agent/install.
    """
    api_url = str(request.base_url).rstrip("/")
    if request.url.path.startswith("/api/v1"):
        api_url = f"{api_url.rsplit('/api/v1', 1)[0]}/api/v1"
    else:
        api_url = f"{api_url}/api/v1"

    version = validate_version(version)

    user_agent = request.headers.get("user-agent")
    is_windows = os == "windows" or (os is None and is_windows_user_agent(user_agent))

    install_service = get_install_service()

    if is_windows:
        script = install_service.generate_powershell_script(api_url, source=StorageSource.BINARY, version=version)

        logger.info(
            "install_script_generated",
            api_url=api_url,
            requested_arch=arch,
            requested_os=os or "windows (auto-detected)",
            source="binary",
            version=version,
            script_type="powershell",
            user_agent=user_agent,
        )

        return Response(
            content=script,
            media_type="text/plain",
            headers={
                "Content-Disposition": 'attachment; filename="hydra-install.ps1"',
                "X-Hydra-Version": __version__,
                "X-Script-Type": "powershell",
            },
        )

    if source == StorageSource.BINARY:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "UNSUPPORTED_SOURCE",
                    "message": "Binary source is not supported for Unix /agent/install. Use ?source=local or ?source=obs for source bundle installation, or download binary directly via /agent/download.",
                    "details": {"allowed_sources": ["local", "obs"]},
                }
            },
        )

    script = install_service.generate_bash_script(api_url, source=source, version=version)

    logger.info(
        "install_script_generated",
        api_url=api_url,
        requested_arch=arch,
        requested_os=os,
        source=source.value,
        version=version,
        script_type="bash",
    )

    return Response(
        content=script,
        media_type="text/x-shellscript",
        headers={
            "Content-Disposition": 'attachment; filename="hydra-install.sh"',
            "X-Hydra-Version": __version__,
            "X-Script-Type": "bash",
        },
    )


@router.get(
    "/download",
    summary="Download Agent Bundle or Binary",
    description="Download agent bundle (source) or binary based on storage source.",
    response_class=Response,
    response_model=None,
    responses={
        200: {
            "description": "Agent bundle or binary file",
            "content": {
                "application/octet-stream": {},
                "application/zip": {},
            },
        },
        404: {"description": "Version not found"},
        503: {"description": "Storage not configured"},
    },
)
async def download_agent(
    storage: StorageServiceDep,
    source: StorageSource = Query(
        default=StorageSource.BINARY,
        description="Storage source: binary (pre-compiled), obs (S3 bundles), local (local bundles)",
    ),
    version: str = Query(default="latest", description="Agent version"),
    target: str | None = Query(
        default=None,
        description="Target architecture (required for source=binary, e.g., linux-amd64)",
    ),
) -> Response:
    """Download agent binary or source bundle.

    For source=binary: Downloads pre-compiled binary for specified target.
    For source=obs or source=local: Downloads bundled source code (zip).

    Args:
        storage: Storage service dependency.
        source: Storage source for agent distribution.
        version: Agent version to download.
        target: Target architecture (required for binary downloads).

    Returns:
        Streaming response with agent binary or bundle.

    Raises:
        HTTPException 400: Target required for binary downloads or invalid target.
        HTTPException 404: Version not found.
        HTTPException 503: Storage not configured or unavailable.
    """
    from hydra.api.v1.services.storage import (
        ObjectNotFoundError,
        StorageNotConfiguredError,
        StorageUnavailableError,
    )

    version = validate_version(version)

    if storage is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "STORAGE_NOT_CONFIGURED",
                    "message": "No storage backend is configured.",
                }
            },
        )

    if not storage.is_source_available(source):
        available = [s.value for s in storage.get_available_sources()]
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SOURCE_NOT_CONFIGURED",
                    "message": f"Storage source '{source.value}' is not configured.",
                    "details": {"available_sources": available},
                }
            },
        )

    try:
        backend = storage.get_backend(source)

        if source == StorageSource.BINARY:
            if not target:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "TARGET_REQUIRED",
                            "message": "Target architecture is required for binary downloads",
                            "details": {
                                "available_targets": [
                                    t["target"] for t in SUPPORTED_TARGETS.values()
                                ]
                            },
                        }
                    },
                )

            valid_targets = {t["target"] for t in SUPPORTED_TARGETS.values()}
            if target not in valid_targets:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "INVALID_TARGET",
                            "message": f"Invalid target: {target}",
                            "details": {"available_targets": list(valid_targets)},
                        }
                    },
                )

            resolved_version = version
            if version == "latest":
                resolved_version = await backend.get_latest_version(target)  # type: ignore[assignment]
                if not resolved_version:
                    raise HTTPException(
                        status_code=404,
                        detail={
                            "error": {
                                "code": "NO_VERSIONS_AVAILABLE",
                                "message": f"No versions available for target {target}",
                            }
                        },
                    )

            binary_name = "hydra-agent.exe" if target.startswith("windows") else "hydra-agent"
            object_key = f"agents/{target}/{resolved_version}/{binary_name}"
            filename = f"hydra-agent-{target}" + (".exe" if target.startswith("windows") else "")
            media_type = "application/octet-stream"

        else:
            resolved_version = version
            if version == "latest":
                resolved_version = await backend.get_latest_version()  # type: ignore[assignment]
                if not resolved_version:
                    raise HTTPException(
                        status_code=404,
                        detail={
                            "error": {
                                "code": "NO_VERSIONS_AVAILABLE",
                                "message": "No bundle versions available",
                            }
                        },
                    )

            object_key = backend.get_bundle_key(resolved_version)  # type: ignore[attr-defined]
            filename = f"hydra-agent-{resolved_version}.zip"
            media_type = "application/zip"

        metadata = await backend.get_object_metadata(object_key)

        logger.info(
            "agent_download",
            source=source.value,
            version=resolved_version,
            target=target,
            key=object_key,
            size=metadata.get("size"),
        )

        async def stream_file() -> AsyncIterator[bytes]:
            async for chunk in backend.get_object_stream(object_key):  # type: ignore[attr-defined]
                yield chunk

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Hydra-Version": resolved_version,
            "X-Storage-Source": source.value,
        }
        if metadata.get("size"):
            headers["Content-Length"] = str(metadata["size"])
        if metadata.get("sha256"):
            headers["X-Checksum-SHA256"] = metadata["sha256"]

        return StreamingResponse(
            stream_file(),
            media_type=media_type,
            headers=headers,
        )

    except StorageNotConfiguredError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SOURCE_NOT_CONFIGURED",
                    "message": str(e),
                }
            },
        )
    except ObjectNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Version {version} not found",
                    "details": {
                        "source": source.value,
                        "version": version,
                        "target": target,
                    },
                }
            },
        )
    except StorageUnavailableError as e:
        logger.error(
            "storage_unavailable",
            source=source.value,
            version=version,
            error=str(e),
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "STORAGE_UNAVAILABLE",
                    "message": "Storage is temporarily unavailable",
                }
            },
        )


@router.get(
    "/versions",
    summary="List Agent Versions",
    description="List available agent versions for all supported targets or bundles.",
    responses={
        200: {
            "description": "Version manifest",
            "content": {"application/json": {}},
        },
        503: {
            "description": "Storage not configured",
        },
    },
)
async def list_versions(
    storage: StorageServiceDep,
    source: StorageSource = Query(
        default=StorageSource.BINARY,
        description="Storage source: binary (pre-compiled), obs (S3 bundles), local (local bundles)",
    ),
) -> dict[str, Any]:
    """List available agent versions.

    For source=binary: Returns versions per target architecture.
    For source=obs or source=local: Returns bundled source versions.

    Args:
        storage: Storage service dependency.
        source: Storage source to query.

    Returns:
        Version manifest with targets/bundles and their available versions.

    Raises:
        HTTPException 503: Storage not configured.
    """
    from hydra.api.v1.services.storage import StorageNotConfiguredError, StorageUnavailableError

    if storage is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "STORAGE_NOT_CONFIGURED",
                    "message": "No storage backend is configured.",
                    "details": {"requested_source": source.value},
                }
            },
        )

    if not storage.is_source_available(source):
        available = [s.value for s in storage.get_available_sources()]
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SOURCE_NOT_CONFIGURED",
                    "message": f"Storage source '{source.value}' is not configured.",
                    "details": {"available_sources": available},
                }
            },
        )

    manifest = {
        "schemaVersion": 1,
        "latestVersion": __version__,
        "source": source.value,
        "availableSources": [s.value for s in storage.get_available_sources()],
    }

    try:
        backend = storage.get_backend(source)

        if source == StorageSource.BINARY:
            manifest["targets"] = {}

            for _target_name, target_info in SUPPORTED_TARGETS.items():
                target = target_info["target"]

                try:
                    logger.debug("listing_versions_for_target", target=target, source=source.value)
                    versions = await backend.list_versions(target)
                    latest = await backend.get_latest_version(target)

                    logger.debug(
                        "versions_found",
                        target=target,
                        version_count=len(versions),
                        latest=latest,
                    )

                    if versions:
                        manifest["targets"][target] = {  # type: ignore[index]
                            "latest": latest or (versions[0]["version"] if versions else None),
                            "versions": versions,
                        }
                    else:
                        manifest["targets"][target] = {  # type: ignore[index]
                            "latest": None,
                            "versions": [],
                            "status": "no_binaries_available",
                        }
                except StorageUnavailableError as e:
                    logger.warning("storage_unavailable_for_target", target=target, error=str(e))
                    manifest["targets"][target] = {  # type: ignore[index]
                        "latest": None,
                        "versions": [],
                        "status": "storage_unavailable",
                    }
                except Exception as e:
                    logger.warning(
                        "list_versions_error",
                        target=target,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    manifest["targets"][target] = {  # type: ignore[index]
                        "latest": None,
                        "versions": [],
                        "status": "error",
                        "error": str(e),
                    }
        else:
            versions = await backend.list_versions()
            latest = await backend.get_latest_version()

            manifest["bundles"] = {
                "latest": latest,
                "versions": versions,
            }

    except StorageNotConfiguredError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "SOURCE_NOT_CONFIGURED",
                    "message": str(e),
                }
            },
        )

    logger.info("versions_listed", source=source.value)

    return manifest


# ---------------------------------------------------------------------------
# Agent Event Reporting
# ---------------------------------------------------------------------------

# Allowed event types agents can report
ALLOWED_AGENT_EVENT_TYPES = {
    "agent_profile_failed",
    "agent_registration_failed",
    "agent_profile_submitted",
    "agent_upgraded",
}


class AgentEventReport(BaseModel):
    """Payload for agent event reports."""

    model_config = ConfigDict(populate_by_name=True)

    event_type: str = Field(alias="eventType", description="Notification event type")
    title: str = Field(max_length=120, description="Short event title")
    message: str = Field(max_length=2000, description="Detailed event message")
    details: dict[str, Any] | None = Field(default=None, description="Additional event details")
    node_id: str | None = Field(
        default=None,
        alias="nodeId",
        description="Node ID this event relates to (defaults to agent's node)",
    )


class AgentEventResponse(BaseModel):
    """Response for agent event reports."""

    model_config = ConfigDict(populate_by_name=True)

    notification_id: str | None = Field(alias="notificationId")
    status: str


@router.post(
    "/report",
    summary="Report Agent Event",
    description="Agents report events (failures, state changes) which create notifications.",
    response_model=AgentEventResponse,
    response_model_by_alias=True,
    responses={
        200: {"description": "Event accepted and notification created"},
        400: {"description": "Invalid event type"},
        401: {"description": "Authentication required"},
        403: {"description": "Agent authentication required"},
    },
)
async def report_agent_event(
    report: AgentEventReport,
    current_user: CurrentUser,
    mongodb: MongoDBDep,
    redis: RedisDep,
) -> AgentEventResponse:
    """Accept an event report from an agent and create a notification.

    Only agents can call this endpoint. The event type must be one of the
    allowed agent event types.

    Args:
        report: The agent event report payload.
        current_user: The authenticated agent user.
        mongodb: MongoDB dependency.
        redis: Redis dependency.

    Returns:
        Response with the created notification ID.
    """
    # Require agent authentication
    if current_user.get("type") != "agent":
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "AGENT_AUTH_REQUIRED",
                    "message": "Only agents can report events via this endpoint",
                }
            },
        )

    # Validate event type
    if report.event_type not in ALLOWED_AGENT_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_EVENT_TYPE",
                    "message": f"Event type '{report.event_type}' is not allowed for agent reporting",
                    "details": {"allowedTypes": sorted(ALLOWED_AGENT_EVENT_TYPES)},
                }
            },
        )

    # Determine node_id from report or agent context
    node_id = report.node_id or current_user.get("node_id")

    # Emit notification (fire-and-forget via service)
    from hydra.api.v1.models.notifications import (
        ActorType,
        NotificationActor,
        NotificationSource,
        NotificationType,
        SourceComponent,
    )
    from hydra.api.v1.services.notifications import NotificationService

    notification_service = NotificationService(mongodb, redis)

    try:
        notification_type = NotificationType(report.event_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_EVENT_TYPE",
                    "message": f"Unknown notification type: {report.event_type}",
                }
            },
        )

    source = NotificationSource(  # type: ignore[call-arg]
        component=SourceComponent.HYDRA_AGENT,
        service="hydra-agent",
        nodeId=node_id,
    )

    actor = NotificationActor(
        type=ActorType.AGENT,
        id=current_user.get("user_id", "unknown"),
    )

    notification_id = await notification_service.emit(
        notification_type=notification_type,
        source=source,
        title=report.title,
        message=report.message,
        details=report.details,
        actor=actor,
    )

    logger.info(
        "agent_event_reported",
        event_type=report.event_type,
        node_id=node_id,
        notification_id=notification_id,
        agent_user_id=current_user.get("user_id"),
    )

    return AgentEventResponse(  # type: ignore[call-arg]
        notificationId=notification_id,
        status="accepted",
    )
