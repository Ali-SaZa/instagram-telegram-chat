"""
Application configuration and settings management.
"""

import os
from pathlib import Path
from typing import Optional, List
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        alias="MONGODB_URI",
        description="MongoDB connection URI"
    )
    
    mongodb_database: str = Field(
        default="instagram_telegram_chat",
        alias="MONGODB_DATABASE",
        description="MongoDB database name"
    )
    
    mongodb_max_pool_size: int = Field(
        default=10,
        alias="MONGODB_MAX_POOL_SIZE",
        description="MongoDB connection pool size"
    )
    
    mongodb_min_pool_size: int = Field(
        default=1,
        alias="MONGODB_MIN_POOL_SIZE",
        description="MongoDB minimum connection pool size"
    )
    
    mongodb_max_idle_time: int = Field(
        default=30000,
        alias="MONGODB_MAX_IDLE_TIME",
        description="MongoDB max idle time in milliseconds"
    )


class InstagramSettings(BaseSettings):
    """Instagram API settings."""
    
    instagram_username: str = Field(
        default="",
        alias="INSTAGRAM_USERNAME",
        description="Instagram username"
    )
    
    instagram_password: str = Field(
        default="",
        alias="INSTAGRAM_PASSWORD",
        description="Instagram password"
    )
    
    instagram_session_file: str = Field(
        default="instagram_session.json",
        alias="INSTAGRAM_SESSION_FILE",
        description="Instagram session file path"
    )
    
    instagram_sync_interval: int = Field(
        default=300,
        alias="INSTAGRAM_SYNC_INTERVAL",
        description="Instagram sync interval in seconds"
    )
    
    instagram_max_retries: int = Field(
        default=3,
        alias="INSTAGRAM_MAX_RETRIES",
        description="Maximum retry attempts for Instagram operations"
    )
    
    instagram_retry_delay: int = Field(
        default=60,
        alias="INSTAGRAM_RETRY_DELAY",
        description="Retry delay in seconds"
    )
    
    instagram_batch_size: int = Field(
        default=50,
        alias="INSTAGRAM_BATCH_SIZE",
        description="Batch size for Instagram operations"
    )
    
    instagram_enable_realtime: bool = Field(
        default=True,
        alias="INSTAGRAM_ENABLE_REALTIME",
        description="Enable real-time Instagram updates"
    )


class TelegramSettings(BaseSettings):
    """Telegram bot settings."""
    
    bot_token: str = Field(
        default="",
        alias="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token"
    )
    
    webhook_url: Optional[str] = Field(
        default=None,
        alias="TELEGRAM_WEBHOOK_URL",
        description="Telegram webhook URL"
    )
    
    webhook_port: int = Field(
        default=8443,
        alias="TELEGRAM_WEBHOOK_PORT",
        description="Telegram webhook port"
    )
    
    webhook_cert: Optional[str] = Field(
        default=None,
        alias="TELEGRAM_WEBHOOK_CERT",
        description="Telegram webhook certificate path"
    )
    
    webhook_key: Optional[str] = Field(
        default=None,
        alias="TELEGRAM_WEBHOOK_KEY",
        description="Telegram webhook private key path"
    )
    
    polling_timeout: int = Field(
        default=30,
        alias="TELEGRAM_POLLING_TIMEOUT",
        description="Telegram polling timeout in seconds"
    )
    
    max_connections: int = Field(
        default=100,
        alias="TELEGRAM_MAX_CONNECTIONS",
        description="Maximum Telegram connections"
    )


class RedisSettings(BaseSettings):
    """Redis settings for caching and message queuing."""
    
    redis_host: str = Field(
        default="localhost",
        alias="REDIS_HOST",
        description="Redis host"
    )
    
    redis_port: int = Field(
        default=6379,
        alias="REDIS_PORT",
        description="Redis port"
    )
    
    redis_password: Optional[str] = Field(
        default=None,
        alias="REDIS_PASSWORD",
        description="Redis password"
    )
    
    redis_database: int = Field(
        default=0,
        alias="REDIS_DATABASE",
        description="Redis database number"
    )
    
    redis_max_connections: int = Field(
        default=10,
        alias="REDIS_MAX_CONNECTIONS",
        description="Redis max connections"
    )


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level"
    )
    
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        alias="LOG_FORMAT",
        description="Log format string"
    )
    
    log_file: Optional[str] = Field(
        default=None,
        alias="LOG_FILE",
        description="Log file path"
    )
    
    log_max_size: int = Field(
        default=10485760,  # 10MB
        alias="LOG_MAX_SIZE",
        description="Maximum log file size in bytes"
    )
    
    log_backup_count: int = Field(
        default=5,
        alias="LOG_BACKUP_COUNT",
        description="Number of log backup files"
    )


