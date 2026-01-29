"""
Webhook and Bot Management API endpoints.
Handles incoming Telegram webhooks and bot CRUD operations.
"""
import hashlib
import hmac
import logging
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.bot_manager import bot_manager, BotConfig
from app.services.command_handler import command_handler

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Webhooks & Bots"])


# ============== Schemas ==============

class BotRegisterRequest(BaseModel):
    """Request to register a new bot."""
    bot_id: str = Field(..., min_length=1, max_length=50, description="Unique bot identifier")
    bot_token: str = Field(..., min_length=40, description="Telegram bot token from @BotFather")
    bot_name: str = Field(..., min_length=1, max_length=100, description="Display name for the bot")
    channel_id: str = Field(..., description="Channel ID (@channel or -100xxx)")
    allowed_users: List[int] = Field(default=[], description="User IDs allowed to use bot (empty = all)")
    take_screenshot: bool = Field(default=True, description="Enable screenshots")
    default_wait_time: int = Field(default=5, ge=0, le=30, description="Default wait time")
    default_timeout: int = Field(default=30, ge=10, le=120, description="Default timeout")


class BotUpdateRequest(BaseModel):
    """Request to update a bot."""
    bot_name: Optional[str] = None
    channel_id: Optional[str] = None
    allowed_users: Optional[List[int]] = None
    is_active: Optional[bool] = None
    take_screenshot: Optional[bool] = None
    default_wait_time: Optional[int] = Field(None, ge=0, le=30)
    default_timeout: Optional[int] = Field(None, ge=10, le=120)
    send_to_channel: Optional[bool] = None


class BotResponse(BaseModel):
    """Bot information response."""
    bot_id: str
    bot_name: str
    channel_id: str
    is_active: bool
    webhook_url: Optional[str]
    allowed_users: List[int]
    take_screenshot: bool
    default_wait_time: int
    default_timeout: int
    send_to_channel: bool


class WebhookSetupRequest(BaseModel):
    """Request to setup webhooks."""
    base_url: str = Field(..., description="Base URL for webhooks (e.g., https://api.example.com)")
    secret: Optional[str] = Field(None, description="Optional webhook secret")


class WebhookSetupResponse(BaseModel):
    """Webhook setup response."""
    success: bool
    results: Dict[str, bool]
    webhook_urls: Dict[str, str]


# ============== Webhook Endpoints ==============

@router.post(
    "/webhook/{bot_id}",
    summary="Telegram webhook endpoint",
    description="Receives updates from Telegram for a specific bot.",
    include_in_schema=False,  # Hide from docs as it's for Telegram
)
async def telegram_webhook(
    bot_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
):
    """
    Handle incoming Telegram webhook for a specific bot.
    
    This endpoint receives messages from users who interact with the bot.
    The bot then processes commands and performs scraping.
    """
    # Get bot config
    bot = bot_manager.get_bot(bot_id)
    if not bot:
        logger.warning(f"Webhook received for unknown bot: {bot_id}")
        raise HTTPException(status_code=404, detail="Bot not found")
    
    # Verify webhook secret if configured
    if bot.webhook_secret:
        if x_telegram_bot_api_secret_token != bot.webhook_secret:
            logger.warning(f"Invalid webhook secret for bot: {bot_id}")
            raise HTTPException(status_code=403, detail="Invalid secret")
    
    # Parse update
    try:
        update_data = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook data: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    logger.info(f"Webhook received for bot {bot_id}: update_id={update_data.get('update_id')}")
    
    # Process in background to respond quickly to Telegram
    background_tasks.add_task(
        command_handler.handle_update,
        bot_id=bot_id,
        update_data=update_data,
    )
    
    # Must return 200 quickly to Telegram
    return {"ok": True}


# ============== Bot Management Endpoints ==============

@router.get(
    "/bots",
    response_model=List[BotResponse],
    summary="List all bots",
    description="Get list of all registered bots.",
)
async def list_bots():
    """List all registered bots."""
    bots = bot_manager.get_all_bots()
    return [
        BotResponse(
            bot_id=b.bot_id,
            bot_name=b.bot_name,
            channel_id=b.channel_id,
            is_active=b.is_active,
            webhook_url=b.webhook_url,
            allowed_users=b.allowed_users,
            take_screenshot=b.take_screenshot,
            default_wait_time=b.default_wait_time,
            default_timeout=b.default_timeout,
            send_to_channel=b.send_to_channel,
        )
        for b in bots
    ]


