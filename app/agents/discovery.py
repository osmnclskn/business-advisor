import json
from app.agents.base import BaseAgent
from app.config import get_settings
from app.llm import get_discovery_llm
from app.models.domain import ConversationTurn, DiscoveryOutput
from app.utils import clean_llm_json_response, detect_language


class DiscoveryAgent(BaseAgent):
    def __init__(self):
        super().__init__(llm=get_discovery_llm())
        settings = get_settings()
        self.min_questions = settings.discovery_min_questions
        self.max_questions = settings.discovery_max_questions
        self._reset_state()

    def _reset_state(self):
        """Reset agent state. Called when starting a new discovery session."""
        self.initial_problem: str = ""
        self.conversation_turns: list[ConversationTurn] = []
        self.current_question: str = ""
        self.response_language: str = "Turkish"

    def start_discovery(self, user_problem: str, language: str | None = None) -> str:
        self._reset_state()
        self.initial_problem = user_problem
        # Language detected from initial problem if not provided by workflow
        self.response_language = language or detect_language(user_problem)
        self.current_question = self._generate_question()
        return self.current_question

    async def start_discovery_async(self, user_problem: str, language: str | None = None) -> str:
        self._reset_state()
        self.initial_problem = user_problem
        self.response_language = language or detect_language(user_problem)
        self.current_question = await self._generate_question_async()
        return self.current_question

    def continue_discovery(self, user_answer: str) -> str | DiscoveryOutput:
        self._record_turn(user_answer)

        if self._should_complete():
            return self._extract_insights()

        self.current_question = self._generate_question()
        return self.current_question

    async def continue_discovery_async(self, user_answer: str) -> str | DiscoveryOutput:
        self._record_turn(user_answer)

        if self._should_complete():
            return await self._extract_insights_async()

        self.current_question = await self._generate_question_async()
        return self.current_question

    def _record_turn(self, user_answer: str):
        turn = ConversationTurn(
            question=self.current_question,
            answer=user_answer,
            turn_number=len(self.conversation_turns) + 1,
        )
        self.conversation_turns.append(turn)

    def _generate_question(self) -> str:
        no_conversation_msg = (
            "Henüz konuşma yok." if self.response_language == "Turkish"
            else "No conversation yet."
        )
        question = self.invoke_llm(
            prompt_name="discovery_question",
            prompt_variables={
                "initial_problem": self.initial_problem,
                "conversation_history": self._format_conversation_history()
                or no_conversation_msg,
                "question_number": len(self.conversation_turns) + 1,
                "response_language": self.response_language,
            },
        )
        return question.strip()

    async def _generate_question_async(self) -> str:
        no_conversation_msg = (
            "Henüz konuşma yok." if self.response_language == "Turkish"
            else "No conversation yet."
        )
        question = await self.invoke_llm_async(
            prompt_name="discovery_question",
            prompt_variables={
                "initial_problem": self.initial_problem,
                "conversation_history": self._format_conversation_history()
                or no_conversation_msg,
                "question_number": len(self.conversation_turns) + 1,
                "response_language": self.response_language,
            },
        )
        return question.strip()

    def _should_complete(self) -> bool:
        turn_count = len(self.conversation_turns)
        if turn_count < self.min_questions:
            return False
        if turn_count >= self.max_questions:
            return True
        # Stop early if last 2 answers are detailed (>100 chars each)
        # Prevents over-questioning when user is being thorough
        recent_answers = [t.answer for t in self.conversation_turns[-2:]]
        if len(recent_answers) >= 2 and all(len(ans) > 100 for ans in recent_answers):
            return True

        return False

    def _extract_insights(self) -> DiscoveryOutput:
        extraction_response = self.invoke_llm(
            prompt_name="discovery_extract",
            prompt_variables={
                "initial_problem": self.initial_problem,
                "conversation_history": self._format_conversation_history(),
                "response_language": self.response_language,
            },
        )
        return self._parse_extraction(extraction_response)

    async def _extract_insights_async(self) -> DiscoveryOutput:
        extraction_response = await self.invoke_llm_async(
            prompt_name="discovery_extract",
            prompt_variables={
                "initial_problem": self.initial_problem,
                "conversation_history": self._format_conversation_history(),
                "response_language": self.response_language,
            },
        )
        return self._parse_extraction(extraction_response)

    def _parse_extraction(self, llm_response: str) -> DiscoveryOutput:
        try:
            cleaned = clean_llm_json_response(llm_response)
            parsed = json.loads(cleaned)

            return DiscoveryOutput(
                customer_stated_problem=parsed.get(
                    "customer_stated_problem", self.initial_problem
                ),
                identified_business_problem=parsed.get(
                    "identified_business_problem", ""
                ),
                hidden_root_risk=parsed.get("hidden_root_risk", ""),
                chat_summary=parsed.get("chat_summary", ""),
                conversation_turns=self.conversation_turns,
            )
        except json.JSONDecodeError:
            fallback_msg = (
                "Extraction başarısız - manuel analiz gerekli"
                if self.response_language == "Turkish"
                else "Extraction failed - manual analysis required"
            )
            return DiscoveryOutput(
                customer_stated_problem=self.initial_problem,
                identified_business_problem=fallback_msg,
                hidden_root_risk="Belirlenemedi" if self.response_language == "Turkish" else "Could not be determined",
                chat_summary=self._format_conversation_history(),
                conversation_turns=self.conversation_turns,
            )

    def _format_conversation_history(self) -> str:
        if not self.conversation_turns:
            return ""

        lines = []
        for turn in self.conversation_turns:
            lines.append(f"Q{turn.turn_number}: {turn.question}")
            lines.append(f"A{turn.turn_number}: {turn.answer}")

        return "\n".join(lines)