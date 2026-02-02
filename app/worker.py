import asyncio

from celery import Celery

from app.agents.workflow import AdvisorWorkflow, create_workflow_with_checkpointer
from app.cache import get_redis_cache
from app.config import get_settings
from app.db import get_mongodb_service
from app.logging import LogContext, get_logger
from app.models.db import ConversationLog

settings = get_settings()
logger = get_logger()

celery_app = Celery(
    "advisor_worker", broker=settings.redis_url, backend=settings.redis_url
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=3600,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=270,
)

_workflow: AdvisorWorkflow | None = None


def _get_workflow() -> AdvisorWorkflow:
    """Worker process başına tek workflow instance."""
    global _workflow
    if _workflow is None:
        _workflow = create_workflow_with_checkpointer()
    return _workflow


def _persist_completed_session(session_id: str, user_input: str, state: dict):
    try:
        db = get_mongodb_service()

        conversation = ConversationLog(
            session_id=session_id,
            user_input=user_input,
            intent=state.get("intent", "unknown"),
            agent_flow=state.get("agent_flow", []),
            final_response={
                "discovery_output": state.get("discovery_output"),
                "problem_tree": state.get("problem_tree"),
                "action_plan": state.get("action_plan"),
                "risk_analysis": state.get("risk_analysis"),
                "business_report": state.get("business_report"),
            },
        )

        asyncio.run(db.log_conversation(conversation))
        logger.info("Session persisted to MongoDB")

    except Exception as persist_error:
        logger.warning(f"MongoDB persist failed: {persist_error}")


@celery_app.task(bind=True, name="process_agent_task")
def process_agent_task(
    self, session_id: str, task: str, existing_state: dict | None = None
) -> dict:
    with LogContext(session_id=session_id, agent="worker"):
        try:
            workflow = _get_workflow()
            cache = get_redis_cache()
            cache.connect()

            if existing_state and existing_state.get("awaiting_user_input"):
                logger.info(f"Continuing discovery: {task[:50]}...")
                state = workflow.continue_session(existing_state, task)
            else:
                logger.info(f"New task: {task[:50]}...")
                state = workflow.run(session_id, task)

            # Redis session yönetimi
            if state["awaiting_user_input"]:
                cache.save_session(
                    session_id, dict(state), settings.session_ttl_seconds
                )
            elif state["is_complete"] and existing_state:
                cache.delete_session(session_id)

            # Tamamlanan session'ları MongoDB'ye kaydet
            if state["is_complete"]:
                _persist_completed_session(session_id, task, state)

            logger.info(f"Task completed - intent: {state['intent']}")

            return {"success": True, "session_id": session_id, "state": dict(state)}

        except Exception as e:
            logger.error(f"Task failed: {str(e)}")
            return {"success": False, "session_id": session_id, "error": str(e)}

