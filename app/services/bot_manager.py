"""
Multi-Bot Manager Service.
Manages multiple Telegram bots with their own configurations.
Supports 30+ bots with individual settings.
"""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class BotConfig:
    """Configuration for a single Telegram bot."""
    bot_id: str
    bot_token: str
    bot_name: str
    channel_id: str  # Channel to send results
    allowed_users: List[int] = field(default_factory=list)  # User IDs allowed (empty = all)
    allowed_commands: List[str] = field(default_factory=lambda: ["scrape", "batch", "status", "help"])
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    
    # Scraping defaults for this bot
    default_wait_time: int = 5
    default_timeout: int = 30
    take_screenshot: bool = True
    send_to_channel: bool = True
    
    # Rate limiting
    max_requests_per_minute: int = 10
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (safe for API responses)."""
        return {
            "bot_id": self.bot_id,
            "bot_token_preview": self.bot_token[:10] + "..." if self.bot_token else None,
            "bot_name": self.bot_name,
            "channel_id": self.channel_id,
            "allowed_users": self.allowed_users,
            "allowed_commands": self.allowed_commands,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "webhook_url": self.webhook_url,
            "default_wait_time": self.default_wait_time,
            "default_timeout": self.default_timeout,
            "take_screenshot": self.take_screenshot,
            "send_to_channel": self.send_to_channel,
            "max_requests_per_minute": self.max_requests_per_minute,
        }


class TelegramBotClient:
    """HTTP client for a single Telegram bot."""
    
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"
    
    def __init__(self, config: BotConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._request_times: List[datetime] = []
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _get_url(self, method: str) -> str:
        """Build Telegram API URL."""
        return self.BASE_URL.format(token=self.config.bot_token, method=method)
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        now = datetime.utcnow()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if (now - t).seconds < 60]
        return len(self._request_times) < self.config.max_requests_per_minute
    
    async def _make_request(
        self,
        method: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to Telegram API."""
        if not self._check_rate_limit():
            logger.warning(f"Rate limit exceeded for bot {self.config.bot_id}")
            return {"ok": False, "error": "Rate limit exceeded"}
        
        self._request_times.append(datetime.utcnow())
        client = await self._get_client()
        url = self._get_url(method)
        
        try:
            if files:
                response = await client.post(url, data=data, files=files)
            else:
                response = await client.post(url, json=data)
            
            result = response.json()
            
            if not result.get("ok"):
                logger.error(f"Telegram API error for bot {self.config.bot_id}: {result}")
            
            return result
        
        except Exception as e:
            logger.exception(f"Failed to send Telegram request for bot {self.config.bot_id}: {e}")
            return {"ok": False, "error": str(e)}
    
    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "HTML",
        reply_to_message_id: Optional[int] = None,
        disable_notification: bool = False,
    ) -> Dict[str, Any]:
        """Send a text message."""
        data = {
            "chat_id": chat_id or self.config.channel_id,
            "text": text[:4096],
            "parse_mode": parse_mode,
            "disable_notification": disable_notification,
        }
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        
        return await self._make_request("sendMessage", data)
    
    async def send_photo(
        self,
        photo: bytes,
        caption: Optional[str] = None,
        chat_id: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a photo."""
        data = {
            "chat_id": chat_id or self.config.channel_id,
            "parse_mode": "HTML",
        }
        if caption:
            data["caption"] = caption[:1024]
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id
        
        files = {"photo": ("screenshot.png", photo, "image/png")}
        return await self._make_request("sendPhoto", data, files=files)
    
    async def send_document(
        self,
        document: bytes,
        filename: str,
        caption: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a document."""
        data = {
            "chat_id": chat_id or self.config.channel_id,
            "parse_mode": "HTML",
        }
        if caption:
            data["caption"] = caption[:1024]
        
        files = {"document": (filename, document)}
        return await self._make_request("sendDocument", data, files=files)
    
    async def get_me(self) -> Dict[str, Any]:
        """Get bot information."""
        return await self._make_request("getMe")
    
    async def set_webhook(self, url: str, secret_token: Optional[str] = None) -> Dict[str, Any]:
        """Set webhook URL for this bot."""
        data = {
            "url": url,
            "allowed_updates": ["message", "callback_query"],
        }
        if secret_token:
            data["secret_token"] = secret_token
        
        return await self._make_request("setWebhook", data)
    
    async def delete_webhook(self) -> Dict[str, Any]:
        """Delete webhook."""
        return await self._make_request("deleteWebhook")
    
    async def get_webhook_info(self) -> Dict[str, Any]:
        """Get current webhook info."""
        return await self._make_request("getWebhookInfo")
    
    async def send_typing_action(self, chat_id: str) -> Dict[str, Any]:
        """Send typing action indicator."""
        return await self._make_request("sendChatAction", {
            "chat_id": chat_id,
            "action": "typing"
        })
    
    async def send_scrape_result(
        self,
        url: str,
        title: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        screenshot: Optional[bytes] = None,
        error: Optional[str] = None,
        chat_id: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        source: str = "api",  # "api" or "telegram"
    ) -> Dict[str, Any]:
        """Send formatted scraping result."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        target_chat = chat_id or self.config.channel_id
        
        if error:
            message = (
                f"❌ <b>Scraping Failed</b>\n\n"
                f"🤖 <b>Bot:</b> {self.config.bot_name}\n"
                f"🔗 <b>URL:</b> {url}\n"
                f"⚠️ <b>Error:</b> {error}\n"
                f"📡 <b>Source:</b> {source}\n"
                f"🕐 <b>Time:</b> {timestamp}"
            )
            return await self.send_message(message, chat_id=target_chat, reply_to_message_id=reply_to_message_id)
        
        # Success message
        message_parts = [
            f"✅ <b>Scraping Complete</b>\n",
            f"🤖 <b>Bot:</b> {self.config.bot_name}",
            f"🔗 <b>URL:</b> {url}",
        ]
        
        if title:
            message_parts.append(f"📄 <b>Title:</b> {title}")
        
        if data:
            message_parts.append("\n📊 <b>Extracted Data:</b>")
            for key, value in list(data.items())[:10]:  # Limit to 10 items
                str_value = str(value)
                if len(str_value) > 100:
                    str_value = str_value[:100] + "..."
                message_parts.append(f"  • <b>{key}:</b> {str_value}")
        
        message_parts.append(f"\n📡 <b>Source:</b> {source}")
        message_parts.append(f"🕐 <b>Time:</b> {timestamp}")
        
        message = "\n".join(message_parts)
        
        # Send screenshot first if available
        if screenshot and self.config.take_screenshot:
            await self.send_photo(
                screenshot,
                caption=f"📸 Screenshot of {url}",
                chat_id=target_chat,
                reply_to_message_id=reply_to_message_id,
            )
        
        return await self.send_message(message, chat_id=target_chat, reply_to_message_id=reply_to_message_id)


class BotManager:
    """
    Manages multiple Telegram bots.
    Supports 30+ bots with individual configurations.
    """
    
    def __init__(self):
        self._bots: Dict[str, BotConfig] = {}
        self._clients: Dict[str, TelegramBotClient] = {}
        self._config_file = Path("/app/data/bots.json")
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize bot manager and load saved configurations."""
        # Load from environment variable if set
        await self._load_from_env()
        
        # Load from config file
        await self._load_from_file()
        
        logger.info(f"Bot manager initialized with {len(self._bots)} bots")
    
    async def _load_from_env(self):
        """Load bots from environment variables."""
        # JSON format: TELEGRAM_BOTS_CONFIG='[{"bot_id": "bot1", "bot_token": "...", ...}]'
        bots_json = getattr(settings, 'TELEGRAM_BOTS_CONFIG', None)
        if bots_json:
            try:
                bots_data = json.loads(bots_json)
                for bot_data in bots_data:
                    await self.register_bot(
                        bot_id=bot_data["bot_id"],
                        bot_token=bot_data["bot_token"],
                        bot_name=bot_data.get("bot_name", bot_data["bot_id"]),
                        channel_id=bot_data["channel_id"],
                        allowed_users=bot_data.get("allowed_users", []),
                        save_to_file=False,
                    )
            except Exception as e:
                logger.error(f"Failed to load bots from env: {e}")
        
        # Also support legacy single bot config
        if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHANNEL_ID:
            await self.register_bot(
                bot_id="default",
                bot_token=settings.TELEGRAM_BOT_TOKEN,
                bot_name="Default Bot",
                channel_id=settings.TELEGRAM_CHANNEL_ID,
                save_to_file=False,
            )
    
    async def _load_from_file(self):
        """Load bot configurations from file."""
        if not self._config_file.exists():
            return
        
        try:
            with open(self._config_file, "r") as f:
                bots_data = json.load(f)
            
            for bot_data in bots_data:
                if bot_data["bot_id"] not in self._bots:
                    await self.register_bot(
                        bot_id=bot_data["bot_id"],
                        bot_token=bot_data["bot_token"],
                        bot_name=bot_data.get("bot_name"),
                        channel_id=bot_data["channel_id"],
                        allowed_users=bot_data.get("allowed_users", []),
                        is_active=bot_data.get("is_active", True),
                        default_wait_time=bot_data.get("default_wait_time", 5),
                        default_timeout=bot_data.get("default_timeout", 30),
                        take_screenshot=bot_data.get("take_screenshot", True),
                        save_to_file=False,
                    )
        except Exception as e:
            logger.error(f"Failed to load bots from file: {e}")
    
    async def _save_to_file(self):
        """Save bot configurations to file."""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            
            bots_data = []
            for bot in self._bots.values():
                bots_data.append({
                    "bot_id": bot.bot_id,
                    "bot_token": bot.bot_token,
                    "bot_name": bot.bot_name,
                    "channel_id": bot.channel_id,
                    "allowed_users": bot.allowed_users,
                    "allowed_commands": bot.allowed_commands,
                    "is_active": bot.is_active,
                    "default_wait_time": bot.default_wait_time,
                    "default_timeout": bot.default_timeout,
                    "take_screenshot": bot.take_screenshot,
                    "send_to_channel": bot.send_to_channel,
                    "webhook_url": bot.webhook_url,
                })
            
            with open(self._config_file, "w") as f:
                json.dump(bots_data, f, indent=2)
            
            logger.info(f"Saved {len(bots_data)} bot configurations")
        except Exception as e:
            logger.error(f"Failed to save bots to file: {e}")
    
    async def register_bot(
        self,
        bot_id: str,
        bot_token: str,
        bot_name: str,
        channel_id: str,
        allowed_users: List[int] = None,
        is_active: bool = True,
        save_to_file: bool = True,
        **kwargs,
    ) -> BotConfig:
        """Register a new bot."""
        async with self._lock:
            config = BotConfig(
                bot_id=bot_id,
                bot_token=bot_token,
                bot_name=bot_name,
                channel_id=channel_id,
                allowed_users=allowed_users or [],
                is_active=is_active,
                **kwargs,
            )
            
            self._bots[bot_id] = config
            self._clients[bot_id] = TelegramBotClient(config)
            
            if save_to_file:
                await self._save_to_file()
            
            logger.info(f"Registered bot: {bot_id} ({bot_name})")
            return config
    
    async def unregister_bot(self, bot_id: str) -> bool:
        """Unregister a bot."""
        async with self._lock:
            if bot_id in self._bots:
                # Close client
                if bot_id in self._clients:
                    await self._clients[bot_id].close()
                    del self._clients[bot_id]
                
                del self._bots[bot_id]
                await self._save_to_file()
                
                logger.info(f"Unregistered bot: {bot_id}")
                return True
            return False
    
    async def update_bot(self, bot_id: str, **kwargs) -> Optional[BotConfig]:
        """Update bot configuration."""
        async with self._lock:
            if bot_id not in self._bots:
                return None
            
            config = self._bots[bot_id]
            
            for key, value in kwargs.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            # Recreate client with new config
            if bot_id in self._clients:
                await self._clients[bot_id].close()
            self._clients[bot_id] = TelegramBotClient(config)
            
            await self._save_to_file()
            return config
    
    def get_bot(self, bot_id: str) -> Optional[BotConfig]:
        """Get bot configuration."""
        return self._bots.get(bot_id)
    
    def get_client(self, bot_id: str) -> Optional[TelegramBotClient]:
        """Get bot client."""
        return self._clients.get(bot_id)
    
    def get_all_bots(self) -> List[BotConfig]:
        """Get all registered bots."""
        return list(self._bots.values())
    
    def get_active_bots(self) -> List[BotConfig]:
        """Get all active bots."""
        return [b for b in self._bots.values() if b.is_active]
    
    def get_bot_count(self) -> int:
        """Get total number of bots."""
        return len(self._bots)
    
    @property
    def bot_count(self) -> int:
        """Property for total number of bots."""
        return len(self._bots)
    
    @property
    def active_bots(self) -> List[str]:
        """Property for active bot IDs."""
        return [b.bot_id for b in self._bots.values() if b.is_active]
    
    def get_bot_by_token(self, token: str) -> Optional[BotConfig]:
        """Find bot by token."""
        for bot in self._bots.values():
            if bot.bot_token == token:
                return bot
        return None
    
    def is_user_allowed(self, bot_id: str, user_id: int) -> bool:
        """Check if user is allowed to use bot."""
        bot = self._bots.get(bot_id)
        if not bot:
            return False
        
        # Empty allowed_users means all users are allowed
        if not bot.allowed_users:
            return True
        
        return user_id in bot.allowed_users
    
    async def broadcast_message(
        self,
        message: str,
        bot_ids: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """Send message from multiple bots to their channels."""
        results = {}
        
        target_bots = bot_ids or list(self._bots.keys())
        
        for bot_id in target_bots:
            client = self._clients.get(bot_id)
            if client and self._bots[bot_id].is_active:
                result = await client.send_message(message)
                results[bot_id] = result.get("ok", False)
            else:
                results[bot_id] = False
        
        return results
    
    async def setup_webhooks(self, base_url: str, secret: Optional[str] = None) -> Dict[str, bool]:
        """Setup webhooks for all active bots."""
        results = {}
        
        for bot_id, client in self._clients.items():
            if self._bots[bot_id].is_active:
                webhook_url = f"{base_url}/api/v1/webhook/{bot_id}"
                result = await client.set_webhook(webhook_url, secret)
                results[bot_id] = result.get("ok", False)
                
                if result.get("ok"):
                    self._bots[bot_id].webhook_url = webhook_url
                    self._bots[bot_id].webhook_secret = secret
        
        await self._save_to_file()
        return results
    
    async def remove_all_webhooks(self) -> Dict[str, bool]:
        """Remove webhooks from all bots."""
        results = {}
        
        for bot_id, client in self._clients.items():
            result = await client.delete_webhook()
            results[bot_id] = result.get("ok", False)
            
            if result.get("ok"):
                self._bots[bot_id].webhook_url = None
        
        await self._save_to_file()
        return results
    
    async def close(self):
        """Close all bot clients."""
        for client in self._clients.values():
            await client.close()
        logger.info("Bot manager closed")
    
    async def close_all(self):
        """Alias for close()."""
        await self.close()
    
    def load_from_env(self) -> int:
        """
        Synchronously load bots from environment variables.
        Returns the number of bots loaded.
        """
        import json
        count = 0
        
        # JSON format: BOTS_CONFIG='[{"bot_id": "bot1", "bot_token": "...", ...}]'
        bots_json = getattr(settings, 'BOTS_CONFIG', None)
        if bots_json:
            try:
                bots_data = json.loads(bots_json)
                for bot_data in bots_data:
                    config = BotConfig(
                        bot_id=bot_data["bot_id"],
                        bot_token=bot_data["bot_token"],
                        bot_name=bot_data.get("bot_name", bot_data["bot_id"]),
                        channel_id=bot_data["channel_id"],
                        allowed_users=bot_data.get("allowed_users", []),
                        take_screenshot=bot_data.get("take_screenshot", True),
                        send_to_channel=bot_data.get("send_to_channel", True),
                        default_wait_time=bot_data.get("default_wait_time", 5),
                        default_timeout=bot_data.get("default_timeout", 30),
                    )
                    self._bots[config.bot_id] = config
                    self._clients[config.bot_id] = TelegramBotClient(config)
                    count += 1
                    logger.info(f"Loaded bot from env: {config.bot_id}")
            except Exception as e:
                logger.error(f"Failed to load bots from BOTS_CONFIG: {e}")
        
        # Also support legacy single bot config
        telegram_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        telegram_channel = getattr(settings, 'TELEGRAM_CHANNEL_ID', None)
        
        if telegram_token and telegram_channel and "default" not in self._bots:
            config = BotConfig(
                bot_id="default",
                bot_token=telegram_token,
                bot_name="Default Bot",
                channel_id=telegram_channel,
            )
            self._bots["default"] = config
            self._clients["default"] = TelegramBotClient(config)
            count += 1
            logger.info("Loaded default bot from TELEGRAM_BOT_TOKEN")
        
        return count


# Global bot manager instance
bot_manager = BotManager()
