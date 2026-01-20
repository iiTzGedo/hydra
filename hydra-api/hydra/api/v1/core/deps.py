"""FastAPI dependencies for authentication and common services."""

from typing import Annotated

import structlog
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hydra.api.v1.core.exceptions import (
    AuthorizationError,
    InvalidTokenError,
)
from hydra.api.v1.core.security import decode_token
from hydra.db.mongodb import MongoDB, get_mongodb
from hydra.db.redis import RedisClient, get_redis
from hydra.api.v1.services.auth import AuthService
from hydra.api.v1.services.users import UsersService

logger = structlog.get_logger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)


async def get_auth_service(
    mongodb: MongoDB = Depends(get_mongodb),
) -> AuthService:
    """Get authentication service instance.

    Args:
        mongodb: MongoDB connection dependency.

    Returns:
        AuthService instance.
    """
    return AuthService(mongodb)


async def get_users_service(
    mongodb: MongoDB = Depends(get_mongodb),
) -> UsersService:
    """Get users service instance.

    Args:
        mongodb: MongoDB connection dependency.

    Returns:
        UsersService instance.
    """
    return UsersService(mongodb)


async def get_optional_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict | None:
    """Get optional token payload for endpoints supporting both auth and anonymous access.

    Args:
        credentials: Optional Bearer token credentials.
        x_api_key: Optional API key from header.

    Returns:
        Token payload dict if authenticated, None otherwise.
    """
    if x_api_key:
        return {"type": "api_key", "key": x_api_key}

    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            return payload
        except InvalidTokenError:
            return None

    return None


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    auth_service: AuthService = Depends(get_auth_service),
    users_service: UsersService = Depends(get_users_service),
) -> dict | None:
    """Get optional current user, returning None if unauthenticated.

    Args:
        credentials: Optional Bearer token credentials.
        x_api_key: Optional API key from header.
        auth_service: Auth service dependency.
        users_service: Users service dependency.

    Returns:
        User dict if authenticated, None otherwise.
    """
    if x_api_key:
        try:
            key_data = await auth_service.validate_api_key(x_api_key)
        except InvalidTokenError:
            return None

        if key_data.get("type") == "node":
            token_payload = {
                "sub": key_data["nodeId"],
                "sub_type": "api_key",
                "node_id": key_data["nodeId"],
                "permissions": key_data.get("permissions", []),
            }
        else:
            token_payload = {
                "sub": key_data["ownerId"],
                "sub_type": "api_key",
                "permissions": key_data.get("permissions", []),
                "roles": key_data.get("roles", []),
                "node_id": key_data.get("nodeId"),
            }

        return await users_service.get_current_user(token_payload)

    if credentials:
        try:
            token_payload = decode_token(credentials.credentials)
        except InvalidTokenError:
            return None
        return await users_service.get_current_user(token_payload)

    return None


async def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Get and validate the current token payload.

    Args:
        credentials: Optional Bearer token credentials.
        x_api_key: Optional API key from header.
        auth_service: Auth service dependency.

    Returns:
        Token payload dict.

    Raises:
        HTTPException: If authentication fails.
    """
    if x_api_key:
        try:
            key_data = await auth_service.validate_api_key(x_api_key)

            if key_data.get("type") == "node":
                return {
                    "sub": key_data["nodeId"],
                    "sub_type": "api_key",
                    "node_id": key_data["nodeId"],
                    "permissions": key_data.get("permissions", []),
                }
            else:
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
    """Get the current authenticated user or agent.

    Args:
        token: Token payload from get_current_token.
        users_service: Users service dependency.

    Returns:
        Current user dict with permissions.
    """
    return await users_service.get_current_user(token)


def require_permission(permission: str):
    """Dependency factory for checking permissions.

    Args:
        permission: Required permission string (e.g., "nodes:read").

    Returns:
        FastAPI dependency that validates the permission.

    Example:
        @router.get("/admin")
        async def admin_endpoint(user = Depends(require_permission("users:*"))):
            ...
    """

    async def check_permission(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        user_permissions = current_user.get("permissions", [])

        if "*:*" in user_permissions:
            return current_user

        if permission in user_permissions:
            return current_user

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
    """Dependency to require agent authentication.

    Returns:
        FastAPI dependency that validates agent authentication.
    """

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
    """Get authentication for node registration.

    Supports three authentication methods:
    1. X-Registration-Token header - node registration token
    2. Bearer token - user JWT (must have nodes:create permission)
    3. X-API-Key header - user API key (must have nodes:create permission)

    Args:
        credentials: Optional Bearer token credentials.
        x_api_key: Optional API key from header.
        x_registration_token: Optional registration token from header.
        auth_service: Auth service dependency.

    Returns:
        Dict with type ("registration_token" or "user") and associated data.

    Raises:
        HTTPException: If authentication fails or lacks permission.
    """
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

    if x_api_key:
        try:
            key_data = await auth_service.validate_api_key(x_api_key)
            if key_data.get("type") == "node":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Node API keys cannot register new nodes",
                )
            permissions = key_data.get("permissions", [])
            roles = key_data.get("roles", [])
            has_permission = (
                "*:*" in permissions
                or "nodes:*" in permissions
                or "nodes:create" in permissions
                or any(r in ["admin", "operator", "agent"] for r in roles)
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
            current_user = await auth_service.users.get_current_user(payload)

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


async def get_storage_service():
    """Get storage service for agent binaries.

    Returns:
        StorageService instance.
    """
    from hydra.core.config import get_settings
    from hydra.api.v1.services.storage import get_cached_storage_service

    settings = get_settings()
    return get_cached_storage_service(settings)


CurrentToken = Annotated[dict, Depends(get_current_token)]
CurrentUser = Annotated[dict, Depends(get_current_user)]
OptionalUser = Annotated[dict | None, Depends(get_optional_user)]
RegistrationAuth = Annotated[dict, Depends(get_registration_auth)]
MongoDBDep = Annotated[MongoDB, Depends(get_mongodb)]
RedisDep = Annotated[RedisClient, Depends(get_redis)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]

from hydra.api.v1.services.storage import StorageService
StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]
