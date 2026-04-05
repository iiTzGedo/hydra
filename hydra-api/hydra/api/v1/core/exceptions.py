"""Custom exceptions and error handling."""

from typing import Any


class HydraError(Exception):
    """Base exception for Hydra API errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(HydraError):
    """Base authentication error."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, status_code=401, details=details)


class InvalidTokenError(AuthenticationError):
    """JWT token is invalid or expired."""

    def __init__(self, message: str = "Invalid or expired token") -> None:
        super().__init__("AUTH_INVALID_TOKEN", message)


class MissingTokenError(AuthenticationError):
    """No authorization token provided."""

    def __init__(self) -> None:
        super().__init__("AUTH_MISSING_TOKEN", "Authorization token required")


class InvalidCredentialsError(AuthenticationError):
    """Invalid username/password."""

    def __init__(self) -> None:
        super().__init__("AUTH_INVALID_CREDENTIALS", "Invalid username or password")


class RegistrationTokenError(AuthenticationError):
    """Registration token error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message)


class PasswordResetTokenError(AuthenticationError):
    """Password reset token error."""

    def __init__(self, code: str = "AUTH_INVALID_RESET_TOKEN", message: str = "Invalid or expired reset token") -> None:
        super().__init__(code, message)


class InvalidPasswordError(AuthenticationError):
    """Current password is incorrect."""

    def __init__(self) -> None:
        super().__init__("AUTH_INVALID_PASSWORD", "Current password is incorrect")


class PendingApprovalError(AuthenticationError):
    """User registration pending approval."""

    def __init__(self, username: str) -> None:
        super().__init__(
            "AUTH_PENDING_APPROVAL",
            f"User '{username}' is pending approval",
            details={"username": username},
        )


class AuthorizationError(HydraError):
    """Insufficient permissions."""

    def __init__(self, required_permission: str | None = None) -> None:
        details = {"required_permission": required_permission} if required_permission else {}
        super().__init__(
            "AUTH_INSUFFICIENT_PERMISSIONS",
            "Insufficient permissions for this operation",
            status_code=403,
            details=details,
        )


class ClientNotAuthorizedError(HydraError):
    """Request origin is not authorized for this operation."""

    def __init__(
        self,
        message: str = "This operation is only available from the Hydra web interface",
    ) -> None:
        super().__init__(
            "CLIENT_NOT_AUTHORIZED",
            message,
            status_code=403,
        )


class AdminOnlyError(HydraError):
    """Operation requires admin role."""

    def __init__(self, operation: str | None = None) -> None:
        details = {"operation": operation} if operation else {}
        super().__init__(
            "ADMIN_ONLY_OPERATION",
            "This operation requires admin role",
            status_code=403,
            details=details,
        )


class NotFoundError(HydraError):
    """Resource not found."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(
            f"{resource_type.upper()}_NOT_FOUND",
            f"{resource_type.title()} '{resource_id}' not found",
            status_code=404,
            details={f"{resource_type}Id": resource_id},
        )


class NodeNotFoundError(NotFoundError):
    """Node not found."""

    def __init__(self, node_id: str) -> None:
        super().__init__("node", node_id)


class ProfileNotFoundError(NotFoundError):
    """Profile not found."""

    def __init__(self, profile_id: str) -> None:
        super().__init__("profile", profile_id)


class ServiceNotFoundError(NotFoundError):
    """Service not found."""

    def __init__(self, service_id: str) -> None:
        super().__init__("service", service_id)


class NetworkNotFoundError(NotFoundError):
    """Network not found."""

    def __init__(self, network_id: str) -> None:
        super().__init__("network", network_id)


class GroupNotFoundError(NotFoundError):
    """Group not found."""

    def __init__(self, group_id: str) -> None:
        super().__init__("group", group_id)


class TopologyNotFoundError(NotFoundError):
    """Topology not found."""

    def __init__(self, topology_id: str) -> None:
        super().__init__("topology", topology_id)


class UserNotFoundError(NotFoundError):
    """User not found."""

    def __init__(self, user_id: str) -> None:
        super().__init__("user", user_id)


class PendingUserNotFoundError(HydraError):
    """Pending user not found."""

    def __init__(self, identifier: str) -> None:
        super().__init__(
            "PENDING_USER_NOT_FOUND",
            f"Pending user '{identifier}' not found",
            status_code=404,
            details={"identifier": identifier},
        )


