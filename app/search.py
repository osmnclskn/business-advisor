# app/search.py

import asyncio
import time
from functools import lru_cache

from tavily import TavilyClient

from app.config import get_settings
from app.models.domain import ResearchResult, ResearchSource


class TavilyResearchService:
    """
    PeerAgent'ın business_info sorularını cevaplamak için Tavily Research API.

    Research tercih edildi çünkü Search Advanced'a göre:
    - Resmi kaynaklar getiriyor (OSD, TİM, Bakanlık raporları)
    - Yapılandırılmış Markdown çıktı (tablo, başlık, inline referans)
    - Spesifik veriler içeriyor (%, $, adet)

    Trade-off: 30-40 saniye sürüyor ama Celery'de çalışacağı için sorun değil.
    """

    def __init__(
        self, tavily_api_key: str, polling_interval: int, max_polling_attempts: int
    ):
        self.tavily_client = TavilyClient(api_key=tavily_api_key)
        self.polling_interval = polling_interval
        self.max_polling_attempts = max_polling_attempts

    def research(self, query: str, model: str = "mini") -> ResearchResult:
        """
        Senkron araştırma - Celery worker'da kullanılacak.

        Args:
            query: Araştırma sorusu
            model: "mini" (~30sn) veya "pro" (~60sn, çok kapsamlı konular için)
        """
        start_time = time.time()

        # Tavily Research async task oluşturuyor, hemen sonuç dönmüyor
        tavily_task = self._create_research_task(query, model)

        if tavily_task.get("error"):
            return ResearchResult(error=tavily_task["error"])

        task_id = tavily_task.get("request_id")
        if not task_id:
            return ResearchResult(error="Tavily task_id döndürmedi")

        # Polling ile tamamlanmasını bekle
        completed_research = self._wait_for_completion(task_id)

        if completed_research.get("error"):
            return ResearchResult(error=completed_research["error"])

        elapsed = time.time() - start_time
        return self._parse_tavily_response(completed_research, elapsed)

    async def research_async(self, query: str, model: str = "mini") -> ResearchResult:
        """
        Asenkron araştırma - FastAPI endpoint'lerinde kullanılacak.
        Tavily SDK research için async desteklemiyor, thread'e sarıyoruz.
        """
        return await asyncio.to_thread(self.research, query, model)

    def _create_research_task(self, query: str, model: str) -> dict:
        """Tavily'de research task başlatır."""
        try:
            return self.tavily_client.research(input=query, model=model)
        except Exception as tavily_error:
            return {"error": f"Research task oluşturulamadı: {tavily_error}"}

    def _wait_for_completion(self, task_id: str) -> dict:
        """
        Research tamamlanana kadar polling yapar.
        2sn interval optimal - daha sık polling Tavily rate limit'e takılır.
        """
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
        """Tavily raw response'unu ResearchResult'a dönüştürür."""
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
    """
    Singleton - tüm uygulama boyunca tek instance.
    lru_cache thread-safe ve test'te cache_clear ile reset edilebilir.
    """
    settings = get_settings()
    return TavilyResearchService(
        tavily_api_key=settings.tavily_api_key,
        polling_interval=settings.tavily_polling_interval,
        max_polling_attempts=settings.tavily_max_polling_attempts,
    )


if __name__ == "__main__":
    print("=" * 60)
    print("Tavily Research Service Test")
    print("=" * 60)

    research_service = get_research_service()

    test_query = "Türkiye'de e-ticaret sektöründe öne çıkan şirketler hangileri?"
    print(f"\n📋 Query: {test_query}")
    print("\n⏳ Araştırılıyor...")

    research_output = research_service.research(test_query)

    if not research_output.is_successful:
        print(f"\n❌ Hata: {research_output.error}")
    else:
        print(f"\n✅ Süre: {research_output.elapsed_seconds} saniye")
        print(f"📊 Kaynak: {len(research_output.sources)} adet")
        print(f"📏 Rapor: {len(research_output.content)} karakter")
        print(f"\n📝 Rapor özeti:\n{research_output.content[:1000]}...")

    print("\n" + "=" * 60)
