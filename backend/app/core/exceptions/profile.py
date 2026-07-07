from app.core.exceptions.base import AppException

class ProfileNotFoundError(AppException):
    def __init__(self, message: str = "Profile file not found") -> None:
        super().__init__(
            status_code=404,
            error_code="PROFILE_NOT_FOUND",
            message=message,
        )

class ProfileParseError(AppException):
    def __init__(self, message: str = "Failed to parse profile content") -> None:
        super().__init__(
            status_code=500,
            error_code="PROFILE_PARSE_ERROR",
            message=message,
        )

class ProfileIndexError(AppException):
    def __init__(self, message: str = "Failed to index profile into vector store") -> None:
        super().__init__(
            status_code=500,
            error_code="PROFILE_INDEX_ERROR",
            message=message,
        )