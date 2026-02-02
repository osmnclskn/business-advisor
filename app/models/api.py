# app/models/api.py

from typing import Any

from pydantic import BaseModel, Field


class AgentExecuteRequest(BaseModel):
    """POST /v1/agent/execute request body."""

    task: str = Field(
        ...,
        min_length=1,
        description="Kullanıcının görevi, sorusu veya discovery cevabı",
        examples=["Satışlarım düşüyor, nedenini anlamak istiyorum"],
    )
    session_id: str | None = Field(
        default=None, description="Mevcut session'ı devam ettirmek için session ID"
    )


class AgentExecuteResponse(BaseModel):
    """Standard response for agent endpoints."""

    session_id: str
    intent: str
    message: str
    data: dict[str, Any] | None = None
    is_complete: bool
    requires_input: bool


class TaskSubmitResponse(BaseModel):
    """Response when task is submitted to queue."""

    task_id: str
    session_id: str
    status: str = "pending"
    message: str = "Task submitted successfully"


class TaskStatusResponse(BaseModel):
    """Response for task status check."""

    task_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str
    detail: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    mongodb: bool
    redis: bool
    version: str