@router.get(
    "/bots/{bot_id}",
    response_model=BotResponse,
    summary="Get bot details",
    description="Get details of a specific bot.",
)
async def get_bot(bot_id: str):
    """Get bot by ID."""
    bot = bot_manager.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    return BotResponse(
        bot_id=bot.bot_id,
        bot_name=bot.bot_name,
        channel_id=bot.channel_id,
        is_active=bot.is_active,
        webhook_url=bot.webhook_url,
        allowed_users=bot.allowed_users,
        take_screenshot=bot.take_screenshot,
        default_wait_time=bot.default_wait_time,
        default_timeout=bot.default_timeout,
        send_to_channel=bot.send_to_channel,
    )


@router.post(
    "/bots",
    response_model=BotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new bot",
    description="Register a new Telegram bot with the system.",
)
async def register_bot(request: BotRegisterRequest):
    """
    Register a new Telegram bot.
    
    Steps to create a bot:
    1. Message @BotFather on Telegram
    2. Send /newbot and follow instructions
    3. Copy the API token
    4. Create a channel and add bot as admin
    5. Use this endpoint to register
    """
    # Check if bot already exists
    if bot_manager.get_bot(request.bot_id):
        raise HTTPException(
            status_code=400,
            detail=f"Bot with ID '{request.bot_id}' already exists"
        )
    
    # Register bot
    bot = await bot_manager.register_bot(
        bot_id=request.bot_id,
        bot_token=request.bot_token,
        bot_name=request.bot_name,
        channel_id=request.channel_id,
        allowed_users=request.allowed_users,
        take_screenshot=request.take_screenshot,
        default_wait_time=request.default_wait_time,
        default_timeout=request.default_timeout,
    )
    
    # Verify bot token by calling getMe
    client = bot_manager.get_client(request.bot_id)
    if client:
        result = await client.get_me()
        if not result.get("ok"):
            # Rollback registration
            await bot_manager.unregister_bot(request.bot_id)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid bot token: {result.get('description', 'Unknown error')}"
            )
    
    logger.info(f"Registered new bot: {request.bot_id}")
    
    return BotResponse(
        bot_id=bot.bot_id,
        bot_name=bot.bot_name,
        channel_id=bot.channel_id,
        is_active=bot.is_active,
        webhook_url=bot.webhook_url,
        allowed_users=bot.allowed_users,
        take_screenshot=bot.take_screenshot,
        default_wait_time=bot.default_wait_time,
        default_timeout=bot.default_timeout,
        send_to_channel=bot.send_to_channel,
    )


@router.patch(
    "/bots/{bot_id}",
    response_model=BotResponse,
    summary="Update bot",
    description="Update bot configuration.",
)
async def update_bot(bot_id: str, request: BotUpdateRequest):
    """Update bot configuration."""
    bot = bot_manager.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    
    updated_bot = await bot_manager.update_bot(bot_id, **update_data)
    
    return BotResponse(
        bot_id=updated_bot.bot_id,
        bot_name=updated_bot.bot_name,
        channel_id=updated_bot.channel_id,
        is_active=updated_bot.is_active,
        webhook_url=updated_bot.webhook_url,
        allowed_users=updated_bot.allowed_users,
        take_screenshot=updated_bot.take_screenshot,
        default_wait_time=updated_bot.default_wait_time,
        default_timeout=updated_bot.default_timeout,
        send_to_channel=updated_bot.send_to_channel,
    )


@router.delete(
    "/bots/{bot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete bot",
    description="Unregister and delete a bot.",
)
async def delete_bot(bot_id: str):
    """Delete a bot."""
    if not bot_manager.get_bot(bot_id):
        raise HTTPException(status_code=404, detail="Bot not found")
    
    # Remove webhook first
    client = bot_manager.get_client(bot_id)
    if client:
        await client.delete_webhook()
    
    await bot_manager.unregister_bot(bot_id)
    logger.info(f"Deleted bot: {bot_id}")


@router.post(
    "/bots/{bot_id}/test",
    summary="Test bot",
    description="Test bot by sending a message to its channel.",
)
async def test_bot(bot_id: str):
    """Test bot by sending a test message."""
    bot = bot_manager.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    client = bot_manager.get_client(bot_id)
    if not client:
        raise HTTPException(status_code=500, detail="Bot client not available")
    
    # Get bot info
    bot_info = await client.get_me()
    
    # Send test message
    result = await client.send_message(
        f"🤖 <b>Test Message</b>\n\n"
        f"Bot: {bot.bot_name}\n"
        f"Status: ✅ Working"
    )
    
    return {
        "success": result.get("ok", False),
        "bot_info": bot_info.get("result"),
        "message_sent": result.get("ok", False),
        "error": result.get("description") if not result.get("ok") else None,
    }


