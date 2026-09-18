"""Domain exceptions raised by services, mapped to error envelope by handlers."""

from app.core.errors import AppError


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = 409


class InvalidCredentialsError(AppError):
    code = "AUTHENTICATION_FAILED"
    status_code = 401


class AccountDisabledError(AppError):
    code = "ACCOUNT_DISABLED"
    status_code = 403


class RefreshTokenInvalidError(AppError):
    code = "REFRESH_TOKEN_INVALID"
    status_code = 401


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 422
