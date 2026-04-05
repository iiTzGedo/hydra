"""Security utilities for JWT and password handling."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from jwt.exceptions import PyJWTError

from hydra.api.v1.core.exceptions import InvalidTokenError
from hydra.core.config import Settings, get_settings

pwd_hasher = PasswordHasher()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.

    Args:
        plain_password: The plaintext password to verify.
        hashed_password: The hashed password to compare against.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return pwd_hasher.verify(hashed_password, plain_password)
    except VerificationError:
        return False


def hash_password(password: str) -> str:
    """Hash a password using Argon2.

    Args:
        password: The plaintext password to hash.

    Returns:
        The hashed password string.
    """
    return pwd_hasher.hash(password)


def create_access_token(
    subject: str,
    token_type: str = "access",
    additional_claims: dict[str, Any] | None = None,
    settings: Settings | None = None,
    token_id: str | None = None,
    expires_at: datetime | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        subject: The subject (user ID, node ID, etc.).
        token_type: Type of token (access, refresh, registration).
        additional_claims: Additional claims to include in the token.
        settings: Application settings (optional, uses global if not provided).
        token_id: Explicit token JTI to embed.
        expires_at: Explicit expiry timestamp.

    Returns:
        Encoded JWT token string.
    """
    settings = settings or get_settings()

    if expires_at is not None:
        expire = expires_at
    elif token_type == "refresh":
        expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days)
    elif token_type == "registration":
        expire = datetime.now(UTC) + timedelta(days=settings.registration_token_expire_days)
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)

    claims = {
        "sub": subject,
        "type": token_type,
        "jti": token_id or uuid4().hex,
        "exp": expire,
        "iat": datetime.now(UTC),
    }

    if additional_claims:
        claims.update(additional_claims)

    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string.
        settings: Application settings.

    Returns:
        Decoded token claims.

    Raises:
        InvalidTokenError: If token is invalid or expired.
    """
    settings = settings or get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except PyJWTError:
        raise InvalidTokenError("Token validation failed")


def create_token_pair(
    subject: str,
    additional_claims: dict[str, Any] | None = None,
    settings: Settings | None = None,
    session_id: str | None = None,
    refresh_token_id: str | None = None,
) -> tuple[str, str]:
    """Create an access/refresh token pair.

    Args:
        subject: The subject (user ID, node ID, etc.).
        additional_claims: Additional claims to include in the access token.
        settings: Application settings.
        session_id: Shared session identifier embedded in both tokens.
        refresh_token_id: Explicit refresh-token JTI.

    Returns:
        Tuple of (access_token, refresh_token).
    """
    settings = settings or get_settings()

    current_session_id = session_id or uuid4().hex
    access_claims = dict(additional_claims or {})
    access_claims["sid"] = current_session_id
    access_token = create_access_token(
        subject=subject,
        token_type="access",
        additional_claims=access_claims,
        settings=settings,
    )

    refresh_token = create_access_token(
        subject=subject,
        token_type="refresh",
        additional_claims={
            "sub_type": additional_claims.get("sub_type", "user") if additional_claims else "user",
            "sid": current_session_id,
        },
        settings=settings,
        token_id=refresh_token_id,
    )

    return access_token, refresh_token
