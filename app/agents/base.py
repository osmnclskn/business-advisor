from abc import ABC
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.prompts import format_prompt, load_prompt


class BaseAgent(ABC):
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    @property
    def agent_name(self) -> str:
        class_name = self.__class__.__name__
        return class_name.replace("Agent", "").lower()

    def _build_messages(
        self, prompt_name: str, prompt_variables: dict[str, Any]
    ) -> list:
        prompt_config = load_prompt(prompt_name)
        formatted = format_prompt(prompt_config, **prompt_variables)

        return [
            SystemMessage(content=formatted["system"]),
            HumanMessage(content=formatted["user"]),
        ]

    def invoke_llm(self, prompt_name: str, prompt_variables: dict[str, Any]) -> str:
        messages = self._build_messages(prompt_name, prompt_variables)
        llm_response = self.llm.invoke(messages)
        return llm_response.content

    async def invoke_llm_async(
        self, prompt_name: str, prompt_variables: dict[str, Any]
    ) -> str:
        messages = self._build_messages(prompt_name, prompt_variables)
        llm_response = await self.llm.ainvoke(messages)
        return llm_response.content
