"""Authentication models - re-export module.

All auth models are split into sub-modules for maintainability:
- auth_enums.py: Enums, role constants, and role utility functions
- auth_requests.py: All request models
- auth_responses.py: All response models

This module re-exports everything for backward compatibility so existing
``from hydra.api.v1.models.auth import X`` imports continue to work.
"""

# Enums and role utilities
from hydra.api.v1.models.auth_enums import (  # noqa: F401
    ApiKeyType,
    Role,
    TokenScope,
    TokenType,
    UserStatus,
    ROLE_LEVELS,
    ROLE_LIMITS,
    can_create_token_for_role,
    can_have_sub_accounts,
    get_role_level,
    is_valid_sub_account_role,
)

# Request models
from hydra.api.v1.models.auth_requests import (  # noqa: F401
    ApproveUserRequest,
    ChangePasswordRequest,
    CreateApiKeyRequest,
    CreateRegistrationTokenRequest,
    CreateUserRequest,
    ElevateRoleRequest,
    ForgotPasswordRequest,
    GrantTemporaryRoleRequest,
    LoginRequest,
    NodeRegistrationRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    SubAccountLinkRequest,
    UserRegistrationRequest,
)

# Response models
from hydra.api.v1.models.auth_responses import (  # noqa: F401
    ApiKeyListItem,
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiKeyRevokeResponse,
    ApprovalResponse,
    ChangePasswordResponse,
    CurrentUserResponse,
    ForgotPasswordResponse,
    LoginResponse,
    NodeApiKeyRefreshResponse,
    NodeRegistrationResponse,
    PendingUserInfo,
    PendingUsersListResponse,
    RegistrationTokenListItem,
    RegistrationTokenListResponse,
    RegistrationTokenResponse,
    RegistrationTokenUsage,
    RejectionResponse,
    ResetPasswordResponse,
    RoleElevationResponse,
    SubAccountInfo,
    SubAccountLinkResponse,
    SubAccountListResponse,
    TemporaryRole,
    TemporaryRoleGrantResponse,
    TemporaryRoleRevokeResponse,
    TokenResponse,
    UserDetailResponse,
    UserInfo,
    UserListItem,
    UserListResponse,
    UserRegistrationResponse,
)