class ApiKeyNotFoundError(NotFoundError):
    """API key not found."""

    def __init__(self, key_id: str) -> None:
        super().__init__("api_key", key_id)


class ConflictError(HydraError):
    """Resource already exists."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        super().__init__(
            f"{resource_type.upper()}_ALREADY_EXISTS",
            f"{resource_type.title()} '{resource_id}' already exists",
            status_code=409,
            details={f"{resource_type}Id": resource_id},
        )


class UsernameExistsError(HydraError):
    """Username already exists."""

    def __init__(self, username: str) -> None:
        super().__init__(
            "USERNAME_ALREADY_EXISTS",
            f"Username '{username}' is already taken",
            status_code=409,
            details={"username": username},
        )


class EmailExistsError(HydraError):
    """Email already exists."""

    def __init__(self, email: str) -> None:
        super().__init__(
            "EMAIL_ALREADY_EXISTS",
            f"Email '{email}' is already registered",
            status_code=409,
            details={"email": email},
        )


class NodeAlreadyRegisteredError(HydraError):
    """Node already registered."""

    def __init__(self, node_id: str) -> None:
        super().__init__(
            "NODE_ALREADY_REGISTERED",
            f"Node '{node_id}' is already registered",
            status_code=409,
            details={"nodeId": node_id},
        )


class ValidationError(HydraError):
    """Request validation failed."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            "VALIDATION_ERROR",
            message,
            status_code=400,
            details=details,
        )


class InvalidNodeIdError(ValidationError):
    """Invalid node ID format."""

    def __init__(self, node_id: str) -> None:
        super().__init__(
            f"Invalid node ID format: '{node_id}'",
            details={
                "nodeId": node_id,
                "pattern": "^[a-z0-9][a-z0-9.-]{2,63}$",
            },
        )


class BootstrapRequiresAdminError(HydraError):
    """First registration must be admin role."""

    def __init__(self) -> None:
        super().__init__(
            "BOOTSTRAP_REQUIRES_ADMIN",
            "First user registration must be an admin account",
            status_code=400,
        )


class RoleLimitExceededError(HydraError):
    """Maximum accounts for role reached."""

    def __init__(self, role: str, limit: int) -> None:
        super().__init__(
            "ROLE_LIMIT_EXCEEDED",
            f"Maximum number of {role} accounts ({limit}) has been reached",
            status_code=422,
            details={"role": role, "limit": limit},
        )


class InvalidRoleForElevationError(HydraError):
    """Cannot elevate to requested role."""

    def __init__(self, role: str, reason: str | None = None) -> None:
        message = f"Cannot elevate to role '{role}'"
        if reason:
            message += f": {reason}"
        super().__init__(
            "INVALID_ROLE_FOR_ELEVATION",
            message,
            status_code=422,
            details={"role": role},
        )


class CannotElevateAgentError(HydraError):
    """Agent role is system-managed."""

    def __init__(self) -> None:
        super().__init__(
            "CANNOT_ELEVATE_AGENT",
            "Agent role is system-managed and cannot be elevated",
            status_code=422,
        )


class TempRoleAlreadyActiveError(HydraError):
    """User already has this temporary role."""

    def __init__(self, user_id: str, role: str) -> None:
        super().__init__(
            "TEMP_ROLE_ALREADY_ACTIVE",
            f"User already has an active temporary '{role}' role",
            status_code=422,
            details={"userId": user_id, "role": role},
        )


class SubAccountError(HydraError):
    """Base error for sub-account operations."""

    pass


class CannotHaveSubAccountsError(SubAccountError):
    """User role cannot have sub-accounts."""

    def __init__(self, role: str) -> None:
        super().__init__(
            "CANNOT_HAVE_SUB_ACCOUNTS",
            f"Users with role '{role}' cannot have sub-accounts. Only admin and operator can.",
            status_code=403,
            details={"role": role},
        )


class InvalidSubAccountRoleError(SubAccountError):
    """Invalid role for sub-account."""

    def __init__(self, role: str) -> None:
        super().__init__(
            "INVALID_SUB_ACCOUNT_ROLE",
            f"Role '{role}' cannot be a sub-account. Only family, viewer, and agent roles can.",
            status_code=422,
            details={"role": role, "allowed_roles": ["family", "viewer", "agent"]},
        )