# ============== Webhook Setup Endpoints ==============

@router.post(
    "/webhooks/setup",
    response_model=WebhookSetupResponse,
    summary="Setup webhooks for all bots",
    description="Configure Telegram webhooks for all active bots.",
)
async def setup_webhooks(request: WebhookSetupRequest):
    """
    Setup webhooks for all active bots.
    
    The base_url should be your server's public URL.
    Each bot will get a webhook at: {base_url}/api/v1/webhook/{bot_id}
    """
    secret = request.secret or secrets.token_hex(32)
    
    results = await bot_manager.setup_webhooks(request.base_url, secret)
    
    webhook_urls = {}
    for bot_id, success in results.items():
        if success:
            webhook_urls[bot_id] = f"{request.base_url}/api/v1/webhook/{bot_id}"
    
    return WebhookSetupResponse(
        success=all(results.values()),
        results=results,
        webhook_urls=webhook_urls,
    )


@router.post(
    "/webhooks/setup/{bot_id}",
    summary="Setup webhook for single bot",
    description="Configure Telegram webhook for a specific bot.",
)
async def setup_bot_webhook(bot_id: str, request: WebhookSetupRequest):
    """Setup webhook for a single bot."""
    bot = bot_manager.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    client = bot_manager.get_client(bot_id)
    if not client:
        raise HTTPException(status_code=500, detail="Bot client not available")
    
    webhook_url = f"{request.base_url}/api/v1/webhook/{bot_id}"
    secret = request.secret or secrets.token_hex(32)
    
    result = await client.set_webhook(webhook_url, secret)
    
    if result.get("ok"):
        bot.webhook_url = webhook_url
        bot.webhook_secret = secret
    
    return {
        "success": result.get("ok", False),
        "webhook_url": webhook_url if result.get("ok") else None,
        "error": result.get("description") if not result.get("ok") else None,
    }


@router.delete(
    "/webhooks",
    summary="Remove all webhooks",
    description="Remove webhooks from all bots.",
)
async def remove_all_webhooks():
    """Remove webhooks from all bots."""
    results = await bot_manager.remove_all_webhooks()
    
    return {
        "success": all(results.values()),
        "results": results,
    }


@router.delete(
    "/webhooks/{bot_id}",
    summary="Remove webhook from bot",
    description="Remove webhook from a specific bot.",
)
async def remove_bot_webhook(bot_id: str):
    """Remove webhook from a specific bot."""
    client = bot_manager.get_client(bot_id)
    if not client:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    result = await client.delete_webhook()
    
    if result.get("ok"):
        bot = bot_manager.get_bot(bot_id)
        if bot:
            bot.webhook_url = None
    
    return {
        "success": result.get("ok", False),
        "error": result.get("description") if not result.get("ok") else None,
    }


@router.get(
    "/webhooks/{bot_id}/info",
    summary="Get webhook info",
    description="Get current webhook information for a bot.",
)
async def get_webhook_info(bot_id: str):
    """Get webhook info for a bot."""
    client = bot_manager.get_client(bot_id)
    if not client:
        raise HTTPException(status_code=404, detail="Bot not found")
    
    result = await client.get_webhook_info()
    
    return result.get("result", {})


# ============== Broadcast Endpoints ==============

@router.post(
    "/broadcast",
    summary="Broadcast message to all channels",
    description="Send a message to all bot channels.",
)
async def broadcast_message(
    message: str,
    bot_ids: Optional[List[str]] = None,
):
    """Broadcast a message to all (or selected) bot channels."""
    results = await bot_manager.broadcast_message(message, bot_ids)
    
    return {
        "success": all(results.values()),
        "results": results,
        "total_sent": sum(1 for v in results.values() if v),
        "total_failed": sum(1 for v in results.values() if not v),
    }


# ============== Stats Endpoints ==============

@router.get(
    "/stats",
    summary="Get system stats",
    description="Get statistics about bots and the system.",
)
async def get_stats():
    """Get system statistics."""
    all_bots = bot_manager.get_all_bots()
    active_bots = bot_manager.get_active_bots()
    
    bots_with_webhook = sum(1 for b in all_bots if b.webhook_url)
    
    return {
        "total_bots": len(all_bots),
        "active_bots": len(active_bots),
        "inactive_bots": len(all_bots) - len(active_bots),
        "webhooks_configured": bots_with_webhook,
        "environment": settings.ENVIRONMENT,
    }
