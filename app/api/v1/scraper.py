"""
Web Scraping API endpoints.
Provides endpoints for Selenium-based web scraping with multi-bot Telegram notifications.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl

from app.core.config import settings
from app.services.scraper import selenium_scraper
from app.services.bot_manager import bot_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraper", tags=["Web Scraper"])


# ============== Request/Response Schemas ==============

class ExtractionRule(BaseModel):
    """Rule for extracting data from page elements."""
    selector: str = Field(..., description="CSS selector for the element")
    attribute: str = Field(default="text", description="Attribute to extract: text, href, src, html")
    multiple: bool = Field(default=False, description="Extract from multiple matching elements")


class ScrapeRequest(BaseModel):
    """Request schema for scraping a URL."""
    url: HttpUrl = Field(..., description="URL to scrape")
    wait_for: Optional[str] = Field(None, description="CSS selector to wait for before scraping")
    wait_type: str = Field(default="presence", description="Wait condition: presence, visibility, clickable")
    wait_time: Optional[int] = Field(None, ge=0, le=60, description="Additional wait time in seconds")
    scroll_to_bottom: bool = Field(default=False, description="Scroll to bottom to load lazy content")
    take_screenshot: bool = Field(default=True, description="Capture screenshot of the page")
    extract_rules: Optional[Dict[str, ExtractionRule]] = Field(
        None, description="Rules for extracting specific data"
    )
    custom_js: Optional[str] = Field(None, description="Custom JavaScript to execute")
    
    # Multi-bot Telegram settings
    send_to_telegram: bool = Field(default=True, description="Send results to Telegram bots")
    bot_id: Optional[str] = Field(None, description="Single bot ID to notify")
    bot_ids: Optional[List[str]] = Field(None, description="List of bot IDs to notify (overrides bot_id)")


class BatchScrapeRequest(BaseModel):
    """Request schema for batch scraping multiple URLs."""
    urls: List[HttpUrl] = Field(..., min_length=1, max_length=50, description="URLs to scrape")
    wait_for: Optional[str] = Field(None, description="CSS selector to wait for")
    wait_type: str = Field(default="presence")
    take_screenshot: bool = Field(default=False, description="Screenshots disabled by default for batch")
    extract_rules: Optional[Dict[str, ExtractionRule]] = None
    
    # Telegram settings
    send_to_telegram: bool = Field(default=True, description="Send summary to Telegram")
    send_individual_results: bool = Field(default=False, description="Send each result individually")
    bot_id: Optional[str] = Field(None, description="Single bot ID")
    bot_ids: Optional[List[str]] = Field(None, description="List of bot IDs")


class ScrapeResponse(BaseModel):
    """Response schema for scraping results."""
    success: bool
    url: str
    timestamp: str
    title: Optional[str] = None
    data: Dict[str, Any] = {}
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    telegram_sent: bool = False
    notified_bots: List[str] = []


class BatchScrapeResponse(BaseModel):
    """Response schema for batch scraping."""
    total: int
    successful: int
    failed: int
    results: List[ScrapeResponse]
    telegram_sent: bool = False
    notified_bots: List[str] = []


# ============== Helper Functions ==============

async def notify_bots(
    url: str,
    title: Optional[str],
    data: Dict[str, Any],
    screenshot: Optional[bytes],
    error: Optional[str],
    bot_id: Optional[str] = None,
    bot_ids: Optional[List[str]] = None,
    source: str = "api",
) -> List[str]:
    """Send notification to specified bots or all active bots."""
    notified = []
    
    # Determine which bots to notify
    if bot_ids:
        target_bots = bot_ids
    elif bot_id:
        target_bots = [bot_id]
    else:
        # Notify all active bots
        target_bots = [b.bot_id for b in bot_manager.get_active_bots()]
    
    for bid in target_bots:
        client = bot_manager.get_client(bid)
        if client:
            try:
                await client.send_scrape_result(
                    url=url,
                    title=title,
                    data=data,
                    screenshot=screenshot,
                    error=error,
                    source=source,
                )
                notified.append(bid)
                logger.info(f"Notified bot {bid} for {url}")
            except Exception as e:
                logger.error(f"Failed to notify bot {bid}: {e}")
    
    return notified


# ============== API Endpoints ==============

@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    summary="Scrape a URL",
    description="Scrape a URL using Selenium and send results to Telegram bots.",
)
async def scrape_url(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Scrape a single URL with Selenium.
    
    The results will be:
    1. Returned in the API response
    2. Sent to specified Telegram bots (or all active bots if none specified)
    
    Features:
    - Wait for specific elements before scraping
    - Extract data using CSS selectors
    - Take screenshots
    - Execute custom JavaScript
    - Notify multiple Telegram bots
    """
    # Convert extraction rules
    extract_rules = None
    if request.extract_rules:
        extract_rules = {
            name: rule.model_dump()
            for name, rule in request.extract_rules.items()
        }

    # Perform scraping
    result = await selenium_scraper.scrape(
        url=str(request.url),
        wait_for=request.wait_for,
        wait_type=request.wait_type,
        wait_time=request.wait_time,
        scroll_to_bottom=request.scroll_to_bottom,
        take_screenshot=request.take_screenshot,
        extract_rules=extract_rules,
        custom_js=request.custom_js,
    )

    # Prepare response
    response = ScrapeResponse(
        success=result["success"],
        url=result["url"],
        timestamp=result["timestamp"],
        title=result.get("title"),
        data=result.get("data", {}),
        screenshot_path=result.get("screenshot_path"),
        error=result.get("error"),
        telegram_sent=False,
        notified_bots=[],
    )

    # Notify Telegram bots
    if request.send_to_telegram and bot_manager.get_bot_count() > 0:
        notified = await notify_bots(
            url=result["url"],
            title=result.get("title"),
            data=result.get("data", {}),
            screenshot=result.get("screenshot") if request.take_screenshot else None,
            error=result.get("error"),
            bot_id=request.bot_id,
            bot_ids=request.bot_ids,
            source="api",
        )
        response.telegram_sent = len(notified) > 0
        response.notified_bots = notified

    return response


