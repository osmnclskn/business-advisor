from app.agents.base import BaseAgent
from app.llm import get_peer_llm
from app.models.domain import IntentType
from app.search import get_research_service
from app.utils import detect_language


class PeerAgent(BaseAgent):
    def __init__(self):
        super().__init__(llm=get_peer_llm())
        self.research_service = get_research_service()

    def classify_intent(self, user_message: str) -> IntentType:
        classification_response = self.invoke_llm(
            prompt_name="peer_classify", prompt_variables={"user_input": user_message}
        )

        return self._parse_intent(classification_response)

    async def classify_intent_async(self, user_message: str) -> IntentType:
        classification_response = await self.invoke_llm_async(
            prompt_name="peer_classify", prompt_variables={"user_input": user_message}
        )

        return self._parse_intent(classification_response)

    def _parse_intent(self, llm_response: str) -> IntentType:
        cleaned = llm_response.strip().lower()

        for intent in IntentType:
            if intent.value in cleaned:
                return intent
        return IntentType.NON_BUSINESS

    def handle_business_info(self, user_message: str) -> dict:
        detected_lang = detect_language(user_message)
        research_output = self.research_service.research(user_message)

        if not research_output.is_successful:
            return {
                "message": f"Araştırma yapılırken sorun oluştu: {research_output.error}",
                "full_report": None,
                "sources": [],
                "research_time": 0,
            }
        summarized = self.invoke_llm(
            prompt_name="peer_summarize",
            prompt_variables={
                "research_content": research_output.content,
                "response_language": detected_lang,
            },
        )

        return {
            "message": summarized,
            "full_report": research_output.content,
            "sources": research_output.source_urls,
            "research_time": research_output.elapsed_seconds,
        }

    async def handle_business_info_async(self, user_message: str) -> dict:
        detected_lang = detect_language(user_message)
        research_output = await self.research_service.research_async(user_message)

        if not research_output.is_successful:
            return {
                "message": f"Araştırma yapılırken sorun oluştu: {research_output.error}",
                "full_report": None,
                "sources": [],
                "research_time": 0,
            }

        summarized = await self.invoke_llm_async(
            prompt_name="peer_summarize",
            prompt_variables={
                "research_content": research_output.content,
                "response_language": detected_lang,
            },
        )

        return {
            "message": summarized,
            "full_report": research_output.content,
            "sources": research_output.source_urls,
            "research_time": research_output.elapsed_seconds,
        }

    def handle_business_problem(self, user_message: str) -> dict:
        detected_lang = detect_language(user_message)

        routing_messages = {
            "Turkish": (
                "Anlattığınız durumun detaylı bir problem analizi gerektirdiğini görüyorum. "
                "Sizi problem keşfi sürecine yönlendiriyorum."
            ),
            "English": (
                "I can see that your situation requires a detailed problem analysis. "
                "I'm routing you to the problem discovery process."
            ),
        }

        return {
            "message": routing_messages.get(detected_lang, routing_messages["English"]),
            "route_to": "discovery",
            "original_input": user_message,
        }

    def handle_non_business(self, user_message: str) -> dict:
        detected_lang = detect_language(user_message)
        rejection = self.invoke_llm(
            prompt_name="peer_respond",
            prompt_variables={
                "response_type": "non_business",
                "user_input": user_message,
                "search_results": "",
                "response_language": detected_lang,
            },
        )

        return {"message": rejection, "route_to": None}

    async def handle_non_business_async(self, user_message: str) -> dict:
        detected_lang = detect_language(user_message)
        rejection = await self.invoke_llm_async(
            prompt_name="peer_respond",
            prompt_variables={
                "response_type": "non_business",
                "user_input": user_message,
                "search_results": "",
                "response_language": detected_lang,
            },
        )

        return {"message": rejection, "route_to": None}

    def process(self, user_message: str) -> dict:
        detected_intent = self.classify_intent(user_message)
        detected_lang = detect_language(user_message)

        if detected_intent == IntentType.BUSINESS_INFO:
            result = self.handle_business_info(user_message)
        elif detected_intent == IntentType.BUSINESS_PROBLEM:
            result = self.handle_business_problem(user_message)
        else:
            result = self.handle_non_business(user_message)

        return {"intent": detected_intent.value, "language": detected_lang, **result}

    async def process_async(self, user_message: str) -> dict:
        detected_intent = await self.classify_intent_async(user_message)
        detected_lang = detect_language(user_message)

        if detected_intent == IntentType.BUSINESS_INFO:
            result = await self.handle_business_info_async(user_message)
        elif detected_intent == IntentType.BUSINESS_PROBLEM:
            result = self.handle_business_problem(user_message)
        else:
            result = await self.handle_non_business_async(user_message)

        return {"intent": detected_intent.value, "language": detected_lang, **result}