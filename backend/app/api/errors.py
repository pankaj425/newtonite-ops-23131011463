from typing import Any


class AppError(Exception):
    """Application error rendered as the project's standard error envelope."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}

    def to_body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


def not_found(message: str = "Resource not found") -> AppError:
    return AppError(404, "not_found", message)


def forbidden(message: str = "You do not have permission to perform this action") -> AppError:
    return AppError(403, "forbidden", message)


def unauthorized(message: str = "Authentication required") -> AppError:
    return AppError(401, "unauthorized", message)


def conflict(code: str, message: str, details: dict[str, Any] | None = None) -> AppError:
    return AppError(409, code, message, details)


def invalid(code: str, message: str, details: dict[str, Any] | None = None) -> AppError:
    return AppError(422, code, message, details)