@router.post(
    "/scrape/batch",
    response_model=BatchScrapeResponse,
    summary="Batch scrape URLs",
    description="Scrape multiple URLs concurrently and send summary to Telegram.",
)
async def scrape_batch(request: BatchScrapeRequest, background_tasks: BackgroundTasks):
    """
    Scrape multiple URLs concurrently.
    
    Limits:
    - Maximum 50 URLs per request
    - Screenshots disabled by default
    """
    # Convert extraction rules
    extract_rules = None
    if request.extract_rules:
        extract_rules = {
            name: rule.model_dump()
            for name, rule in request.extract_rules.items()
        }

    # Scrape all URLs
    results = await selenium_scraper.scrape_multiple(
        urls=[str(url) for url in request.urls],
        wait_for=request.wait_for,
        wait_type=request.wait_type,
        take_screenshot=request.take_screenshot,
        extract_rules=extract_rules,
    )

    # Process results
    successful = sum(1 for r in results if r.get("success", False))
    failed = len(results) - successful

    response_results = [
        ScrapeResponse(
            success=r["success"],
            url=r["url"],
            timestamp=r["timestamp"],
            title=r.get("title"),
            data=r.get("data", {}),
            screenshot_path=r.get("screenshot_path"),
            error=r.get("error"),
        )
        for r in results
    ]

    response = BatchScrapeResponse(
        total=len(results),
        successful=successful,
        failed=failed,
        results=response_results,
        telegram_sent=False,
        notified_bots=[],
    )

    # Notify Telegram bots
    if request.send_to_telegram and bot_manager.get_bot_count() > 0:
        # Determine target bots
        if request.bot_ids:
            target_bots = request.bot_ids
        elif request.bot_id:
            target_bots = [request.bot_id]
        else:
            target_bots = [b.bot_id for b in bot_manager.get_active_bots()]
        
        notified = []
        
        for bid in target_bots:
            client = bot_manager.get_client(bid)
            if not client:
                continue
            
            try:
                # Send individual results if requested
                if request.send_individual_results:
                    for r in results:
                        await client.send_scrape_result(
                            url=r["url"],
                            title=r.get("title"),
                            data=r.get("data", {}),
                            screenshot=r.get("screenshot"),
                            error=r.get("error"),
                            source="api (batch)",
                        )
                
                # Send summary
                summary = (
                    f"📊 <b>Batch Scraping Complete</b>\n\n"
                    f"✅ Successful: {successful}\n"
                    f"❌ Failed: {failed}\n"
                    f"📈 Total: {len(results)}\n"
                    f"📡 Source: API"
                )
                await client.send_message(summary)
                notified.append(bid)
            except Exception as e:
                logger.error(f"Failed to notify bot {bid}: {e}")
        
        response.telegram_sent = len(notified) > 0
        response.notified_bots = notified

    return response


@router.post(
    "/scrape/simple",
    summary="Simple scrape",
    description="Quick scrape with minimal options.",
)
async def scrape_simple(
    url: HttpUrl,
    send_to_telegram: bool = True,
    bot_id: Optional[str] = None,
):
    """
    Simple scrape - just get page title and screenshot.
    Useful for quick checks.
    """
    result = await selenium_scraper.scrape(
        url=str(url),
        take_screenshot=True,
    )

    notified = []
    if send_to_telegram and bot_manager.get_bot_count() > 0:
        notified = await notify_bots(
            url=result["url"],
            title=result.get("title"),
            data={},
            screenshot=result.get("screenshot"),
            error=result.get("error"),
            bot_id=bot_id,
            source="api (simple)",
        )

    return {
        "success": result["success"],
        "url": result["url"],
        "title": result.get("title"),
        "error": result.get("error"),
        "html_length": len(result.get("html", "")),
        "telegram_sent": len(notified) > 0,
        "notified_bots": notified,
    }


@router.get(
    "/status",
    summary="Scraper status",
    description="Check the status of the scraper and Telegram bots.",
)
async def get_scraper_status():
    """Get current status of scraper services."""
    all_bots = bot_manager.get_all_bots()
    active_bots = bot_manager.get_active_bots()
    
    return {
        "scraper": {
            "available": True,
            "headless": settings.SELENIUM_HEADLESS,
            "timeout": settings.SELENIUM_TIMEOUT,
        },
        "telegram": {
            "total_bots": len(all_bots),
            "active_bots": len(active_bots),
            "bot_names": [b.bot_name for b in active_bots],
        },
        "settings": {
            "environment": settings.ENVIRONMENT,
            "screenshots_dir": str(settings.SCREENSHOTS_DIR),
        },
    }
