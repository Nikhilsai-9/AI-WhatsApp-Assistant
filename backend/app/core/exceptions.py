"""Custom exception hierarchy + FastAPI handlers."""

from __future__ import annotations

from fastapi import HTTPException, status


class AppError(Exception):
    """Base class for domain-specific errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ConsentRequired(AppError):
    """Raised when a contact has not approved AI replies."""

    status_code = status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS
    code = "consent_required"


class UpstreamError(AppError):
    """Wraps failures in 3rd-party AI / bridge services."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_error"


def http_exc_from_app(exc: AppError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )
