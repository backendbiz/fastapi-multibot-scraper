"""
Bot Management API endpoints.
Handles bot registration, configuration, and testing.
Note: Webhook endpoints are in webhooks.py
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from app.services.bot_manager import bot_manager
from app.services.scraper import selenium_scraper

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bots", tags=["Bot Management"])


# ============== Schemas ==============

class BotCreate(BaseModel):
    """Schema for creating a bot."""
    bot_id: str = Field(..., min_length=1, max_length=50, description="Unique bot identifier")
    bot_token: str = Field(..., min_length=40, description="Telegram bot token from @BotFather")
    bot_name: str = Field(..., min_length=1, max_length=100, description="Display name")
    channel_id: str = Field(..., description="Channel ID (@channel or -100xxx)")
    allowed_users: List[int] = Field(default=[], description="User IDs allowed (empty = all)")
    allowed_commands: List[str] = Field(
        default=["scrape", "batch", "status", "help"],
        description="Allowed commands"
    )
    is_active: bool = Field(default=True)
    default_wait_time: int = Field(default=5, ge=0, le=60)
    default_timeout: int = Field(default=30, ge=10, le=120)
    take_screenshot: bool = Field(default=True)
    send_to_channel: bool = Field(default=True)


class BotUpdate(BaseModel):
    """Schema for updating a bot."""
    bot_name: Optional[str] = None
    channel_id: Optional[str] = None
    allowed_users: Optional[List[int]] = None
    allowed_commands: Optional[List[str]] = None
    is_active: Optional[bool] = None
    default_wait_time: Optional[int] = Field(None, ge=0, le=60)
    default_timeout: Optional[int] = Field(None, ge=10, le=120)
    take_screenshot: Optional[bool] = None
    send_to_channel: Optional[bool] = None


class BotResponse(BaseModel):
    """Bot response schema."""
    bot_id: str
    bot_name: str
    channel_id: str
    allowed_users: List[int]
    allowed_commands: List[str]
    is_active: bool
    webhook_url: Optional[str] = None
    default_wait_time: int
    default_timeout: int
    take_screenshot: bool
    send_to_channel: bool


class BulkBotsCreate(BaseModel):
    """Bulk bot creation."""
    bots: List[BotCreate] = Field(..., min_length=1, max_length=50)


class ScrapeNotifyRequest(BaseModel):
    """API scrape request with notification."""
    url: str = Field(..., description="URL to scrape")
    bot_id: Optional[str] = Field(None, description="Specific bot to notify (or all if None)")
    bot_ids: Optional[List[str]] = Field(None, description="List of bot IDs to notify")
    wait_for: Optional[str] = Field(None, description="CSS selector to wait for")
    wait_time: Optional[int] = Field(None, ge=0, le=60)
    take_screenshot: bool = Field(default=True)
    extract_rules: Optional[Dict[str, Dict]] = Field(None)
    notify_channel: bool = Field(default=True, description="Send results to Telegram")


# ============== Bot CRUD ==============

@router.post("/register", response_model=BotResponse, status_code=201)
async def register_bot(config: BotCreate):
    """
    Register a new Telegram bot.
    
    Steps to create a bot:
    1. Message @BotFather on Telegram
    2. Send /newbot and follow instructions
    3. Copy the API token
    4. Create a channel and add bot as admin
    5. Use this endpoint to register
    """
    if bot_manager.get_bot(config.bot_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bot '{config.bot_id}' already exists"
        )
    
    # Register bot
    bot = await bot_manager.register_bot(
        bot_id=config.bot_id,
        bot_token=config.bot_token,
        bot_name=config.bot_name,
        channel_id=config.channel_id,
        allowed_users=config.allowed_users,
        is_active=config.is_active,
        default_wait_time=config.default_wait_time,
        default_timeout=config.default_timeout,
        take_screenshot=config.take_screenshot,
        send_to_channel=config.send_to_channel,
    )
    
    # Verify bot token
    client = bot_manager.get_client(config.bot_id)
    if client:
        result = await client.get_me()
        if not result.get("ok"):
            await bot_manager.unregister_bot(config.bot_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid bot token: {result.get('description', 'Unknown error')}"
            )
    
    logger.info(f"Registered new bot: {config.bot_id}")
    
    return BotResponse(
        bot_id=bot.bot_id,
        bot_name=bot.bot_name,
        channel_id=bot.channel_id,
        allowed_users=bot.allowed_users,
        allowed_commands=bot.allowed_commands,
        is_active=bot.is_active,
        webhook_url=bot.webhook_url,
        default_wait_time=bot.default_wait_time,
        default_timeout=bot.default_timeout,
        take_screenshot=bot.take_screenshot,
        send_to_channel=bot.send_to_channel,
    )


@router.post("/register/bulk")
async def register_bots_bulk(request: BulkBotsCreate):
    """Register multiple bots at once."""
    results = {"success": [], "failed": []}
    
    for bot in request.bots:
        try:
            await bot_manager.register_bot(
                bot_id=bot.bot_id,
                bot_token=bot.bot_token,
                bot_name=bot.bot_name,
                channel_id=bot.channel_id,
                allowed_users=bot.allowed_users,
                is_active=bot.is_active,
                default_wait_time=bot.default_wait_time,
                default_timeout=bot.default_timeout,
                take_screenshot=bot.take_screenshot,
                send_to_channel=bot.send_to_channel,
            )
            results["success"].append(bot.bot_id)
        except Exception as e:
            results["failed"].append({"bot_id": bot.bot_id, "error": str(e)})
    
    return {
        "total": len(request.bots),
        "registered": len(results["success"]),
        "failed": len(results["failed"]),
        "results": results,
    }


@router.get("", response_model=List[BotResponse])
async def list_bots():
    """List all registered bots."""
    bots = bot_manager.get_all_bots()
    return [
        BotResponse(
            bot_id=b.bot_id,
            bot_name=b.bot_name,
            channel_id=b.channel_id,
            allowed_users=b.allowed_users,
            allowed_commands=b.allowed_commands,
            is_active=b.is_active,
            webhook_url=b.webhook_url,
            default_wait_time=b.default_wait_time,
            default_timeout=b.default_timeout,
            take_screenshot=b.take_screenshot,
            send_to_channel=b.send_to_channel,
        )
        for b in bots
    ]


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(bot_id: str):
    """Get bot details."""
    bot = bot_manager.get_bot(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot '{bot_id}' not found"
        )
    
    return BotResponse(
        bot_id=bot.bot_id,
        bot_name=bot.bot_name,
        channel_id=bot.channel_id,
        allowed_users=bot.allowed_users,
        allowed_commands=bot.allowed_commands,
        is_active=bot.is_active,
        webhook_url=bot.webhook_url,
        default_wait_time=bot.default_wait_time,
        default_timeout=bot.default_timeout,
        take_screenshot=bot.take_screenshot,
        send_to_channel=bot.send_to_channel,
    )


@router.patch("/{bot_id}", response_model=BotResponse)
async def update_bot(bot_id: str, update: BotUpdate):
    """Update bot configuration."""
    bot = bot_manager.get_bot(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot '{bot_id}' not found"
        )
    
    update_data = update.model_dump(exclude_unset=True)
    updated_bot = await bot_manager.update_bot(bot_id, **update_data)
    
    return BotResponse(
        bot_id=updated_bot.bot_id,
        bot_name=updated_bot.bot_name,
        channel_id=updated_bot.channel_id,
        allowed_users=updated_bot.allowed_users,
        allowed_commands=updated_bot.allowed_commands,
        is_active=updated_bot.is_active,
        webhook_url=updated_bot.webhook_url,
        default_wait_time=updated_bot.default_wait_time,
        default_timeout=updated_bot.default_timeout,
        take_screenshot=updated_bot.take_screenshot,
        send_to_channel=updated_bot.send_to_channel,
    )


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_bot(bot_id: str):
    """Unregister and delete a bot."""
    if not bot_manager.get_bot(bot_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot '{bot_id}' not found"
        )
    
    # Remove webhook first
    client = bot_manager.get_client(bot_id)
    if client:
        await client.delete_webhook()
    
    await bot_manager.unregister_bot(bot_id)
    logger.info(f"Deleted bot: {bot_id}")


@router.post("/{bot_id}/test")
async def test_bot(bot_id: str):
    """Test bot by sending a test message to its channel."""
    bot = bot_manager.get_bot(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot '{bot_id}' not found"
        )
    
    client = bot_manager.get_client(bot_id)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bot client not available"
        )
    
    # Get bot info
    bot_info = await client.get_me()
    
    # Send test message
    result = await client.send_message(
        f"🤖 <b>Test Message</b>\n\n"
        f"Bot: {bot.bot_name}\n"
        f"Status: ✅ Working\n"
        f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    
    return {
        "success": result.get("ok", False),
        "bot_info": bot_info.get("result"),
        "message_sent": result.get("ok", False),
        "error": result.get("description") if not result.get("ok") else None,
    }


# ============== API Scraping with Notification ==============

@router.post("/scrape")
async def scrape_and_notify(request: ScrapeNotifyRequest, background_tasks: BackgroundTasks):
    """
    Scrape URL via API and send results to Telegram channel(s).
    
    Flow:
    1. API request comes in
    2. Selenium scrapes the URL
    3. Results returned in API response
    4. Results also sent to Telegram channel(s)
    
    If bot_id/bot_ids specified, sends only to those bots' channels.
    If none specified, sends to ALL active bot channels.
    """
    # Perform scraping
    result = await selenium_scraper.scrape(
        url=request.url,
        wait_for=request.wait_for,
        wait_time=request.wait_time,
        take_screenshot=request.take_screenshot,
        extract_rules=request.extract_rules,
    )
    
    notification_results = {}
    
    # Notify Telegram channels
    if request.notify_channel and bot_manager.bot_count > 0:
        # Determine target bots
        if request.bot_ids:
            target_bots = request.bot_ids
        elif request.bot_id:
            target_bots = [request.bot_id]
        else:
            target_bots = bot_manager.active_bots
        
        for bid in target_bots:
            client = bot_manager.get_client(bid)
            if client:
                try:
                    await client.send_scrape_result(
                        url=result["url"],
                        title=result.get("title"),
                        data=result.get("data", {}),
                        screenshot=result.get("screenshot") if request.take_screenshot else None,
                        error=result.get("error"),
                        source="api",
                    )
                    notification_results[bid] = {"status": "success"}
                    logger.info(f"Notified bot {bid}")
                except Exception as e:
                    notification_results[bid] = {"status": "error", "error": str(e)}
                    logger.error(f"Failed to notify bot {bid}: {e}")
    
    return {
        "success": result.get("success", False),
        "url": result.get("url"),
        "title": result.get("title"),
        "data": result.get("data", {}),
        "screenshot_taken": bool(result.get("screenshot")),
        "html_length": len(result.get("html", "")),
        "notification_sent": len([r for r in notification_results.values() if r.get("status") == "success"]) > 0,
        "notified_bots": list(notification_results.keys()),
        "notification_results": notification_results,
        "error": result.get("error"),
    }


@router.post("/broadcast")
async def broadcast_message(message: str, bot_ids: Optional[List[str]] = None):
    """Broadcast a message to all (or selected) bot channels."""
    results = await bot_manager.broadcast_message(message, bot_ids)
    
    return {
        "success": all(results.values()),
        "results": results,
        "total_sent": sum(1 for v in results.values() if v),
        "total_failed": sum(1 for v in results.values() if not v),
    }


@router.get("/status/summary")
async def get_status():
    """Get bots system status."""
    all_bots = bot_manager.get_all_bots()
    active_bots = bot_manager.get_active_bots()
    
    return {
        "total_bots": len(all_bots),
        "active_bots": len(active_bots),
        "inactive_bots": len(all_bots) - len(active_bots),
        "bot_ids": [b.bot_id for b in all_bots],
        "active_bot_ids": [b.bot_id for b in active_bots],
    }
