from app.core.exceptions.base import AppException


class RoadmapNotFoundError(AppException):
    def __init__(self, message: str = "Roadmap has not been generated yet") -> None:
        super().__init__(
            status_code=404,
            error_code="ROADMAP_NOT_FOUND",
            message=message,
        )

class SubjectNotFoundError(AppException):
    def __init__(self, message: str = "Subject not found") -> None:
        super().__init__(
            status_code=404,
            error_code="SUBJECT_NOT_FOUND",
            message=message,
        )

class TopicNotFoundError(AppException):
    def __init__(self, message: str = "Topic not found") -> None:
        super().__init__(
            status_code=404,
            error_code="TOPIC_NOT_FOUND",
            message=message,
        )

class SubtopicNotFoundError(AppException):
    def __init__(self, message: str = "Subtopic not found") -> None:
        super().__init__(
            status_code=404,
            error_code="SUBTOPIC_NOT_FOUND",
            message=message,
        )

class QuestionGenerationError(AppException):
    def __init__(self, message: str = "Failed to generate questions") -> None:
        super().__init__(
            status_code=500,
            error_code="QUESTION_GENERATION_ERROR",
            message=message,
        )

class PrepPathGenerationError(AppException):
    def __init__(self, message: str = "Failed to generate job prep path") -> None:
        super().__init__(
            status_code=500,
            error_code="PREP_PATH_GENERATION_ERROR",
            message=message,
        )

class RoadmapGenerationError(AppException):
    def __init__(self, message: str = "Failed to generate roadmap") -> None:
        super().__init__(
            status_code=500,
            error_code="ROADMAP_GENERATION_ERROR",
            message=message,
        )