from app.core.exceptions.base import AppException

class AuthenticationError(AppException):
    def __init__(self, message: str = "Invalid email or password") -> None:
        super().__init__(
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            message=message,
        )

class InvalidTokenError(AppException):
    def __init__(self, message: str = "Token is invalid or has expired") -> None:
        super().__init__(
            status_code=401,
            error_code="INVALID_TOKEN",
            message=message,
        )

class ForbiddenError(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action") -> None:
        super().__init__(
            status_code=403,
            error_code="FORBIDDEN",
            message=message,
        )