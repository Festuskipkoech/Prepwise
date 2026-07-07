from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions.base import AppException

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        return JSONResponse(
            status_code = exc.status_code,
            content = {
                "error_code": exc.error_code,
                "message": exc.message,
                "status_code": exc.status_code,
            }
        )
    
    @app.exception_handler(Exception)
    async def unhandled_exception(
        request: Request, exc: Exception
        ) -> JSONResponse:
            return JSONResponse(
                status_code = 500,
                content = {
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occured",
                    "status_code": 500,
                }

            )
    