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
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


# Authentication Errors (401)
class AuthenticationError(HydraError):
    """Base authentication error."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(code, message, status_code=401, details=details)


class InvalidTokenError(AuthenticationError):
    """JWT token is invalid or expired."""

    def __init__(self, message: str = "Invalid or expired token"):
        super().__init__("AUTH_INVALID_TOKEN", message)


class MissingTokenError(AuthenticationError):
    """No authorization token provided."""

    def __init__(self):
        super().__init__("AUTH_MISSING_TOKEN", "Authorization token required")


class InvalidCredentialsError(AuthenticationError):
    """Invalid username/password."""

    def __init__(self):
        super().__init__("AUTH_INVALID_CREDENTIALS", "Invalid username or password")


class RegistrationTokenError(AuthenticationError):
    """Registration token error."""

    def __init__(self, code: str, message: str):
        super().__init__(code, message)


class PasswordResetTokenError(AuthenticationError):
    """Password reset token error."""

    def __init__(self, code: str = "AUTH_INVALID_RESET_TOKEN", message: str = "Invalid or expired reset token"):
        super().__init__(code, message)


class InvalidPasswordError(AuthenticationError):
    """Current password is incorrect."""

    def __init__(self):
        super().__init__("AUTH_INVALID_PASSWORD", "Current password is incorrect")


class PendingApprovalError(AuthenticationError):
    """User registration pending approval."""

    def __init__(self, username: str):
        super().__init__(
            "AUTH_PENDING_APPROVAL",
            f"User '{username}' is pending approval",
            details={"username": username},
        )


# Authorization Errors (403)
class AuthorizationError(HydraError):
    """Insufficient permissions."""

    def __init__(self, required_permission: str | None = None):
        details = {"required_permission": required_permission} if required_permission else {}
        super().__init__(
            "AUTH_INSUFFICIENT_PERMISSIONS",
            "Insufficient permissions for this operation",
            status_code=403,
            details=details,
        )


class AdminOnlyError(HydraError):
    """Operation requires admin role."""

    def __init__(self, operation: str | None = None):
        details = {"operation": operation} if operation else {}
        super().__init__(
            "ADMIN_ONLY_OPERATION",
            "This operation requires admin role",
            status_code=403,
            details=details,
        )


# Not Found Errors (404)
class NotFoundError(HydraError):
    """Resource not found."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type.upper()}_NOT_FOUND",
            f"{resource_type.title()} '{resource_id}' not found",
            status_code=404,
            details={f"{resource_type}Id": resource_id},
        )


class NodeNotFoundError(NotFoundError):
    """Node not found."""

    def __init__(self, node_id: str):
        super().__init__("node", node_id)


class ProfileNotFoundError(NotFoundError):
    """Profile not found."""

    def __init__(self, profile_id: str):
        super().__init__("profile", profile_id)


class ServiceNotFoundError(NotFoundError):
    """Service not found."""

    def __init__(self, service_id: str):
        super().__init__("service", service_id)


class NetworkNotFoundError(NotFoundError):
    """Network not found."""

    def __init__(self, network_id: str):
        super().__init__("network", network_id)


class GroupNotFoundError(NotFoundError):
    """Group not found."""

    def __init__(self, group_id: str):
        super().__init__("group", group_id)


class TopologyNotFoundError(NotFoundError):
    """Topology not found."""

    def __init__(self, topology_id: str):
        super().__init__("topology", topology_id)


class UserNotFoundError(NotFoundError):
    """User not found."""

    def __init__(self, user_id: str):
        super().__init__("user", user_id)


class PendingUserNotFoundError(HydraError):
    """Pending user not found."""

    def __init__(self, identifier: str):
        super().__init__(
            "PENDING_USER_NOT_FOUND",
            f"Pending user '{identifier}' not found",
            status_code=404,
            details={"identifier": identifier},
        )


class ApiKeyNotFoundError(NotFoundError):
    """API key not found."""

    def __init__(self, key_id: str):
        super().__init__("api_key", key_id)


# Conflict Errors (409)
class ConflictError(HydraError):
    """Resource already exists."""

    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            f"{resource_type.upper()}_ALREADY_EXISTS",
            f"{resource_type.title()} '{resource_id}' already exists",
            status_code=409,
            details={f"{resource_type}Id": resource_id},
        )


class UsernameExistsError(HydraError):
    """Username already exists."""

    def __init__(self, username: str):
        super().__init__(
            "USERNAME_ALREADY_EXISTS",
            f"Username '{username}' is already taken",
            status_code=409,
            details={"username": username},
        )


class EmailExistsError(HydraError):
    """Email already exists."""

    def __init__(self, email: str):
        super().__init__(
            "EMAIL_ALREADY_EXISTS",
            f"Email '{email}' is already registered",
            status_code=409,
            details={"email": email},
        )


class NodeAlreadyRegisteredError(HydraError):
    """Node already registered."""

    def __init__(self, node_id: str):
        super().__init__(
            "NODE_ALREADY_REGISTERED",
            f"Node '{node_id}' is already registered",
            status_code=409,
            details={"nodeId": node_id},
        )


# Validation Errors (400)
class ValidationError(HydraError):
    """Request validation failed."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            "VALIDATION_ERROR",
            message,
            status_code=400,
            details=details,
        )


class InvalidNodeIdError(ValidationError):
    """Invalid node ID format."""

    def __init__(self, node_id: str):
        super().__init__(
            f"Invalid node ID format: '{node_id}'",
            details={
                "nodeId": node_id,
                "pattern": "^[a-z0-9][a-z0-9.-]{2,63}$",
            },
        )


class BootstrapRequiresAdminError(HydraError):
    """First registration must be admin role."""

    def __init__(self):
        super().__init__(
            "BOOTSTRAP_REQUIRES_ADMIN",
            "First user registration must be an admin account",
            status_code=400,
        )


# Unprocessable Entity Errors (422)
class RoleLimitExceededError(HydraError):
    """Maximum accounts for role reached."""

    def __init__(self, role: str, limit: int):
        super().__init__(
            "ROLE_LIMIT_EXCEEDED",
            f"Maximum number of {role} accounts ({limit}) has been reached",
            status_code=422,
            details={"role": role, "limit": limit},
        )


class InvalidRoleForElevationError(HydraError):
    """Cannot elevate to requested role."""

    def __init__(self, role: str, reason: str | None = None):
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

    def __init__(self):
        super().__init__(
            "CANNOT_ELEVATE_AGENT",
            "Agent role is system-managed and cannot be elevated",
            status_code=422,
        )


class TempRoleAlreadyActiveError(HydraError):
    """User already has this temporary role."""

    def __init__(self, user_id: str, role: str):
        super().__init__(
            "TEMP_ROLE_ALREADY_ACTIVE",
            f"User already has an active temporary '{role}' role",
            status_code=422,
            details={"userId": user_id, "role": role},
        )


# Rate Limit Error (429)
class RateLimitError(HydraError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int):
        super().__init__(
            "RATE_LIMIT_EXCEEDED",
            "Too many requests",
            status_code=429,
            details={"retryAfter": retry_after},
        )


# Service Unavailable (503)
class ServiceUnavailableError(HydraError):
    """External service unavailable."""

    def __init__(self, service: str, message: str | None = None):
        super().__init__(
            f"{service.upper()}_UNAVAILABLE",
            message or f"{service} is temporarily unavailable",
            status_code=503,
            details={"service": service},
        )
