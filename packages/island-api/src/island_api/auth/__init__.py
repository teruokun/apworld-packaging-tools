# SPDX-License-Identifier: MIT
"""Authentication handlers."""

from .oidc import (
    OIDCClaims,
    require_trusted_publisher_for_package,
    validate_oidc_token,
    validate_trusted_publisher,
    verify_oidc_token,
)
from .tokens import (
    AuthenticatedUser,
    TokenInfo,
    generate_api_token,
    get_current_user,
    get_optional_user,
    hash_token,
    parse_authorization_header,
    require_scope,
    validate_api_token,
)

__all__ = [
    # Token auth
    "AuthenticatedUser",
    "TokenInfo",
    "generate_api_token",
    "get_current_user",
    "get_optional_user",
    "hash_token",
    "parse_authorization_header",
    "require_scope",
    "validate_api_token",
    # OIDC auth
    "OIDCClaims",
    "require_trusted_publisher_for_package",
    "validate_oidc_token",
    "validate_trusted_publisher",
    "verify_oidc_token",
]