class AlreadyHasParentError(SubAccountError):
    """User is already a sub-account."""

    def __init__(self, user_id: str, parent_id: str) -> None:
        super().__init__(
            "ALREADY_HAS_PARENT",
            f"User '{user_id}' is already a sub-account of '{parent_id}'",
            status_code=409,
            details={"userId": user_id, "parentUserId": parent_id},
        )


class NotASubAccountError(SubAccountError):
    """User is not a sub-account."""

    def __init__(self, user_id: str) -> None:
        super().__init__(
            "NOT_A_SUB_ACCOUNT",
            f"User '{user_id}' is not a sub-account",
            status_code=422,
            details={"userId": user_id},
        )


class SystemAccountLoginBlockedError(AuthenticationError):
    """System accounts cannot login via web."""

    def __init__(self, username: str) -> None:
        super().__init__(
            "SYSTEM_ACCOUNT_LOGIN_BLOCKED",
            f"System account '{username}' cannot login via web interface. Use API key instead.",
            details={"username": username},
        )


class RateLimitError(HydraError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int) -> None:
        super().__init__(
            "RATE_LIMIT_EXCEEDED",
            "Too many requests",
            status_code=429,
            details={"retryAfter": retry_after},
        )


class ServiceUnavailableError(HydraError):
    """External service unavailable."""

    def __init__(self, service: str, message: str | None = None) -> None:
        super().__init__(
            f"{service.upper()}_UNAVAILABLE",
            message or f"{service} is temporarily unavailable",
            status_code=503,
            details={"service": service},
        )


class CommandNotFoundError(NotFoundError):
    """Command not found."""

    def __init__(self, command_id: str) -> None:
        super().__init__("command", command_id)


class CommandNotCancellableError(HydraError):
    """Command cannot be cancelled."""

    def __init__(self, command_id: str, status: str) -> None:
        super().__init__(
            "COMMAND_NOT_CANCELLABLE",
            f"Command '{command_id}' cannot be cancelled (status: {status})",
            status_code=422,
            details={"commandId": command_id, "status": status},
        )


class CommandAlreadyExecutingError(HydraError):
    """Command is not in queued state."""

    def __init__(self, command_id: str, status: str) -> None:
        super().__init__(
            "COMMAND_ALREADY_EXECUTING",
            f"Command '{command_id}' is not in queued state (status: {status})",
            status_code=422,
            details={"commandId": command_id, "status": status},
        )


class CommandNotSupportedError(HydraError):
    """Command execution not supported for this agent tier."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "COMMAND_NOT_SUPPORTED",
            message,
            status_code=400,
        )


class CommandNodeMismatchError(HydraError):
    """Command target node does not match."""

    def __init__(self, command_id: str, expected_node: str, actual_node: str) -> None:
        super().__init__(
            "COMMAND_NODE_MISMATCH",
            f"Command '{command_id}' is not for node '{actual_node}'",
            status_code=403,
            details={
                "commandId": command_id,
                "expectedNode": expected_node,
                "actualNode": actual_node,
            },
        )


class CommandRegistryNotFoundError(NotFoundError):
    """Command registry entry not found."""

    def __init__(self, registry_id: str) -> None:
        super().__init__("command_definition", registry_id)


class CommandRejectedError(HydraError):
    """Command was rejected (validation/RBAC failure)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "COMMAND_REJECTED",
            message,
            status_code=403,
        )


class CommandConfirmationExpiredError(HydraError):
    """Command confirmation window has expired."""

    def __init__(self, command_id: str) -> None:
        super().__init__(
            "COMMAND_CONFIRMATION_EXPIRED",
            f"Confirmation window for command '{command_id}' has expired",
            status_code=410,
            details={"commandId": command_id},
        )


class CommandConfirmationInvalidError(HydraError):
    """Command is not in pending_confirmation state."""

    def __init__(self, command_id: str, current_status: str) -> None:
        super().__init__(
            "COMMAND_CONFIRMATION_INVALID",
            f"Command '{command_id}' is in status '{current_status}', not 'pending_confirmation'",
            status_code=409,
            details={"commandId": command_id, "currentStatus": current_status},
        )


