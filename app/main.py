"""
FastAPI Scraper Server - Main Application Entry Point
With Selenium Scraping and Multi-Bot Telegram Support (30+ bots)
Designed for deployment on Coolify with Docker
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1 import router as api_v1_router
from app.core.config import settings
from app.middleware.api_key import APIKeyMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("🚀 Starting FastAPI Scraper Server...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    
    # Initialize Database
    from app.db.session import engine, Base
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Uncomment to reset DB
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ Database tables created")
    
    # Initialize bot manager
    from app.services.bot_manager import bot_manager
    
    await bot_manager.initialize()
    bot_count = bot_manager.get_bot_count()
    
    if bot_count > 0:
        logger.info(f"📱 Loaded {bot_count} bot(s)")
        for bot in bot_manager.get_active_bots():
            logger.info(f"   - {bot.bot_name} ({bot.bot_id})")
    else:
        logger.info("ℹ️ No bots configured. Add bots via API: POST /api/v1/bots")
    
    yield
    
    # Cleanup
    logger.info("👋 Shutting down FastAPI Scraper Server...")
    await bot_manager.close()
    logger.info("✅ Shutdown complete")


from scalar_fastapi import get_scalar_api_reference

def create_application() -> FastAPI:
    """Application factory pattern for creating FastAPI instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.PROJECT_DESCRIPTION,
        version=settings.VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
        lifespan=lifespan,
    )

    if settings.ENABLE_DOCS:
        @app.get("/docs", include_in_schema=False)
        async def scalar_html():
            return get_scalar_api_reference(
                openapi_url=app.openapi_url,
                title=app.title,
            )

    # Add middlewares
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.ENVIRONMENT == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )

    # Add custom API Key middleware
    app.add_middleware(APIKeyMiddleware)

    # Include routers
    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - service info."""
    from app.services.bot_manager import bot_manager
    
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "bots": {
            "total": bot_manager.get_bot_count(),
            "active": len(bot_manager.get_active_bots()),
        },
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint."""
    from app.services.bot_manager import bot_manager
    
    active_bots = bot_manager.get_active_bots()
    
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION,
        "bots": {
            "total": bot_manager.get_bot_count(),
            "active": len(active_bots),
            "names": [b.bot_name for b in active_bots],
        },
        "services": {
            "scraper": "ready",
            "telegram": "ready" if bot_manager.get_bot_count() > 0 else "no_bots",
        },
    }
