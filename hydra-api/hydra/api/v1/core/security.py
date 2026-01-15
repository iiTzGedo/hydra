"""Security utilities for JWT and password handling."""

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from hydra.core.config import Settings, get_settings
from hydra.api.v1.core.exceptions import InvalidTokenError

# Password hashing context
pwd_hasher = PasswordHasher()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    try:
        return pwd_hasher.verify(hashed_password, plain_password)
    except VerificationError:
        return False


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_hasher.hash(password)


def create_access_token(
    subject: str,
    token_type: str = "access",
    additional_claims: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        subject: The subject (user ID, node ID, etc.)
        token_type: Type of token (access, refresh, registration)
        additional_claims: Additional claims to include in the token
        settings: Application settings (optional, uses global if not provided)

    Returns:
        Encoded JWT token string
    """
    settings = settings or get_settings()

    # Determine expiration based on token type
    if token_type == "refresh":
        expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_expire_days)
    elif token_type == "registration":
        expire = datetime.now(timezone.utc) + timedelta(days=settings.registration_token_expire_days)
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)

    claims = {
        "sub": subject,
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    if additional_claims:
        claims.update(additional_claims)

    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token string
        settings: Application settings

    Returns:
        Decoded token claims

    Raises:
        InvalidTokenError: If token is invalid or expired
    """
    settings = settings or get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as e:
        raise InvalidTokenError(f"Token validation failed: {str(e)}")


def create_token_pair(
    subject: str,
    additional_claims: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> tuple[str, str]:
    """
    Create an access/refresh token pair.

    Returns:
        Tuple of (access_token, refresh_token)
    """
    settings = settings or get_settings()

    access_token = create_access_token(
        subject=subject,
        token_type="access",
        additional_claims=additional_claims,
        settings=settings,
    )

    refresh_token = create_access_token(
        subject=subject,
        token_type="refresh",
        additional_claims={"sub_type": additional_claims.get("sub_type", "user") if additional_claims else "user"},
        settings=settings,
    )

    return access_token, refresh_token
