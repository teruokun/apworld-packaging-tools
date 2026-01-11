# SPDX-License-Identifier: MIT
"""Error handling middleware and exception classes."""

from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


# Error codes following the design document
class ErrorCode:
    """Standard API error codes."""

    INVALID_MANIFEST = "INVALID_MANIFEST"
    INVALID_VERSION = "INVALID_VERSION"
    VERSION_EXISTS = "VERSION_EXISTS"
    PACKAGE_NOT_FOUND = "PACKAGE_NOT_FOUND"
    VERSION_NOT_FOUND = "VERSION_NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    RATE_LIMITED = "RATE_LIMITED"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    INVALID_REQUEST = "INVALID_REQUEST"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# HTTP status codes for each error
ERROR_STATUS_CODES = {
    ErrorCode.INVALID_MANIFEST: 400,
    ErrorCode.INVALID_VERSION: 400,
    ErrorCode.INVALID_REQUEST: 400,
    ErrorCode.VERSION_EXISTS: 409,
    ErrorCode.PACKAGE_NOT_FOUND: 404,
    ErrorCode.VERSION_NOT_FOUND: 404,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.CHECKSUM_MISMATCH: 400,
    ErrorCode.INTERNAL_ERROR: 500,
}


@dataclass
class ErrorDetail:
    """Detailed error information for a specific field or issue."""

    field: str
    error: str
    value: Any = None


@dataclass
class APIError(Exception):
    """Base API exception with structured error response.

    Attributes:
        code: Error code from ErrorCode class
        message: Human-readable error message
        details: List of detailed error information
    """

    code: str
    message: str
    details: list[ErrorDetail] = field(default_factory=list)

    @property
    def status_code(self) -> int:
        """Get HTTP status code for this error."""
        return ERROR_STATUS_CODES.get(self.code, 500)

    def to_response(self) -> dict:
        """Convert to API response format."""
        response = {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }
        if self.details:
            response["error"]["details"] = [
                {"field": d.field, "error": d.error} for d in self.details
            ]
        return response


class PackageNotFoundError(APIError):
    """Package does not exist."""

    def __init__(self, package_name: str):
        super().__init__(
            code=ErrorCode.PACKAGE_NOT_FOUND,
            message=f"Package '{package_name}' not found",
        )


class VersionNotFoundError(APIError):
    """Version does not exist."""

    def __init__(self, package_name: str, version: str):
        super().__init__(
            code=ErrorCode.VERSION_NOT_FOUND,
            message=f"Version '{version}' of package '{package_name}' not found",
        )


class VersionExistsError(APIError):
    """Version already exists (immutability violation)."""

    def __init__(self, package_name: str, version: str):
        super().__init__(
            code=ErrorCode.VERSION_EXISTS,
            message=f"Version '{version}' of package '{package_name}' already exists",
        )


class InvalidManifestError(APIError):
    """Manifest validation failed."""

    def __init__(self, message: str, details: list[ErrorDetail] | None = None):
        super().__init__(
            code=ErrorCode.INVALID_MANIFEST,
            message=message,
            details=details or [],
        )


class InvalidVersionError(APIError):
    """Version string does not follow semver."""

    def __init__(self, version: str):
        super().__init__(
            code=ErrorCode.INVALID_VERSION,
            message=f"Version '{version}' does not follow semantic versioning format",
        )


class UnauthorizedError(APIError):
    """Authentication required."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            code=ErrorCode.UNAUTHORIZED,
            message=message,
        )


class ForbiddenError(APIError):
    """Not authorized for this operation."""

    def __init__(self, message: str = "Not authorized for this operation"):
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
        )


class RateLimitedError(APIError):
    """Too many requests."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            message=f"Rate limit exceeded. Retry after {retry_after} seconds",
        )
        self.retry_after = retry_after


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle APIError exceptions."""
    headers = {}
    if isinstance(exc, RateLimitedError):
        headers["Retry-After"] = str(exc.retry_after)

    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(),
        headers=headers,
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": ErrorCode.INTERNAL_ERROR,
                "message": "An unexpected error occurred",
            }
        },
    )


def add_error_handlers(app: FastAPI) -> None:
    """Register error handlers with the FastAPI application."""
    app.add_exception_handler(APIError, api_error_handler)
    # Only catch generic exceptions in production
    # app.add_exception_handler(Exception, generic_error_handler)
