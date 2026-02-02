import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.cache import get_redis_cache
from app.config import get_settings
from app.db import get_mongodb_service
from app.logging import LogContext, get_logger
from app.models.api import (
    AgentExecuteRequest,
    ErrorResponse,
    HealthResponse,
    TaskStatusResponse,
    TaskSubmitResponse,
)
from app.worker import celery_app, process_agent_task

settings = get_settings()
logger = get_logger()

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting...")

    db_service = get_mongodb_service()
    if await db_service.health_check():
        logger.info("MongoDB connection established")
    else:
        logger.warning("MongoDB connection failed - logging disabled")

    cache = get_redis_cache()
    cache.connect()

    yield

    logger.info("Application shutting down...")
    await db_service.close()
    cache.close()


app = FastAPI(
    title="Business Advisor API",
    description="Agentic business advisory system with multi-agent orchestration",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    db_service = get_mongodb_service()
    db_healthy = await db_service.health_check()

    cache = get_redis_cache()
    redis_healthy = cache.is_connected()

    overall_status = "healthy" if (db_healthy and redis_healthy) else "degraded"

    return HealthResponse(
        status=overall_status, mongodb=db_healthy, redis=redis_healthy, version="1.0.0"
    )


@app.post(
    "/v1/agent/execute",
    response_model=TaskSubmitResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"description": "Rate limit exceeded"},
    },
    tags=["Agent"],
)
@limiter.limit(settings.rate_limit_execute)
async def execute_agent(request: Request, body: AgentExecuteRequest):
    """
    Task'ı queue'ya gönder.

    Rate limit: 20/dakika
    """
    if not body.task or not body.task.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Task cannot be empty"
        )

    cache = get_redis_cache()

    existing_state = None
    if body.session_id:
        existing_state = cache.get_session(body.session_id)
        if not existing_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or expired",
            )

    session_id = body.session_id or str(uuid.uuid4())

    with LogContext(session_id=session_id, agent="api"):
        logger.info(f"Queuing task: {body.task[:50]}...")

        celery_task = process_agent_task.delay(
            session_id=session_id, task=body.task, existing_state=existing_state
        )

        logger.info(f"Task queued: {celery_task.id}")

        return TaskSubmitResponse(
            task_id=celery_task.id,
            session_id=session_id,
            status="pending",
            message="Task submitted to queue",
        )


@app.get(
    "/v1/tasks/{task_id}",
    response_model=TaskStatusResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["Agent"],
)
@limiter.limit(settings.rate_limit_tasks)
async def get_task_status(request: Request, task_id: str):
    """
    Task durumunu sorgula (polling).

    Rate limit: 60/dakika
    """
    result = celery_app.AsyncResult(task_id)

    if result.state == "PENDING":
        return TaskStatusResponse(task_id=task_id, status="pending")

    if result.state == "STARTED":
        return TaskStatusResponse(task_id=task_id, status="processing")

    if result.state == "SUCCESS":
        task_result = result.result

        if task_result.get("success"):
            state = task_result["state"]
            return TaskStatusResponse(
                task_id=task_id,
                status="completed",
                result=_build_response_dict(task_result["session_id"], state),
            )
        return TaskStatusResponse(
            task_id=task_id,
            status="failed",
            error=task_result.get("error", "Unknown error"),
        )

    if result.state == "FAILURE":
        return TaskStatusResponse(
            task_id=task_id, status="failed", error=str(result.result)
        )

    return TaskStatusResponse(task_id=task_id, status=result.state.lower())


@app.get("/v1/sessions/{session_id}", tags=["Agent"])
@limiter.limit(settings.rate_limit_sessions)
async def get_session_status(request: Request, session_id: str):
    """
    Session durumunu sorgula.

    Rate limit: 30/dakika
    """
    cache = get_redis_cache()
    state = cache.get_session(session_id)

    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    return {
        "session_id": session_id,
        "current_agent": state["current_agent"],
        "awaiting_user_input": state["awaiting_user_input"],
        "is_complete": state["is_complete"],
        "agent_flow": state["agent_flow"],
    }


def _build_response_dict(session_id: str, state: dict) -> dict:
    if state.get("error"):
        return {
            "session_id": session_id,
            "intent": state["intent"] or "error",
            "message": state["error"],
            "data": None,
            "is_complete": True,
            "requires_input": False
        }

    if state["intent"] in ["business_info", "non_business"]:
        peer_response = state.get("peer_response", {})
        return {
            "session_id": session_id,
            "intent": state["intent"],
            "message": peer_response.get("message", ""),
            "data": {
                "sources": peer_response.get("sources", []),
                "full_report": peer_response.get("full_report")
            } if state["intent"] == "business_info" else None,
            "is_complete": True,
            "requires_input": False
        }

    if state["awaiting_user_input"]:
        return {
            "session_id": session_id,
            "intent": "business_problem",
            "message": state["discovery_question"],
            "data": None,
            "is_complete": False,
            "requires_input": True
        }

    if state["is_complete"] and state.get("business_report"):
        return {
            "session_id": session_id,
            "intent": "business_problem",
            "message": "Problem analizi tamamlandı",
            "data": {
                "discovery_output": state["discovery_output"],
                "problem_tree": state["problem_tree"],
                "action_plan": state["action_plan"],
                "risk_analysis": state["risk_analysis"],
                "business_report": state["business_report"],
            },
            "is_complete": True,
            "requires_input": False
        }

    return {
        "session_id": session_id,
        "intent": state["intent"] or "unknown",
        "message": "Unexpected state",
        "data": None,
        "is_complete": True,
        "requires_input": False
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
