from app.core.exceptions.base import AppException

class DocumentNotFoundError(AppException):
    def __init__(self, message: str = "Document not found") -> None:
        super().__init__(
            status_code=404,
            error_code="DOCUMENT_NOT_FOUND",
            message=message,
        )

class DocumentGenerationError(AppException):
    def __init__(self, message: str = "Failed to generate document") -> None:
        super().__init__(
            status_code=500,
            error_code="DOCUMENT_GENERATION_ERROR",
            message=message,
        )

class JDMissingError(AppException):
    def __init__(self, message: str = "Job has no JD text to generate documents from") -> None:
        super().__init__(
            status_code=422,
            error_code="JD_MISSING",
            message=message,
        )