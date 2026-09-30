from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.health import router as health_router
from app.api.v1.auth import router as auth_router
from app.api.v1.datasets import router as datasets_router
from app.core.constants import API_V1_PREFIX


api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(datasets_router)
api_router.include_router(ai_router)
