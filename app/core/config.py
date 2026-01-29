"""
Application configuration using Pydantic Settings.
All settings are loaded from environment variables.
"""
import secrets
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Project Info
    PROJECT_NAME: str = "FastAPI Scraper Server"
    PROJECT_DESCRIPTION: str = "Production-grade FastAPI server with Selenium scraping and Telegram notifications"
    VERSION: str = "1.0.0"

    # Environment
    ENVIRONMENT: str = Field(default="development", description="Current environment")
    DEBUG: bool = Field(default=False, description="Enable debug mode")

    # Server
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=3000, description="Server port")
    WORKERS: int = Field(default=4, description="Number of worker processes")

    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    ENABLE_DOCS: bool = Field(default=True, description="Enable API documentation")

    # Security - API Key Encryption
    API_KEY_SECRET: str = Field(
        default_factory=lambda: secrets.token_hex(32),
        description="Secret key for API key encryption/decryption (32-byte hex string)",
    )
    API_KEY_HEADER_NAME: str = Field(default="X-API-Key", description="Header name for API key")

    # Sentry
    SENTRY_DSN: Optional[str] = None

    # Valid API Keys (comma-separated encrypted keys in production)
    VALID_API_KEYS: str = Field(
        default="dev-key-123,test-key-456",
        description="Comma-separated list of valid API keys (encrypted in production)",
    )

    # CORS
    ALLOWED_ORIGINS: List[str] | str = Field(
        default=["*"],
        description="List of allowed CORS origins",
    )
    ALLOWED_HOSTS: List[str] | str = Field(
        default=["*"],
        description="List of allowed hosts",
    )

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(default=100, description="Max requests per window")
    RATE_LIMIT_WINDOW: int = Field(default=60, description="Rate limit window in seconds")

    # ============== Telegram Configuration ==============
    TELEGRAM_BOT_TOKEN: str = Field(
        default="",
        description="Telegram Bot API token from @BotFather",
    )
    TELEGRAM_CHANNEL_ID: str = Field(
        default="",
        description="Telegram channel ID (e.g., @channelname or -1001234567890)",
    )
    TELEGRAM_CHAT_ID: Optional[str] = Field(
        default=None,
        description="Telegram chat ID for direct messages (optional)",
    )
    TELEGRAM_PARSE_MODE: str = Field(
        default="HTML",
        description="Message parse mode: HTML or Markdown",
    )

    # ============== Selenium Configuration ==============
    SELENIUM_HEADLESS: bool = Field(
        default=True,
        description="Run Chrome in headless mode",
    )
    SELENIUM_TIMEOUT: int = Field(
        default=30,
        description="Default timeout for Selenium operations in seconds",
    )
    SELENIUM_PAGE_LOAD_TIMEOUT: int = Field(
        default=60,
        description="Page load timeout in seconds",
    )
    SELENIUM_IMPLICIT_WAIT: int = Field(
        default=10,
        description="Implicit wait time in seconds",
    )
    CHROME_BINARY_PATH: Optional[str] = Field(
        default=None,
        description="Path to Chrome binary (auto-detected if not set)",
    )
    CHROMEDRIVER_PATH: Optional[str] = Field(
        default=None,
        description="Path to ChromeDriver (auto-detected if not set)",
    )
    SELENIUM_USER_AGENT: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User agent string for Selenium",
    )
    SCREENSHOTS_DIR: str = Field(
        default="/app/screenshots",
        description="Directory to save screenshots",
    )

    # ============== Multi-Bot Configuration ==============
    BOTS_CONFIG: str = Field(
        default="",
        description="JSON array of bot configurations for bulk loading",
    )
    BOTS_CONFIG_FILE: Optional[str] = Field(
        default=None,
        description="Path to JSON file with bot configurations",
    )

    # Database (placeholder for future use)
    DATABASE_URL: str = Field(
        default="sqlite:///./data.db",
        description="Database connection URL",
    )

    # Redis (for caching/rate limiting/celery)
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    
    # Sentry
    SENTRY_DSN: Optional[str] = None
    
    # Bot Credentials
    PANDAMASTER_USER: Optional[str] = None
    PANDAMASTER_PASS: Optional[str] = None
    FIREKIRIN_USER: Optional[str] = None
    FIREKIRIN_PASS: Optional[str] = None

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v

    def get_valid_api_keys(self) -> List[str]:
        """Parse and return list of valid API keys."""
        return [key.strip() for key in self.VALID_API_KEYS.split(",") if key.strip()]

    @property
    def telegram_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.TELEGRAM_BOT_TOKEN and (self.TELEGRAM_CHANNEL_ID or self.TELEGRAM_CHAT_ID))


settings = Settings()
