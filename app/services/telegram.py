"""
Telegram Notification Service.
Sends messages, images, and documents to Telegram channels/chats.
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class TelegramService:
    """
    Service for sending notifications to Telegram.
    Uses the Telegram Bot API directly via HTTP.
    """

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        default_chat_id: Optional[str] = None,
    ):
        """
        Initialize Telegram service.

        Args:
            bot_token: Telegram bot token from @BotFather
            default_chat_id: Default chat/channel ID to send messages
        """
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.default_chat_id = default_chat_id or settings.TELEGRAM_CHANNEL_ID or settings.TELEGRAM_CHAT_ID
        self.parse_mode = settings.TELEGRAM_PARSE_MODE
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token and self.default_chat_id)

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
        return self.BASE_URL.format(token=self.bot_token, method=method)

    async def _make_request(
        self,
        method: str,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to Telegram API."""
        if not self.is_configured:
            logger.warning("Telegram not configured, skipping notification")
            return {"ok": False, "error": "Telegram not configured"}

        client = await self._get_client()
        url = self._get_url(method)

        try:
            if files:
                response = await client.post(url, data=data, files=files)
            else:
                response = await client.post(url, json=data)

            result = response.json()

            if not result.get("ok"):
                logger.error(f"Telegram API error: {result}")

            return result

        except Exception as e:
            logger.exception(f"Failed to send Telegram request: {e}")
            return {"ok": False, "error": str(e)}

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: bool = False,
        disable_notification: bool = False,
        reply_markup: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Send a text message to Telegram.

        Args:
            text: Message text (max 4096 characters)
            chat_id: Target chat ID (uses default if not provided)
            parse_mode: Parse mode (HTML or Markdown)
            disable_web_page_preview: Disable link previews
            disable_notification: Send silently
            reply_markup: Inline keyboard or other markup

        Returns:
            Telegram API response
        """
        data = {
            "chat_id": chat_id or self.default_chat_id,
            "text": text[:4096],  # Telegram limit
            "parse_mode": parse_mode or self.parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
            "disable_notification": disable_notification,
        }

        if reply_markup:
            data["reply_markup"] = reply_markup

        return await self._make_request("sendMessage", data)

    async def send_photo(
        self,
        photo: Union[str, bytes, Path],
        caption: Optional[str] = None,
        chat_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a photo to Telegram.

        Args:
            photo: Photo URL, file path, or bytes
            caption: Photo caption (max 1024 characters)
            chat_id: Target chat ID
            parse_mode: Parse mode for caption

        Returns:
            Telegram API response
        """
        data = {
            "chat_id": chat_id or self.default_chat_id,
            "parse_mode": parse_mode or self.parse_mode,
        }

        if caption:
            data["caption"] = caption[:1024]

        # Handle different photo input types
        if isinstance(photo, str) and (photo.startswith("http://") or photo.startswith("https://")):
            # URL
            data["photo"] = photo
            return await self._make_request("sendPhoto", data)
        elif isinstance(photo, (str, Path)):
            # File path
            photo_path = Path(photo)
            if not photo_path.exists():
                return {"ok": False, "error": f"Photo file not found: {photo}"}
            with open(photo_path, "rb") as f:
                files = {"photo": (photo_path.name, f.read(), "image/png")}
            return await self._make_request("sendPhoto", data, files=files)
        elif isinstance(photo, bytes):
            # Bytes
            files = {"photo": ("screenshot.png", photo, "image/png")}
            return await self._make_request("sendPhoto", data, files=files)

        return {"ok": False, "error": "Invalid photo input"}

    async def send_document(
        self,
        document: Union[str, bytes, Path],
        filename: Optional[str] = None,
        caption: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a document to Telegram.

        Args:
            document: Document URL, file path, or bytes
            filename: Filename for bytes input
            caption: Document caption
            chat_id: Target chat ID

        Returns:
            Telegram API response
        """
        data = {
            "chat_id": chat_id or self.default_chat_id,
            "parse_mode": self.parse_mode,
        }

        if caption:
            data["caption"] = caption[:1024]

        if isinstance(document, str) and document.startswith("http"):
            data["document"] = document
            return await self._make_request("sendDocument", data)
        elif isinstance(document, (str, Path)):
            doc_path = Path(document)
            if not doc_path.exists():
                return {"ok": False, "error": f"Document not found: {document}"}
            with open(doc_path, "rb") as f:
                files = {"document": (doc_path.name, f.read())}
            return await self._make_request("sendDocument", data, files=files)
        elif isinstance(document, bytes):
            files = {"document": (filename or "document.txt", document)}
            return await self._make_request("sendDocument", data, files=files)

        return {"ok": False, "error": "Invalid document input"}

    async def send_scrape_result(
        self,
        url: str,
        title: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        screenshot: Optional[bytes] = None,
        error: Optional[str] = None,
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a formatted scraping result to Telegram.

        Args:
            url: Scraped URL
            title: Page title
            data: Extracted data dictionary
            screenshot: Screenshot bytes
            error: Error message if scraping failed
            chat_id: Target chat ID

        Returns:
            Telegram API response
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        if error:
            # Error message
            message = (
                f"❌ <b>Scraping Failed</b>\n\n"
                f"🔗 <b>URL:</b> {url}\n"
                f"⚠️ <b>Error:</b> {error}\n"
                f"🕐 <b>Time:</b> {timestamp}"
            )
            return await self.send_message(message, chat_id=chat_id)

        # Success message
        message_parts = [
            f"✅ <b>Scraping Complete</b>\n",
            f"🔗 <b>URL:</b> {url}",
        ]

        if title:
            message_parts.append(f"📄 <b>Title:</b> {title}")

        if data:
            message_parts.append("\n📊 <b>Extracted Data:</b>")
            for key, value in data.items():
                # Truncate long values
                str_value = str(value)
                if len(str_value) > 200:
                    str_value = str_value[:200] + "..."
                message_parts.append(f"  • <b>{key}:</b> {str_value}")

        message_parts.append(f"\n🕐 <b>Time:</b> {timestamp}")

        message = "\n".join(message_parts)

        # Send screenshot first if available
        if screenshot:
            await self.send_photo(
                screenshot,
                caption=f"📸 Screenshot of {url}",
                chat_id=chat_id,
            )

        return await self.send_message(message, chat_id=chat_id)

    async def send_batch_results(
        self,
        results: List[Dict[str, Any]],
        chat_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a summary of batch scraping results.

        Args:
            results: List of scraping results
            chat_id: Target chat ID

        Returns:
            Telegram API response
        """
        total = len(results)
        successful = sum(1 for r in results if r.get("success", False))
        failed = total - successful

        message = (
            f"📊 <b>Batch Scraping Summary</b>\n\n"
            f"✅ Successful: {successful}\n"
            f"❌ Failed: {failed}\n"
            f"📈 Total: {total}\n"
            f"🕐 Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        return await self.send_message(message, chat_id=chat_id)

    async def get_me(self) -> Dict[str, Any]:
        """Get bot information."""
        return await self._make_request("getMe")

    async def get_chat(self, chat_id: Optional[str] = None) -> Dict[str, Any]:
        """Get chat information."""
        return await self._make_request(
            "getChat",
            {"chat_id": chat_id or self.default_chat_id}
        )


# Global service instance
telegram_service = TelegramService()
