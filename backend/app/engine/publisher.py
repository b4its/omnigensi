import json
import logging
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)


class ExecutionPublisher:
    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self.channel = f"execution:{execution_id}"
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Publishes an event to the Redis SSE channel.
        Format: {"type": event_type, "data": payload}
        """
        message = json.dumps({
            "type": event_type,
            "data": payload,
            "execution_id": self.execution_id,
        })
        try:
            r = await self._get_redis()
            await r.publish(self.channel, message)
        except Exception as e:
            logger.warning(f"Failed to publish event {event_type} to Redis: {e}")

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
