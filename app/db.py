from datetime import datetime
from functools import lru_cache
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings
from app.models.db import ConversationLog, DiscoverySessionLog, ProblemTreeLog


class MongoDBService:
    def __init__(self, mongodb_uri: str, database_name: str):
        self.client = AsyncIOMotorClient(mongodb_uri)
        self.db: AsyncIOMotorDatabase = self.client[database_name]

        self.conversations = self.db["conversations"]
        self.discovery_sessions = self.db["discovery_sessions"]
        self.problem_trees = self.db["problem_trees"]

    async def log_conversation(self, log: ConversationLog) -> str:
        """Conversation'ı kaydet."""
        result = await self.conversations.insert_one(log.model_dump())
        return str(result.inserted_id)

    async def save_discovery_session(self, log: DiscoverySessionLog) -> str:
        """Discovery session'ı kaydet."""
        result = await self.discovery_sessions.insert_one(log.model_dump())
        return str(result.inserted_id)

    async def save_problem_tree(self, log: ProblemTreeLog) -> str:
        """Problem tree'yi kaydet."""
        result = await self.problem_trees.insert_one(log.model_dump())
        return str(result.inserted_id)

    async def get_conversation_history(
        self, session_id: str, limit: int = 10
    ) -> list[dict]:
        """Session'a ait son N conversation'ı getir."""
        cursor = (
            self.conversations.find({"session_id": session_id})
            .sort("created_at", -1)
            .limit(limit)
        )

        return await cursor.to_list(length=limit)

    async def health_check(self) -> bool:
        """MongoDB bağlantı kontrolü."""
        try:
            await self.client.admin.command("ping")
            return True
        except Exception:
            return False

    async def close(self):
        """Bağlantıyı kapat."""
        self.client.close()


@lru_cache(maxsize=1)
def get_mongodb_service() -> MongoDBService:
    """Singleton MongoDB service."""
    settings = get_settings()
    return MongoDBService(
        mongodb_uri=settings.mongodb_uri, database_name=settings.mongodb_database
    )


if __name__ == "__main__":
    import asyncio

    async def test():
        print("=" * 60)
        print("MongoDB Service Test")
        print("=" * 60)

        service = get_mongodb_service()

        is_healthy = await service.health_check()
        if is_healthy:
            print("✓ MongoDB bağlantısı başarılı")
        else:
            print("✗ MongoDB bağlantısı başarısız")
            print("  docker-compose up -d ile servisleri başlat")
            return

        test_log = ConversationLog(
            session_id="test-session-123",
            user_input="Satışlarım düşüyor",
            intent="business_problem",
            agent_flow=["peer", "discovery", "structuring"],
            final_response={"status": "completed"},
        )

        log_id = await service.log_conversation(test_log)
        print(f"✓ Test log kaydedildi: {log_id}")

        history = await service.get_conversation_history("test-session-123", limit=1)
        print(f"✓ History alındı: {len(history)} kayıt")

        await service.close()
        print("\n✓ Tüm testler başarılı")
        print("=" * 60)

    asyncio.run(test())
