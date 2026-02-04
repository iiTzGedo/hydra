"""User management service module.

Composes the UsersService from focused mixin classes:
- CoreMixin: Base class with __init__, CRUD, user retrieval, utility methods
- RegistrationMixin: Registration, approval, pending user flows
- RolesMixin: Role elevation, temporary roles, permission mappings
- CredentialsMixin: Password reset, change, email flows
- SubAccountsMixin: Sub-account linking, unlinking, listing
"""

from hydra.api.v1.services.users._core import CoreMixin
from hydra.api.v1.services.users._credentials import CredentialsMixin
from hydra.api.v1.services.users._registration import RegistrationMixin
from hydra.api.v1.services.users._roles import RolesMixin
from hydra.api.v1.services.users._sub_accounts import SubAccountsMixin
from hydra.db.mongodb import MongoDB


class UsersService(
    CoreMixin,
    RegistrationMixin,
    RolesMixin,
    CredentialsMixin,
    SubAccountsMixin,
):
    """User management service.

    Combines all user-related functionality through mixin composition.
    CoreMixin provides __init__(mongodb) and shared utility methods.
    """

    def __init__(self, mongodb: MongoDB):
        super().__init__(mongodb)


__all__ = ["UsersService"]
