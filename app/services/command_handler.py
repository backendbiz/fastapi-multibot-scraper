"""
Telegram Command Handler Service.
Processes incoming commands from Telegram bots and executes scraping tasks.
"""
import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.services.bot_manager import BotManager, BotConfig, TelegramBotClient, bot_manager
from app.services.scraper import selenium_scraper

logger = logging.getLogger(__name__)


@dataclass
class TelegramUpdate:
    """Parsed Telegram update."""
    update_id: int
    message_id: Optional[int] = None
    chat_id: Optional[int] = None
    chat_type: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    text: Optional[str] = None
    command: Optional[str] = None
    command_args: Optional[str] = None
    is_bot: bool = False
    date: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelegramUpdate":
        """Parse Telegram update from dictionary."""
        update_id = data.get("update_id", 0)
        
        message = data.get("message", {})
        chat = message.get("chat", {})
        user = message.get("from", {})
        text = message.get("text", "")
        
        # Parse command
        command = None
        command_args = None
        if text and text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0].split("@")[0]
            command = cmd[1:]
            command_args = parts[1] if len(parts) > 1 else None
        
        return cls(
            update_id=update_id,
            message_id=message.get("message_id"),
            chat_id=chat.get("id"),
            chat_type=chat.get("type"),
            user_id=user.get("id"),
            username=user.get("username"),
            first_name=user.get("first_name"),
            text=text,
            command=command,
            command_args=command_args,
            is_bot=user.get("is_bot", False),
            date=datetime.fromtimestamp(message.get("date", 0)) if message.get("date") else None,
        )


