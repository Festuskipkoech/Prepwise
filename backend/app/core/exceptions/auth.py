from app.core.exceptions.base import AppException

class AuthenticationError(AppException):
    def __init__(self, message: str = "Invalid email or password") -> None:
        super().__init__(
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            message=message,
        )

class InvalidTokenError(AppException):
    def __init__(self, message: str = "Session is invalid or has expired") -> None:
        super().__init__(
            status_code=401,
            error_code="INVALID_TOKEN",
            message=message,
        )

class InactiveAccountError(AppException):
    def __init__(self, message: str = "This account has been deactivated") -> None:
        super().__init__(
            status_code=403,
            error_code="INACTIVE_ACCOUNT",
            message=message,
        )

class UserAlreadyExistsError(AppException):
    def __init__(self, message: str = "An account with this email already exists") -> None:
        super().__init__(
            status_code=409,
            error_code="USER_ALREADY_EXISTS",
            message=message,
        )

class ForbiddenError(AppException):
    def __init__(self, message: str = "Action not allowed") -> None:
        super().__init__(
            status_code=403,
            error_code="FORBIDDEN",
            message=message,
        )