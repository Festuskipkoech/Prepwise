from app.core.exceptions.base import AppException

class JobNotFoundError(AppException):
    def __init__(self, message: str = "Job not found") -> None:
        super().__init__(
            status_code=404,
            error_code="JOB_NOT_FOUND",
            message=message,
        )

class JDFetchError(AppException):
    def __init__(self, message: str = "Failed to fetch job description from URL") -> None:
        super().__init__(
            status_code=502,
            error_code="JD_FETCH_ERROR",
            message=message,
        )

class JobAlreadyExistsError(AppException):
    def __init__(self, message: str = "A job with this URL already exists") -> None:
        super().__init__(
            status_code=409,
            error_code="JOB_ALREADY_EXISTS",
            message=message,
        )