class CommandHandler:
    """
    Handles Telegram bot commands for scraping.
    
    Supported commands:
    - /scrape <url> [options] - Scrape a URL
    - /batch <url1> <url2> ... - Scrape multiple URLs
    - /status - Get bot status
    - /help - Show help message
    """
    
    URL_PATTERN = re.compile(
        r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*',
        re.IGNORECASE
    )
    
    def __init__(self, manager: BotManager):
        self.bot_manager = manager
        self._scraping_tasks: Dict[str, asyncio.Task] = {}
    
    async def handle_update(
        self,
        bot_id: str,
        update_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle incoming Telegram update."""
        bot = self.bot_manager.get_bot(bot_id)
        client = self.bot_manager.get_client(bot_id)
        
        if not bot or not client:
            logger.error(f"Bot not found: {bot_id}")
            return {"ok": False, "error": "Bot not found"}
        
        if not bot.is_active:
            logger.warning(f"Bot is inactive: {bot_id}")
            return {"ok": False, "error": "Bot is inactive"}
        
        update = TelegramUpdate.from_dict(update_data)
        
        if update.is_bot:
            return {"ok": True, "message": "Ignored bot message"}
        
        if not self.bot_manager.is_user_allowed(bot_id, update.user_id):
            logger.warning(f"User {update.user_id} not allowed for bot {bot_id}")
            await client.send_message(
                "⛔ You are not authorized to use this bot.",
                chat_id=str(update.chat_id),
                reply_to_message_id=update.message_id,
            )
            return {"ok": False, "error": "User not authorized"}
        
        if update.command:
            return await self._handle_command(bot, client, update)
        
        urls = self.URL_PATTERN.findall(update.text or "")
        if urls:
            return await self._handle_auto_scrape(bot, client, update, urls)
        
        return {"ok": True, "message": "No action taken"}
    
    async def _handle_command(
        self,
        bot: BotConfig,
        client: TelegramBotClient,
        update: TelegramUpdate,
    ) -> Dict[str, Any]:
        """Handle a bot command."""
        command = update.command.lower()
        
        if command not in bot.allowed_commands and command not in ["start", "help"]:
            await client.send_message(
                f"⚠️ Command /{command} is not available.",
                chat_id=str(update.chat_id),
                reply_to_message_id=update.message_id,
            )
            return {"ok": False, "error": "Command not allowed"}
        
        handlers = {
            "start": self._cmd_start,
            "help": self._cmd_help,
            "scrape": self._cmd_scrape,
            "batch": self._cmd_batch,
            "status": self._cmd_status,
            "cancel": self._cmd_cancel,
        }
        
        handler = handlers.get(command)
        if handler:
            return await handler(bot, client, update)
        
        await client.send_message(
            f"❓ Unknown command: /{command}\n\nUse /help for available commands.",
            chat_id=str(update.chat_id),
            reply_to_message_id=update.message_id,
        )
        return {"ok": False, "error": "Unknown command"}
    
    async def _cmd_start(
        self,
        bot: BotConfig,
        client: TelegramBotClient,
        update: TelegramUpdate,
    ) -> Dict[str, Any]:
        """Handle /start command."""
        message = (
            f"👋 <b>Welcome to {bot.bot_name}!</b>\n\n"
            f"I can scrape websites and send results.\n\n"
            f"<b>Quick Start:</b>\n"
            f"• Send me a URL to scrape it\n"
            f"• Use /scrape &lt;url&gt; for options\n"
            f"• Use /batch &lt;urls&gt; for multiple URLs\n\n"
            f"Use /help for all commands."
        )
        
        await client.send_message(
            message,
            chat_id=str(update.chat_id),
            reply_to_message_id=update.message_id,
        )
        return {"ok": True, "command": "start"}
    
    async def _cmd_help(
        self,
        bot: BotConfig,
        client: TelegramBotClient,
        update: TelegramUpdate,
    ) -> Dict[str, Any]:
        """Handle /help command."""
        message = (
            f"📖 <b>{bot.bot_name} Commands</b>\n\n"
            f"<b>/scrape</b> &lt;url&gt; [options]\n"
            f"  Scrape a single URL\n"
            f"  Options: <code>wait=5</code>, <code>noscreen</code>\n\n"
            f"<b>/batch</b> &lt;url1&gt; &lt;url2&gt; ...\n"
            f"  Scrape multiple URLs (max 10)\n\n"
            f"<b>/status</b> - Bot status\n"
            f"<b>/cancel</b> - Cancel task\n\n"
            f"💡 Or just send any URL!"
        )
        
        await client.send_message(
            message,
            chat_id=str(update.chat_id),
            reply_to_message_id=update.message_id,
        )
        return {"ok": True, "command": "help"}
    
    async def _cmd_scrape(
        self,
        bot: BotConfig,
        client: TelegramBotClient,
        update: TelegramUpdate,
    ) -> Dict[str, Any]:
        """Handle /scrape command."""
        args = update.command_args or ""
        
        urls = self.URL_PATTERN.findall(args)
        if not urls:
            await client.send_message(
                "⚠️ Please provide a URL.\n\n"
                "Example: <code>/scrape https://example.com</code>",
                chat_id=str(update.chat_id),
                reply_to_message_id=update.message_id,
            )
            return {"ok": False, "error": "No URL provided"}
        
        url = urls[0]
        options = self._parse_scrape_options(args, bot)
        
        await client.send_typing_action(str(update.chat_id))
        await client.send_message(
            f"🔄 <b>Scraping...</b>\n\n🔗 {url}",
            chat_id=str(update.chat_id),
            reply_to_message_id=update.message_id,
        )
        
        try:
            result = await selenium_scraper.scrape(
                url=url,
                wait_time=options.get("wait_time"),
                take_screenshot=options.get("take_screenshot", True),
            )
            
            # Send to user
            await client.send_scrape_result(
                url=result["url"],
                title=result.get("title"),
                data=result.get("data", {}),
                screenshot=result.get("screenshot") if options.get("take_screenshot") else None,
                error=result.get("error"),
                chat_id=str(update.chat_id),
                reply_to_message_id=update.message_id,
                source="telegram",
            )
            
            # Send to channel
            if bot.send_to_channel and str(update.chat_id) != bot.channel_id:
                await client.send_scrape_result(
                    url=result["url"],
                    title=result.get("title"),
                    data=result.get("data", {}),
                    screenshot=result.get("screenshot") if options.get("take_screenshot") else None,
                    error=result.get("error"),
                    source=f"telegram (@{update.username or update.user_id})",
                )
            
            return {"ok": True, "command": "scrape", "url": url}
        
        except Exception as e:
            logger.exception(f"Scraping error: {e}")
            await client.send_message(
                f"❌ <b>Scraping Failed</b>\n\n⚠️ {str(e)}",
                chat_id=str(update.chat_id),
                reply_to_message_id=update.message_id,
            )
            return {"ok": False, "error": str(e)}
    
    async def _cmd_batch(
        self,
        bot: BotConfig,
        client: TelegramBotClient,
        update: TelegramUpdate,
    ) -> Dict[str, Any]:
        """Handle /batch command."""
        args = update.command_args or ""
        
        urls = self.URL_PATTERN.findall(args)
        if not urls:
            await client.send_message(
                "⚠️ Please provide URLs.\n\n"
                "Example: <code>/batch https://a.com https://b.com</code>",
                chat_id=str(update.chat_id),
                reply_to_message_id=update.message_id,
            )
            return {"ok": False, "error": "No URLs provided"}
        
        max_urls = 10
        if len(urls) > max_urls:
            urls = urls[:max_urls]
        
        await client.send_typing_action(str(update.chat_id))
        await client.send_message(
            f"🔄 <b>Batch Scraping {len(urls)} URLs...</b>",
            chat_id=str(update.chat_id),
            reply_to_message_id=update.message_id,
        )
        
        results = await selenium_scraper.scrape_multiple(urls=urls, take_screenshot=False)
        
        successful = sum(1 for r in results if r.get("success"))
        failed = len(results) - successful
        
        summary = (
            f"📊 <b>Batch Complete</b>\n\n"
            f"✅ Success: {successful}\n"
            f"❌ Failed: {failed}\n"
            f"📈 Total: {len(results)}\n\n"
        )
        
        for i, result in enumerate(results, 1):
            status = "✅" if result.get("success") else "❌"
            title = (result.get("title") or "No title")[:25]
            summary += f"{i}. {status} {title}\n"
        
        await client.send_message(summary, chat_id=str(update.chat_id))
        
        if bot.send_to_channel and str(update.chat_id) != bot.channel_id:
            await client.send_message(
                f"📊 <b>Batch by @{update.username or update.user_id}</b>\n"
                f"✅ {successful} / ❌ {failed} / 📈 {len(results)}",
            )
        
        return {"ok": True, "command": "batch", "total": len(results)}
    
    async def _cmd_status(
        self,
        bot: BotConfig,
        client: TelegramBotClient,
        update: TelegramUpdate,
    ) -> Dict[str, Any]:
        """Handle /status command."""
        bot_info = await client.get_me()
        bot_username = bot_info.get("result", {}).get("username", "Unknown")
        
        message = (
            f"📊 <b>Status</b>\n\n"
            f"🤖 {bot.bot_name} (@{bot_username})\n"
            f"📢 Channel: {bot.channel_id}\n"
            f"✅ Active: {'Yes' if bot.is_active else 'No'}\n\n"
            f"⚙️ Screenshot: {'On' if bot.take_screenshot else 'Off'}\n"
            f"⏱️ Timeout: {bot.default_timeout}s\n"
            f"👤 Your ID: {update.user_id}"
        )
        
        await client.send_message(
            message,
            chat_id=str(update.chat_id),
            reply_to_message_id=update.message_id,
        )
        return {"ok": True, "command": "status"}
    
    async def _cmd_cancel(
        self,
        bot: BotConfig,
        client: TelegramBotClient,
        update: TelegramUpdate,
    ) -> Dict[str, Any]:
        """Handle /cancel command."""
        task_key = f"{bot.bot_id}:{update.user_id}"
        
        if task_key in self._scraping_tasks:
            self._scraping_tasks[task_key].cancel()
            del self._scraping_tasks[task_key]
            
            await client.send_message(
                "🛑 Task cancelled.",
                chat_id=str(update.chat_id),
                reply_to_message_id=update.message_id,
            )
            return {"ok": True, "cancelled": True}
        
        await client.send_message(
            "ℹ️ No active task.",
            chat_id=str(update.chat_id),
            reply_to_message_id=update.message_id,
        )
        return {"ok": True, "cancelled": False}
    
    async def _handle_auto_scrape(
        self,
        bot: BotConfig,
        client: TelegramBotClient,
        update: TelegramUpdate,
        urls: List[str],
    ) -> Dict[str, Any]:
        """Auto-scrape URLs sent without command."""
        url = urls[0]
        
        await client.send_typing_action(str(update.chat_id))
        
        try:
            result = await selenium_scraper.scrape(
                url=url,
                take_screenshot=bot.take_screenshot,
                wait_time=bot.default_wait_time,
            )
            
            await client.send_scrape_result(
                url=result["url"],
                title=result.get("title"),
                data=result.get("data", {}),
                screenshot=result.get("screenshot") if bot.take_screenshot else None,
                error=result.get("error"),
                chat_id=str(update.chat_id),
                reply_to_message_id=update.message_id,
                source="telegram (auto)",
            )
            
            if bot.send_to_channel and str(update.chat_id) != bot.channel_id:
                await client.send_scrape_result(
                    url=result["url"],
                    title=result.get("title"),
                    data=result.get("data", {}),
                    screenshot=result.get("screenshot") if bot.take_screenshot else None,
                    error=result.get("error"),
                    source=f"telegram (@{update.username or update.user_id})",
                )
            
            return {"ok": True, "auto_scrape": True, "url": url}
        
        except Exception as e:
            logger.exception(f"Auto-scrape error: {e}")
            return {"ok": False, "error": str(e)}
    
    def _parse_scrape_options(self, args: str, bot: BotConfig) -> Dict[str, Any]:
        """Parse options from command arguments."""
        options = {
            "wait_time": bot.default_wait_time,
            "timeout": bot.default_timeout,
            "take_screenshot": bot.take_screenshot,
        }
        
        wait_match = re.search(r'wait=(\d+)', args, re.IGNORECASE)
        if wait_match:
            options["wait_time"] = min(int(wait_match.group(1)), 30)
        
        if "noscreen" in args.lower():
            options["take_screenshot"] = False
        
        return options


# Global instance
command_handler = CommandHandler(bot_manager)