class SecuritySettings(BaseSettings):
    """Security and privacy settings."""
    
    encryption_key: Optional[str] = Field(
        default=None,
        alias="ENCRYPTION_KEY",
        description="Encryption key for sensitive data"
    )
    
    enable_encryption: bool = Field(
        default=True,
        alias="ENABLE_ENCRYPTION",
        description="Enable data encryption"
    )
    
    api_rate_limit: int = Field(
        default=100,
        alias="API_RATE_LIMIT",
        description="API rate limit per minute"
    )
    
    session_timeout: int = Field(
        default=3600,
        alias="SESSION_TIMEOUT",
        description="Session timeout in seconds"
    )


class Settings(BaseSettings):
    """Main application settings."""
    
    # Environment
    environment: str = Field(
        default="development",
        alias="ENVIRONMENT",
        description="Application environment"
    )
    
    debug: bool = Field(
        default=False,
        alias="DEBUG",
        description="Enable debug mode"
    )
    
    # Base directories
    base_dir: Path = Path(__file__).parent.parent
    data_dir: Path = base_dir / "data"
    logs_dir: Path = base_dir / "logs"
    sessions_dir: Path = base_dir / "sessions"
    
    # Feature flags
    enable_webhooks: bool = Field(
        default=True,
        alias="ENABLE_WEBHOOKS",
        description="Enable webhook support"
    )
    
    enable_sync_service: bool = Field(
        default=True,
        alias="ENABLE_SYNC_SERVICE",
        description="Enable Instagram sync service"
    )
    
    enable_telegram_bot: bool = Field(
        default=True,
        alias="ENABLE_TELEGRAM_BOT",
        description="Enable Telegram bot"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize nested settings after the parent is initialized
        # This ensures environment variables are loaded first
        self._database = None
        self._instagram = None
        self._telegram = None
        self._redis = None
        self._logging = None
        self._security = None
        self._create_directories()
    
    def _create_directories(self):
        """Create necessary directories if they don't exist."""
        directories = [
            self.data_dir,
            self.logs_dir,
            self.sessions_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @property
    def database(self) -> DatabaseSettings:
        if self._database is None:
            self._database = DatabaseSettings()
        return self._database
    
    @property
    def instagram(self) -> InstagramSettings:
        if self._instagram is None:
            self._instagram = InstagramSettings()
        return self._instagram
    
    @property
    def telegram(self) -> TelegramSettings:
        if self._telegram is None:
            self._telegram = TelegramSettings()
        return self._telegram
    
    @property
    def redis(self) -> RedisSettings:
        if self._redis is None:
            self._redis = RedisSettings()
        return self._redis
    
    @property
    def logging(self) -> LoggingSettings:
        if self._logging is None:
            self._logging = LoggingSettings()
        return self._logging
    
    @property
    def security(self) -> SecuritySettings:
        if self._security is None:
            self._security = SecuritySettings()
        return self._security
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment.lower() == "testing"
    
    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        if self.redis.redis_password:
            return f"redis://:{self.redis.redis_password}@{self.redis.redis_host}:{self.redis.redis_port}/{self.redis.redis_database}"
        return f"redis://{self.redis.redis_host}:{self.redis.redis_port}/{self.redis.redis_database}"
    
    @property
    def websocket_host(self) -> str:
        """Get WebSocket host."""
        return "0.0.0.0"
    
    @property
    def websocket_port(self) -> int:
        """Get WebSocket port."""
        return 8765
    
    @property
    def media_cache_path(self) -> str:
        """Get media cache path."""
        return str(self.data_dir / "media_cache")
    
    @property
    def max_media_file_size(self) -> int:
        """Get maximum media file size."""
        return 100 * 1024 * 1024  # 100MB


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get global settings instance."""
    return settings


def reload_settings():
    """Reload settings from environment."""
    global settings
    settings = Settings()
    return settings 