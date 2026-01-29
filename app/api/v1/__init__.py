"""
API v1 Router - combines all endpoint routers.
"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.bot.actions import router as bot_actions_router

router = APIRouter()

# Include all routers
router.include_router(auth_router)
router.include_router(webhooks_router)
router.include_router(bot_actions_router, prefix="/bot", tags=["Bot Actions"])
