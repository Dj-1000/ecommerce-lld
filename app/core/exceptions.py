import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.responses import ErrorDetail, ErrorInfo, ErrorResponse

from app.core.logger import logger


class AppException(Exception):
    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: list[ErrorDetail] | dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def _error_response(
    *,
    status_code: int,
    message: str,
    code: str,
    details: list[ErrorDetail] | dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = ErrorResponse(
        message=message,
        error=ErrorInfo(code=code, details=details),
    )

    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True),
        headers=headers,
    )


async def app_exception_handler(
    request: Request,
    exc: AppException,
) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        message=exc.message,
        code=exc.code,
        details=exc.details,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    messages = {
        400: ("Bad request.", "BAD_REQUEST"),
        401: ("Authentication required or invalid.", "UNAUTHORIZED"),
        403: ("You do not have permission to perform this action.", "FORBIDDEN"),
        404: ("Resource not found.", "NOT_FOUND"),
        405: ("Method not allowed.", "METHOD_NOT_ALLOWED"),
        409: ("Request conflicts with the current resource state.", "CONFLICT"),
        429: ("Too many requests. Please try again later.", "RATE_LIMIT_EXCEEDED"),
    }

    default_message, default_code = messages.get(
        exc.status_code,
        ("Request failed.", "HTTP_ERROR"),
    )

    # Preserve explicit application messages where they are safe to expose.
    message = exc.detail if isinstance(exc.detail, str) else default_message

    return _error_response(
        status_code=exc.status_code,
        message=message,
        code=default_code,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in error["loc"] if part != "body"),
            message=error["msg"],
        )
        for error in exc.errors()
    ]

    return _error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Request validation failed.",
        code="VALIDATION_ERROR",
        details=details,
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        f"Unhandled exception while processing {request.method} {request.url.path}"
    )

    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="An unexpected error occurred.",
        code="INTERNAL_SERVER_ERROR",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,
    )
    app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,
    )
    app.add_exception_handler(
        Exception,
        unhandled_exception_handler,
    )