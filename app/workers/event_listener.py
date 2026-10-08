import asyncio
import json
import logging
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


async def listen_to_task_events(redis_url: str = "redis://localhost:6379/0"):
    """Długo działający worker nasłuchujący wiadomości z kanału Pub/Sub."""
    redis = aioredis.from_url(redis_url, decode_responses=True)
    pubsub = redis.pubsub()

    # Subskrybujemy wybrany kanał
    await pubsub.subscribe("task_events")
    logger.info(
        "Zasubskrybowano kanał 'task_events'. Oczekiwanie na wiadomości...")

    try:
        # Pętla odbierająca wiadomości w czasie rzeczywistym
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                event_type = data.get("event")
                payload = data.get("data")

                logger.info(
                    f"Odebrano zdarzenie [{event_type}]: Task #{payload.get('task_id')} "
                    f"w projekcie #{payload.get('project_id')}"
                )

                # Tutaj np. wywołanie logiki WebSockets, audit logów czy analityki
    except asyncio.CancelledError:
        logger.info("Anulowano nasłuchiwanie Pub/Sub.")
    finally:
        await pubsub.unsubscribe("task_events")
        await redis.aclose()
