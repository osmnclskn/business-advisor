
import asyncio
import time
from functools import lru_cache

from tavily import TavilyClient

from app.config import get_settings
from app.models.domain import ResearchResult, ResearchSource


class TavilyResearchService:
    def __init__(
        self, tavily_api_key: str, polling_interval: int, max_polling_attempts: int
    ):
        self.tavily_client = TavilyClient(api_key=tavily_api_key)
        self.polling_interval = polling_interval
        self.max_polling_attempts = max_polling_attempts

    def research(self, query: str, model: str = "mini") -> ResearchResult:
        start_time = time.time()

        tavily_task = self._create_research_task(query, model)

        if tavily_task.get("error"):
            return ResearchResult(error=tavily_task["error"])

        task_id = tavily_task.get("request_id")
        if not task_id:
            return ResearchResult(error="Tavily task_id döndürmedi")

        completed_research = self._wait_for_completion(task_id)

        if completed_research.get("error"):
            return ResearchResult(error=completed_research["error"])

        elapsed = time.time() - start_time
        return self._parse_tavily_response(completed_research, elapsed)

    async def research_async(self, query: str, model: str = "mini") -> ResearchResult:
        return await asyncio.to_thread(self.research, query, model)

    def _create_research_task(self, query: str, model: str) -> dict:
        try:
            return self.tavily_client.research(input=query, model=model)
        except Exception as tavily_error:
            return {"error": f"Research task oluşturulamadı: {tavily_error}"}

    def _wait_for_completion(self, task_id: str) -> dict:
        for _ in range(self.max_polling_attempts):
            time.sleep(self.polling_interval)

            try:
                tavily_status = self.tavily_client.get_research(task_id)
            except Exception as polling_error:
                return {"error": f"Polling hatası: {polling_error}"}

            current_status = tavily_status.get("status")

            if current_status == "completed":
                return tavily_status

            if current_status == "failed":
                failure_reason = tavily_status.get("error", "Bilinmeyen hata")
                return {"error": f"Tavily research başarısız: {failure_reason}"}

        max_wait = self.max_polling_attempts * self.polling_interval
        return {"error": f"Research {max_wait} saniyede tamamlanmadı"}

    def _parse_tavily_response(
        self, tavily_response: dict, elapsed: float
    ) -> ResearchResult:
        parsed_sources = []

        for raw_source in tavily_response.get("sources", []):
            if isinstance(raw_source, dict):
                parsed_sources.append(
                    ResearchSource(
                        title=raw_source.get("title", ""), url=raw_source.get("url", "")
                    )
                )

        return ResearchResult(
            content=tavily_response.get("content", ""),
            sources=parsed_sources,
            elapsed_seconds=round(elapsed, 2),
        )


@lru_cache(maxsize=1)
def get_research_service() -> TavilyResearchService:
    settings = get_settings()
    return TavilyResearchService(
        tavily_api_key=settings.tavily_api_key,
        polling_interval=settings.tavily_polling_interval,
        max_polling_attempts=settings.tavily_max_polling_attempts,
    )


