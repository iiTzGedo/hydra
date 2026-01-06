"""FastAPI dependencies for authentication and common services."""

from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hydra.api.v1.core.exceptions import (
    AuthorizationError,
    InvalidTokenError,
    MissingTokenError,
)
from hydra.api.v1.core.security import decode_token
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import RedisClient, get_redis
from hydra.api.v1.services.auth import AuthService
from hydra.api.v1.services.users import UsersService

logger = structlog.get_logger(__name__)

# Security scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_auth_service(
    mongodb: MongoDB = Depends(get_mongodb),
) -> AuthService:
    """Get authentication service."""
    return AuthService(mongodb)


async def get_users_service(
    mongodb: MongoDB = Depends(get_mongodb),
) -> UsersService:
    """Get users service."""
    return UsersService(mongodb)


async def get_optional_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict | None:
    """Get optional token payload (for endpoints that support both auth and anon)."""
    if x_api_key:
        # API key authentication is handled separately
        return {"type": "api_key", "key": x_api_key}

    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            return payload
        except InvalidTokenError:
            return None

    return None


async def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Get and validate the current token payload."""
    if x_api_key:
        # Validate API key
        try:
            key_data = await auth_service.validate_api_key(x_api_key)

            # Build the payload based on API key type
            if key_data.get("type") == "node":
                # Node API key - return as agent
                return {
                    "sub": key_data["nodeId"],
                    "sub_type": "api_key",
                    "node_id": key_data["nodeId"],
                    "permissions": key_data.get("permissions", []),
                }
            else:
                # User API key
                return {
                    "sub": key_data["ownerId"],
                    "sub_type": "api_key",
                    "roles": key_data.get("roles", []),
                    "permissions": key_data.get("permissions", []),
                }
        except InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
        return payload
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    token: dict = Depends(get_current_token),
    users_service: UsersService = Depends(get_users_service),
) -> dict:
    """Get the current authenticated user or agent."""
    return await users_service.get_current_user(token)


def require_permission(permission: str):
    """
    Dependency factory for checking permissions.

    Usage:
        @router.get("/admin")
        async def admin_endpoint(user = Depends(require_permission("users:*"))):
            ...
    """

    async def check_permission(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        user_permissions = current_user.get("permissions", [])

        # Check for wildcard
        if "*:*" in user_permissions:
            return current_user

        # Check for exact match
        if permission in user_permissions:
            return current_user

        # Check for resource wildcard (e.g., "nodes:*" matches "nodes:read")
        resource, action = permission.split(":", 1) if ":" in permission else (permission, "*")
        if f"{resource}:*" in user_permissions:
            return current_user

        logger.warning(
            "permission_denied",
            required=permission,
            user_permissions=user_permissions,
        )
        raise AuthorizationError(permission)

    return check_permission


def require_agent() -> dict:
    """Dependency to require agent authentication."""

    async def check_agent(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        if current_user.get("type") != "agent":
            raise AuthorizationError("Agent authentication required")
        return current_user

    return Depends(check_agent)


async def get_registration_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_registration_token: str | None = Header(default=None, alias="X-Registration-Token"),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """
    Get authentication for node registration.

    Supports three authentication methods:
    1. X-Registration-Token header - node registration token
    2. Bearer token - user JWT (must have nodes:create permission)
    3. X-API-Key header - user API key (must have nodes:create permission)

    Returns a dict with:
    - type: "registration_token" | "user"
    - For registration_token: token_data
    - For user: user data with user_id
    """
    # Priority 1: Registration token
    if x_registration_token:
        try:
            token_data = await auth_service.validate_registration_token(x_registration_token)
            return {
                "type": "registration_token",
                "token": x_registration_token,
                "token_data": token_data,
                "user_id": token_data.get("createdBy", "system"),
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Priority 2: API key or Bearer token
    if x_api_key:
        try:
            key_data = await auth_service.validate_api_key(x_api_key)
            if key_data.get("type") == "node":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Node API keys cannot register new nodes",
                )
            # User API key - check permissions
            permissions = key_data.get("permissions", [])
            roles = key_data.get("roles", [])
            has_permission = (
                "*:*" in permissions
                or "nodes:*" in permissions
                or "nodes:create" in permissions
                or any(r in ["admin", "operator"] for r in roles)
            )
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API key does not have permission to register nodes",
                )
            return {
                "type": "user",
                "user_id": key_data["ownerId"],
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )

    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            current_user = await auth_service.get_current_user(payload)

            # Check permission
            user_permissions = current_user.get("permissions", [])
            has_permission = (
                "*:*" in user_permissions
                or "nodes:*" in user_permissions
                or "nodes:create" in user_permissions
            )
            if not has_permission:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User does not have permission to register nodes",
                )

            return {
                "type": "user",
                "user_id": current_user["user_id"],
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Bearer token, X-API-Key, or X-Registration-Token",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Storage service for agent binary distribution
async def get_storage_service():
    """Get storage service for agent binaries."""
    from hydra.core.config import get_settings
    from hydra.api.v1.services.storage import get_cached_storage_service, StorageService

    settings = get_settings()
    return get_cached_storage_service(settings)


# Type aliases for cleaner dependency injection
CurrentToken = Annotated[dict, Depends(get_current_token)]
CurrentUser = Annotated[dict, Depends(get_current_user)]
RegistrationAuth = Annotated[dict, Depends(get_registration_auth)]
MongoDBDep = Annotated[MongoDB, Depends(get_mongodb)]
RedisDep = Annotated[RedisClient, Depends(get_redis)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]

# Import StorageService type for annotation
from hydra.api.v1.services.storage import StorageService
StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]
