from typing import Any

from pydantic import BaseModel, ConfigDict


class SuccessResponse[T](BaseModel):
    success: bool = True
    message: str
    data: T
    meta: dict[str, Any] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "success": True,
                    "message": "User retrieved successfully.",
                    "data": {"id": 1, "email": "user@example.com"},
                }
            ]
        }
    )


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorInfo(BaseModel):
    code: str
    details: list[ErrorDetail] | dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error: ErrorInfo