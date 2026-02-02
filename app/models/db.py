from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.utils import utc_now


class ConversationLog(BaseModel):
    """MongoDB'ye kaydedilecek conversation yapısı."""

    session_id: str
    user_input: str
    intent: str
    agent_flow: list[str]
    final_response: dict[str, Any]
    created_at: datetime = Field(default_factory=utc_now)


class DiscoverySessionLog(BaseModel):
    """Discovery session kaydı."""

    session_id: str
    initial_problem: str
    conversation_turns: list[dict]
    discovery_output: dict
    created_at: datetime = Field(default_factory=utc_now)


class ProblemTreeLog(BaseModel):
    """Problem tree kaydı."""

    session_id: str
    discovery_id: str
    problem_tree: dict
    created_at: datetime = Field(default_factory=utc_now)
