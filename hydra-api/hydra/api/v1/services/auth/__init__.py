"""Authentication service module.

Re-exports AuthService so that existing imports continue to work:
    from hydra.api.v1.services.auth import AuthService
"""

from .service import AuthService

__all__ = ["AuthService"]
