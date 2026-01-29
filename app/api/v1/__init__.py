"""
API v1 Router - combines all endpoint routers.
"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.items import router as items_router
from app.api.v1.users import router as users_router
from app.api.v1.scraper import router as scraper_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.bots import router as bots_router

router = APIRouter()

# Include all routers
router.include_router(auth_router)
router.include_router(items_router)
router.include_router(users_router)
router.include_router(scraper_router)
router.include_router(webhooks_router)
router.include_router(bots_router)