class CommandCooldownError(HydraError):
    """Node is in cooldown period after a destructive command."""

    def __init__(self, node_id: str, remaining_seconds: int) -> None:
        super().__init__(
            "COMMAND_COOLDOWN_ACTIVE",
            f"Node '{node_id}' is in cooldown period ({remaining_seconds}s remaining)",
            status_code=429,
            details={"nodeId": node_id, "remainingSeconds": remaining_seconds},
        )


class CommandRateLimitError(HydraError):
    """Command-specific rate limit exceeded."""

    def __init__(self, limit_type: str, retry_after: int) -> None:
        super().__init__(
            "COMMAND_RATE_LIMIT_EXCEEDED",
            f"Command rate limit exceeded ({limit_type}). Retry after {retry_after}s.",
            status_code=429,
            details={"limitType": limit_type, "retryAfter": retry_after},
        )


class DocNotFoundError(NotFoundError):
    """Documentation not found."""

    def __init__(self, doc_id: str) -> None:
        super().__init__("doc", doc_id)


class HomeAssistantUnavailableError(ServiceUnavailableError):
    """Home Assistant is unavailable."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__("HA", message or "Home Assistant is not reachable")


class CacheUnavailableError(ServiceUnavailableError):
    """Redis cache is unavailable."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__("CACHE", message or "Cache service is temporarily unavailable")


class DatabaseUnavailableError(ServiceUnavailableError):
    """MongoDB database is unavailable."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__("DATABASE", message or "Database is temporarily unavailable")


class ObjectStorageUnavailableError(ServiceUnavailableError):
    """S3/Garage object storage is unavailable."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__("OBJECT_STORAGE", message or "Object storage is temporarily unavailable")


class TokenExpiredError(AuthenticationError):
    """JWT token has expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__("AUTH_TOKEN_EXPIRED", message)


class InvalidParameterError(ValidationError):
    """Specific parameter has an invalid value."""

    def __init__(self, parameter: str, value: Any, reason: str | None = None) -> None:
        message = f"Invalid value for parameter '{parameter}'"
        if reason:
            message += f": {reason}"
        super().__init__(
            message,
            details={"parameter": parameter, "value": str(value)},
        )
        self.code = "INVALID_PARAMETER"


class MissingParameterError(ValidationError):
    """Required parameter is missing."""

    def __init__(self, parameter: str) -> None:
        super().__init__(
            f"Missing required parameter: {parameter}",
            details={"parameter": parameter},
        )
        self.code = "MISSING_PARAMETER"


class InvalidStateTransitionError(HydraError):
    """State transition is not allowed."""

    def __init__(self, resource_type: str, current_state: str, target_state: str) -> None:
        super().__init__(
            "INVALID_STATE_TRANSITION",
            f"Cannot transition {resource_type} from '{current_state}' to '{target_state}'",
            status_code=422,
            details={
                "resourceType": resource_type,
                "currentState": current_state,
                "targetState": target_state,
            },
        )


class OperationNotAllowedError(HydraError):
    """Operation is not allowed in current context."""

    def __init__(self, operation: str, reason: str | None = None) -> None:
        message = f"Operation '{operation}' is not allowed"
        if reason:
            message += f": {reason}"
        super().__init__(
            "OPERATION_NOT_ALLOWED",
            message,
            status_code=422,
            details={"operation": operation},
        )


# ── Workflow Exceptions ──────────────────────────────────────────────────


class WorkflowNotFoundError(NotFoundError):
    """Workflow definition not found."""

    def __init__(self, chain_id: str) -> None:
        super().__init__("workflow", chain_id)


class WorkflowExecutionNotFoundError(NotFoundError):
    """Workflow execution not found."""

    def __init__(self, execution_id: str) -> None:
        super().__init__("workflow_execution", execution_id)


class WorkflowCycleError(HydraError):
    """Workflow step dependency graph contains a cycle."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "WORKFLOW_CYCLE_DETECTED",
            message,
            status_code=422,
        )


class WorkflowNotCancellableError(HydraError):
    """Workflow execution cannot be cancelled."""

    def __init__(self, execution_id: str, status: str) -> None:
        super().__init__(
            "WORKFLOW_NOT_CANCELLABLE",
            f"Workflow execution '{execution_id}' cannot be cancelled (status: {status})",
            status_code=422,
            details={"executionId": execution_id, "status": status},
        )
