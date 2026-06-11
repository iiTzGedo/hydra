"""SSH remote agent installation service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from pymongo import ASCENDING, DESCENDING

from hydra.api.v1.core.exceptions import (
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
)
from hydra.api.v1.models.installations import (
    InstallationListParams,
    InstallationStatus,
    InstallationStepStatus,
    StartInstallationRequest,
)
from hydra.core.config import get_settings
from hydra.db.mongodb import MongoDB

logger = structlog.get_logger(__name__)

# Process-wide concurrency guard shared across all installation requests.
# Lazily created from settings so the limit reflects HYDRA_REMOTE_INSTALL_MAX_CONCURRENT.
_install_semaphore: asyncio.Semaphore | None = None
_install_semaphore_limit: int | None = None


def get_install_semaphore() -> asyncio.Semaphore:
    """Return the process-wide remote-installation concurrency semaphore.

    Created lazily so it binds to the running event loop, and recreated when the
    configured limit changes (e.g. between test cases that override settings).
    """
    global _install_semaphore, _install_semaphore_limit  # noqa: PLW0603
    limit = get_settings().remote_install_max_concurrent
    if _install_semaphore is None or _install_semaphore_limit != limit:
        _install_semaphore = asyncio.Semaphore(limit)
        _install_semaphore_limit = limit
    return _install_semaphore


def reset_install_concurrency() -> None:
    """Reset the cached installation semaphore. Intended for test isolation."""
    global _install_semaphore, _install_semaphore_limit  # noqa: PLW0603
    _install_semaphore = None
    _install_semaphore_limit = None

# Phases in execution order with associated percent-complete values
_PHASE_PROGRESS: list[tuple[InstallationStatus, int, str]] = [
    (InstallationStatus.CONNECTING, 10, "Connecting to remote host via SSH"),
    (InstallationStatus.TRANSFERRING, 30, "Transferring agent binary to remote host"),
    (InstallationStatus.CONFIGURING, 50, "Writing agent configuration"),
    (InstallationStatus.REGISTERING, 70, "Registering agent with Hydra API"),
    (InstallationStatus.RUNNING, 90, "Starting agent service on remote host"),
    (InstallationStatus.COMPLETED, 100, "Installation completed successfully"),
]


# ── Exceptions ──────────────────────────────────────────────────────────


class InstallationNotFoundError(NotFoundError):
    """Installation not found."""

    def __init__(self, installation_id: str) -> None:
        super().__init__("installation", installation_id)


# ── Service ─────────────────────────────────────────────────────────────


class InstallationService:
    """Service for managing remote SSH agent installations."""

    def __init__(self, mongodb: MongoDB) -> None:
        self.db = mongodb
        self.installations = mongodb.db["installations"]
        self.discovered_nodes = mongodb.db["discovered_nodes"]
        self.nodes = mongodb.db["nodes"]

    # ── Public API ─────────────────────────────────────────────────────

    async def start_installation(
        self,
        request: StartInstallationRequest,
        user_id: str,
    ) -> dict[str, Any]:
        """Start a new remote agent installation.

        Args:
            request: Installation request with SSH credentials and target.
            user_id: ID of the user initiating the installation.

        Returns:
            The created installation document.
        """
        now = datetime.now(UTC)
        installation_id = f"inst_{uuid4().hex[:12]}"

        target_ip = request.target_ip or ""
        target_hostname: str | None = None

        # Resolve target from discovery if discovery_id is provided, and gate the
        # install on the device's stored eligibility (P2E-T02).
        if request.discovery_id:
            device = await self.discovered_nodes.find_one(
                {"discoveryId": request.discovery_id}
            )
            if device:
                identity = device.get("identity", {})
                target_ip = identity.get("currentIp", target_ip)
                target_hostname = identity.get("hostname")
                self._assert_remote_install_eligible(device)

        doc: dict[str, Any] = {
            "installationId": installation_id,
            "discoveryId": request.discovery_id,
            "targetIp": target_ip,
            "targetHostname": target_hostname,
            "status": InstallationStatus.PENDING,
            "progress": {
                "phase": InstallationStatus.PENDING,
                "percentComplete": 0,
                "message": "Installation queued",
                "startedAt": None,
                "updatedAt": now,
            },
            "steps": [],
            "nodeId": None,
            "error": None,
            "agentTier": request.agent_tier,
            "tags": request.tags,
            "createdBy": user_id,
            "createdAt": now,
            "updatedAt": now,
            "completedAt": None,
        }

        await self.installations.insert_one(doc)

        # Store credentials transiently for the background task (not persisted)
        credentials_dict = request.credentials.model_dump(by_alias=True)

        # Launch background installation task
        asyncio.create_task(
            self._execute_installation(installation_id, credentials_dict)
        )

        logger.info(
            "installation.started",
            installation_id=installation_id,
            target_ip=target_ip,
            discovery_id=request.discovery_id,
        )

        return await self.get_installation(installation_id)

    async def get_installation(self, installation_id: str) -> dict[str, Any]:
        """Get an installation by ID.

        Args:
            installation_id: The installation identifier.

        Returns:
            The installation document.

        Raises:
            InstallationNotFoundError: If the installation does not exist.
        """
        doc = await self.installations.find_one(
            {"installationId": installation_id}
        )
        if not doc:
            raise InstallationNotFoundError(installation_id)
        return self._format_installation(doc)

    async def list_installations(
        self,
        params: InstallationListParams,
        user_id: str,  # noqa: ARG002
    ) -> tuple[list[dict[str, Any]], int]:
        """List installations with optional filtering and pagination.

        Args:
            params: Listing parameters.
            user_id: ID of the requesting user (reserved for future filtering).

        Returns:
            Tuple of (installations, total_count).
        """
        query: dict[str, Any] = {}
        if params.status is not None:
            query["status"] = params.status.value

        sort_dir = DESCENDING if params.sort_order == "desc" else ASCENDING
        total = await self.installations.count_documents(query)
        cursor = (
            self.installations.find(query)
            .sort(params.sort_by, sort_dir)
            .skip(params.offset)
            .limit(params.limit)
        )
        docs = await cursor.to_list(length=params.limit)
        return [self._format_installation(d) for d in docs], total

    async def cancel_installation(
        self,
        installation_id: str,
        user_id: str,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Cancel an active installation.

        Args:
            installation_id: The installation to cancel.
            user_id: ID of the user cancelling (reserved for audit).

        Returns:
            The updated installation document.

        Raises:
            InstallationNotFoundError: If installation does not exist.
            InvalidStateTransitionError: If installation is not in a cancellable state.
        """
        doc = await self.installations.find_one(
            {"installationId": installation_id}
        )
        if not doc:
            raise InstallationNotFoundError(installation_id)

        terminal = {
            InstallationStatus.COMPLETED,
            InstallationStatus.FAILED,
            InstallationStatus.CANCELLED,
        }
        if doc["status"] in terminal:
            raise InvalidStateTransitionError(
                "installation", doc["status"], InstallationStatus.CANCELLED
            )

        now = datetime.now(UTC)
        await self.installations.update_one(
            {"installationId": installation_id},
            {
                "$set": {
                    "status": InstallationStatus.CANCELLED,
                    "progress.phase": InstallationStatus.CANCELLED,
                    "progress.message": "Cancelled by user",
                    "progress.updatedAt": now,
                    "updatedAt": now,
                    "completedAt": now,
                }
            },
        )

        logger.info("installation.cancelled", installation_id=installation_id)
        return await self.get_installation(installation_id)

    async def retry_installation(
        self,
        installation_id: str,
        user_id: str,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Retry a failed installation.

        Args:
            installation_id: The installation to retry.
            user_id: ID of the user retrying (reserved for audit).

        Returns:
            The updated installation document.

        Raises:
            InstallationNotFoundError: If installation does not exist.
            InvalidStateTransitionError: If installation is not in a retriable state.
        """
        doc = await self.installations.find_one(
            {"installationId": installation_id}
        )
        if not doc:
            raise InstallationNotFoundError(installation_id)

        if doc["status"] != InstallationStatus.FAILED:
            raise InvalidStateTransitionError(
                "installation", doc["status"], InstallationStatus.PENDING
            )

        now = datetime.now(UTC)
        await self.installations.update_one(
            {"installationId": installation_id},
            {
                "$set": {
                    "status": InstallationStatus.PENDING,
                    "progress": {
                        "phase": InstallationStatus.PENDING,
                        "percentComplete": 0,
                        "message": "Retrying installation",
                        "startedAt": None,
                        "updatedAt": now,
                    },
                    "error": None,
                    "updatedAt": now,
                    "completedAt": None,
                }
            },
        )

        # Re-launch background task (credentials unavailable on retry — simulate)
        asyncio.create_task(
            self._execute_installation(installation_id, None)
        )

        logger.info("installation.retried", installation_id=installation_id)
        return await self.get_installation(installation_id)

    # ── Background Execution ──────────────────────────────────────────

    async def _execute_installation(
        self,
        installation_id: str,
        credentials: dict[str, Any] | None,
    ) -> None:
        """Execute the installation process in the background.

        Progresses through SSH phases: connect, transfer, configure, register, run.
        On failure, marks the installation as failed with an error message.
        If asyncssh is not available, simulates the flow for development/testing.

        Args:
            installation_id: The installation being executed.
            credentials: SSH credentials dict, or None for retries.
        """
        try:
            # Check if the installation was already cancelled before starting
            doc = await self.installations.find_one(
                {"installationId": installation_id}
            )
            if not doc or doc["status"] == InstallationStatus.CANCELLED:
                return

            discovery_id = doc.get("discoveryId")

            # Bound concurrent installs (HYDRA_REMOTE_INSTALL_MAX_CONCURRENT).
            # While waiting for a slot the installation remains queued (PENDING).
            async with get_install_semaphore():
                # Re-check cancellation after acquiring the slot — the install
                # may have been cancelled while queued behind other installs.
                doc = await self.installations.find_one(
                    {"installationId": installation_id}
                )
                if not doc or doc["status"] == InstallationStatus.CANCELLED:
                    return

                # Update discovery status to INSTALLING if linked
                if discovery_id:
                    await self.discovered_nodes.update_one(
                        {"discoveryId": discovery_id},
                        {"$set": {"status": "installing"}},
                    )

                for phase, percent, message in _PHASE_PROGRESS:
                    # Check for cancellation before each phase
                    current = await self.installations.find_one(
                        {"installationId": installation_id}
                    )
                    if not current or current["status"] == InstallationStatus.CANCELLED:
                        return

                    await self._update_progress(
                        installation_id, phase, percent, message
                    )

                    if phase == InstallationStatus.COMPLETED:
                        break

                    # Record a structured step around each phase's work.
                    step_started = datetime.now(UTC)
                    await self._log_step(
                        installation_id,
                        phase.value,
                        InstallationStepStatus.IN_PROGRESS,
                        message,
                        started_at=step_started,
                    )

                    # Simulate SSH work — in production this will use asyncssh
                    await self._execute_phase(phase, credentials)

                    await self._log_step(
                        installation_id,
                        phase.value,
                        InstallationStepStatus.COMPLETED,
                        f"{message} — completed",
                        started_at=step_started,
                    )

                # Mark completed
                now = datetime.now(UTC)
                await self.installations.update_one(
                    {"installationId": installation_id},
                    {
                        "$set": {
                            "status": InstallationStatus.COMPLETED,
                            "completedAt": now,
                            "updatedAt": now,
                        }
                    },
                )

                # Update discovery status to INSTALLED if linked
                if discovery_id:
                    await self.discovered_nodes.update_one(
                        {"discoveryId": discovery_id},
                        {"$set": {"status": "installed"}},
                    )

                logger.info(
                    "installation.completed", installation_id=installation_id
                )

        except Exception as exc:
            logger.error(
                "installation.failed",
                installation_id=installation_id,
                error=str(exc),
            )
            now = datetime.now(UTC)
            await self.installations.update_one(
                {"installationId": installation_id},
                {
                    "$set": {
                        "status": InstallationStatus.FAILED,
                        "error": str(exc),
                        "progress.phase": InstallationStatus.FAILED,
                        "progress.message": f"Failed: {exc}",
                        "progress.updatedAt": now,
                        "updatedAt": now,
                        "completedAt": now,
                    }
                },
            )
            # Mark any still-in-progress step as failed.
            await self.installations.update_one(
                {"installationId": installation_id},
                {
                    "$set": {
                        "steps.$[s].status": InstallationStepStatus.FAILED.value,
                        "steps.$[s].completedAt": now,
                        "steps.$[s].message": f"Failed: {exc}",
                    }
                },
                array_filters=[{"s.status": InstallationStepStatus.IN_PROGRESS.value}],
            )

    async def _execute_phase(
        self,
        phase: InstallationStatus,
        credentials: dict[str, Any] | None,  # noqa: ARG002
    ) -> None:
        """Execute a single installation phase.

        Currently simulates the SSH operations. When asyncssh is integrated,
        each phase will perform real SSH work.

        Args:
            phase: The current phase to execute.
            credentials: SSH credentials (unused in simulation).
        """
        # Simulate work for each phase — real implementation will use asyncssh
        phase_delays: dict[InstallationStatus, float] = {
            InstallationStatus.CONNECTING: 0.5,
            InstallationStatus.TRANSFERRING: 1.0,
            InstallationStatus.CONFIGURING: 0.5,
            InstallationStatus.REGISTERING: 0.5,
            InstallationStatus.RUNNING: 0.5,
        }
        delay = phase_delays.get(phase, 0.3)
        await asyncio.sleep(delay)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _suggested_actions_for_blockers(blockers: list[str]) -> list[str]:
        """Derive remediation guidance from remote-install blockers."""
        actions: list[str] = []
        for blocker in blockers:
            lowered = blocker.lower()
            if "ssh" in lowered:
                actions.append(
                    "Enable SSH (port 22) on the target and ensure it is reachable."
                )
            elif "windows" in lowered:
                actions.append(
                    "Install the agent manually on Windows via the PowerShell installer."
                )
            elif "embedded" in lowered:
                actions.append(
                    "Profile this device via an integration rather than the Hydra agent."
                )
        if not actions:
            actions.append(
                "Resolve the listed blockers, then re-run discovery before installing."
            )
        return actions

    def _assert_remote_install_eligible(self, device: dict[str, Any]) -> None:
        """Raise a 400 if the discovered device is not eligible for remote install.

        Args:
            device: The discovered device document.

        Raises:
            ValidationError: If the device has remote-install blockers or its
                eligibility marks it as not remote-installable.
        """
        eligibility = device.get("eligibility") or {}
        blockers = list(eligibility.get("remoteInstallBlockers") or [])
        # If eligibility was assessed and explicitly not installable, surface it.
        if not blockers and eligibility and eligibility.get("remoteInstallable") is False:
            blockers = ["Device is not eligible for remote agent installation"]
        if blockers:
            raise ValidationError(
                "Device is not eligible for remote agent installation",
                {
                    "blockers": blockers,
                    "suggestedActions": self._suggested_actions_for_blockers(blockers),
                },
            )

    async def _log_step(
        self,
        installation_id: str,
        step: str,
        status: InstallationStepStatus,
        message: str,
        *,
        started_at: datetime | None = None,
        output: str | None = None,
    ) -> None:
        """Append or update a structured step entry on the installation document.

        A new step is appended when it first starts; on completion the matching
        in-progress step is finalized with its duration.
        """
        now = datetime.now(UTC)
        if status == InstallationStepStatus.IN_PROGRESS:
            await self.installations.update_one(
                {"installationId": installation_id},
                {
                    "$push": {
                        "steps": {
                            "step": step,
                            "status": status.value,
                            "startedAt": now,
                            "completedAt": None,
                            "durationSeconds": None,
                            "message": message,
                            "output": output,
                        }
                    }
                },
            )
            return

        duration = (now - started_at).total_seconds() if started_at else None
        await self.installations.update_one(
            {"installationId": installation_id, "steps.step": step},
            {
                "$set": {
                    "steps.$.status": status.value,
                    "steps.$.completedAt": now,
                    "steps.$.durationSeconds": duration,
                    "steps.$.message": message,
                    "steps.$.output": output,
                }
            },
        )

    async def _update_progress(
        self,
        installation_id: str,
        phase: InstallationStatus,
        percent: int,
        message: str,
    ) -> None:
        """Update installation progress in the database.

        Args:
            installation_id: The installation to update.
            phase: The current phase.
            percent: Percent complete (0-100).
            message: Human-readable status message.
        """
        now = datetime.now(UTC)
        await self.installations.update_one(
            {"installationId": installation_id},
            {
                "$set": {
                    "status": phase
                    if phase != InstallationStatus.COMPLETED
                    else InstallationStatus.RUNNING,
                    "progress.phase": phase,
                    "progress.percentComplete": percent,
                    "progress.message": message,
                    "progress.startedAt": now,
                    "progress.updatedAt": now,
                    "updatedAt": now,
                }
            },
        )

    @staticmethod
    def _format_installation(doc: dict[str, Any]) -> dict[str, Any]:
        """Format an installation document for API response.

        Strips MongoDB _id and ensures consistent shape.

        Args:
            doc: Raw MongoDB document.

        Returns:
            Formatted installation dict.
        """
        doc.pop("_id", None)
        return doc
