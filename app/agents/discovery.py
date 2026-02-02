
import json
from app.agents.base import BaseAgent
from app.config import get_settings
from app.llm import get_discovery_llm
from app.models.domain import ConversationTurn, DiscoveryOutput
from app.utils import clean_llm_json_response


class DiscoveryAgent(BaseAgent):
    def __init__(self):
        super().__init__(llm=get_discovery_llm())
        settings = get_settings()
        self.min_questions = settings.discovery_min_questions
        self.max_questions = settings.discovery_max_questions
        self._reset_state()

    def _reset_state(self):
        """Agent state'ini sıfırlar. Yeni discovery başlatırken çağrılır."""
        self.initial_problem: str = ""
        self.conversation_turns: list[ConversationTurn] = []
        self.current_question: str = ""

    def start_discovery(self, user_problem: str) -> str:
        self._reset_state()
        self.initial_problem = user_problem
        self.current_question = self._generate_question()
        return self.current_question

    async def start_discovery_async(self, user_problem: str) -> str:
        """FastAPI endpoint'lerinde kullanılacak."""
        self._reset_state()
        self.initial_problem = user_problem
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
        question = self.invoke_llm(
            prompt_name="discovery_question",
            prompt_variables={
                "initial_problem": self.initial_problem,
                "conversation_history": self._format_conversation_history()
                or "Henüz konuşma yok.",
                "question_number": len(self.conversation_turns) + 1,
            },
        )
        return question.strip()

    async def _generate_question_async(self) -> str:
        question = await self.invoke_llm_async(
            prompt_name="discovery_question",
            prompt_variables={
                "initial_problem": self.initial_problem,
                "conversation_history": self._format_conversation_history()
                or "Henüz konuşma yok.",
                "question_number": len(self.conversation_turns) + 1,
            },
        )
        return question.strip()

    def _should_complete(self) -> bool:
        turn_count = len(self.conversation_turns)
        if turn_count < self.min_questions:
            return False
        if turn_count >= self.max_questions:
            return True
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
            },
        )
        return self._parse_extraction(extraction_response)

    async def _extract_insights_async(self) -> DiscoveryOutput:
        extraction_response = await self.invoke_llm_async(
            prompt_name="discovery_extract",
            prompt_variables={
                "initial_problem": self.initial_problem,
                "conversation_history": self._format_conversation_history(),
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
            return DiscoveryOutput(
                customer_stated_problem=self.initial_problem,
                identified_business_problem="Extraction başarısız - manuel analiz gerekli",
                hidden_root_risk="Belirlenemedi",
                chat_summary=self._format_conversation_history(),
                conversation_turns=self.conversation_turns,
            )

    def _format_conversation_history(self) -> str:
        if not self.conversation_turns:
            return ""

        lines = []
        for turn in self.conversation_turns:
            lines.append(f"S{turn.turn_number}: {turn.question}")
            lines.append(f"C{turn.turn_number}: {turn.answer}")

        return "\n".join(lines)
