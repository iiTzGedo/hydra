"""Cryptographic utilities for encrypting sensitive data."""

import base64
import hashlib

from cryptography.fernet import Fernet

from hydra.core.config import get_settings


def _get_fernet_key() -> bytes:
    """Derive a Fernet key from the JWT secret.

    Returns:
        Base64-encoded 32-byte key suitable for Fernet encryption.
    """
    settings = get_settings()
    key_bytes = hashlib.sha256(settings.jwt_secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value using Fernet symmetric encryption.

    Args:
        plaintext: The value to encrypt.

    Returns:
        Base64-encoded encrypted value.
    """
    fernet = Fernet(_get_fernet_key())
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted value.

    Args:
        ciphertext: Base64-encoded encrypted value.

    Returns:
        Decrypted plaintext string.
    """
    fernet = Fernet(_get_fernet_key())
    decrypted = fernet.decrypt(ciphertext.encode())
    return decrypted.decode()


def mask_api_key(api_key: str, visible_chars: int = 4) -> str:
    """Mask an API key, showing only the last N characters.

    Args:
        api_key: The API key to mask.
        visible_chars: Number of characters to show at the end.

    Returns:
        Masked API key (e.g., "sk-...abcd").
    """
    if len(api_key) <= visible_chars:
        return "*" * len(api_key)

    prefix = api_key[:3] if len(api_key) > 3 else ""
    suffix = api_key[-visible_chars:]
    return f"{prefix}...{suffix}"
