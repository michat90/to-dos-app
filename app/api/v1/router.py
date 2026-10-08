from fastapi import APIRouter

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.tasks import router as tasks_router

api_router = APIRouter()

# Podpinamy poszczególne moduły
api_router.include_router(auth_router)
api_router.include_router(projects_router)
api_router.include_router(tasks_router)
