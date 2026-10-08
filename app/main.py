from contextlib import asynccontextmanager
import fastapi
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi import Depends
import redis.asyncio as aioredis

from app.core.redis import get_redis
from app.api.v1.router import api_router
from app.core.exceptions import BusinessException, NotFoundException
from app.core.logging import get_logger, setup_logging

# Initialize logger configuration
setup_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    logger.info("Application startup", service="todo-api")
    yield
    logger.info("Application shutdown", service="todo-api")


app = fastapi.FastAPI(
    title="To-Do API",
    lifespan=lifespan,
)

# Podpinamy wszystkie trasy z prefiksem wersjonowania /api/v1
app.include_router(api_router, prefix="/api/v1")

# Globalny handler dla wszystkich błędów typu Not Found (404)


@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": exc.message},
    )


@app.exception_handler(BusinessException)
async def business_exception_handler(request: Request, exc: BusinessException):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message},
    )


@app.get("/health/redis")
async def redis_health(redis: aioredis.Redis = Depends(get_redis)):
    pong = await redis.ping()
    return {"redis_ping": pong}
