"""
Configuration settings for Instagram-Telegram chat integration.
"""

import os
from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        env="MONGODB_URI",
        description="MongoDB connection URI"
    )
    
    mongodb_database: str = Field(
        default="instagram_telegram_chat",
        env="MONGODB_DATABASE",
        description="MongoDB database name"
    )
    
    mongodb_max_pool_size: int = Field(
        default=10,
        env="MONGODB_MAX_POOL_SIZE",
        description="MongoDB connection pool size"
    )
    
    mongodb_min_pool_size: int = Field(
        default=1,
        env="MONGODB_MIN_POOL_SIZE",
        description="MongoDB minimum connection pool size"
    )
    
    mongodb_max_idle_time: int = Field(
        default=30000,
        env="MONGODB_MAX_IDLE_TIME",
        description="MongoDB max idle time in milliseconds"
    )


class InstagramSettings(BaseSettings):
    """Instagram API settings."""
    
    instagram_username: str = Field(
        default="",
        env="INSTAGRAM_USERNAME",
        description="Instagram username"
    )
    
    instagram_password: str = Field(
        default="",
        env="INSTAGRAM_PASSWORD",
        description="Instagram password"
    )
    
    instagram_session_file: str = Field(
        default="instagram_session.json",
        env="INSTAGRAM_SESSION_FILE",
        description="Instagram session file path"
    )
    
    instagram_sync_interval: int = Field(
        default=300,
        env="INSTAGRAM_SYNC_INTERVAL",
        description="Instagram sync interval in seconds"
    )
    
    instagram_max_retries: int = Field(
        default=3,
        env="INSTAGRAM_MAX_RETRIES",
        description="Maximum retry attempts for Instagram operations"
    )
    
    instagram_retry_delay: int = Field(
        default=60,
        env="INSTAGRAM_RETRY_DELAY",
        description="Retry delay in seconds"
    )
    
    instagram_batch_size: int = Field(
        default=50,
        env="INSTAGRAM_BATCH_SIZE",
        description="Batch size for Instagram operations"
    )
    
    instagram_enable_realtime: bool = Field(
        default=True,
        env="INSTAGRAM_ENABLE_REALTIME",
        description="Enable real-time Instagram updates"
    )


class TelegramSettings(BaseSettings):
    """Telegram bot settings."""
    
    telegram_bot_token: str = Field(
        default="",
        env="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token"
    )
    
    telegram_webhook_url: Optional[str] = Field(
        default=None,
        env="TELEGRAM_WEBHOOK_URL",
        description="Telegram webhook URL"
    )
    
    telegram_webhook_port: int = Field(
        default=8443,
        env="TELEGRAM_WEBHOOK_PORT",
        description="Telegram webhook port"
    )
    
    telegram_webhook_cert: Optional[str] = Field(
        default=None,
        env="TELEGRAM_WEBHOOK_CERT",
        description="Telegram webhook certificate path"
    )
    
    telegram_webhook_key: Optional[str] = Field(
        default=None,
        env="TELEGRAM_WEBHOOK_KEY",
        description="Telegram webhook private key path"
    )
    
    telegram_polling_timeout: int = Field(
        default=30,
        env="TELEGRAM_POLLING_TIMEOUT",
        description="Telegram polling timeout in seconds"
    )
    
    telegram_max_connections: int = Field(
        default=100,
        env="TELEGRAM_MAX_CONNECTIONS",
        description="Maximum Telegram connections"
    )


class RedisSettings(BaseSettings):
    """Redis settings for caching and message queuing."""
    
    redis_host: str = Field(
        default="localhost",
        env="REDIS_HOST",
        description="Redis host"
    )
    
    redis_port: int = Field(
        default=6379,
        env="REDIS_PORT",
        description="Redis port"
    )
    
    redis_password: Optional[str] = Field(
        default=None,
        env="REDIS_PASSWORD",
        description="Redis password"
    )
    
    redis_database: int = Field(
        default=0,
        env="REDIS_DATABASE",
        description="Redis database number"
    )
    
    redis_max_connections: int = Field(
        default=10,
        env="REDIS_MAX_CONNECTIONS",
        description="Redis max connections"
    )


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    
    log_level: str = Field(
        default="INFO",
        env="LOG_LEVEL",
        description="Logging level"
    )
    
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT",
        description="Log format string"
    )
    
    log_file: Optional[str] = Field(
        default=None,
        env="LOG_FILE",
        description="Log file path"
    )
    
    log_max_size: int = Field(
        default=10485760,  # 10MB
        env="LOG_MAX_SIZE",
        description="Maximum log file size in bytes"
    )
    
    log_backup_count: int = Field(
        default=5,
        env="LOG_BACKUP_COUNT",
        description="Number of log backup files"
    )


class SecuritySettings(BaseSettings):
    """Security and privacy settings."""
    
    encryption_key: Optional[str] = Field(
        default=None,
        env="ENCRYPTION_KEY",
        description="Encryption key for sensitive data"
    )
    
    enable_encryption: bool = Field(
        default=True,
        env="ENABLE_ENCRYPTION",
        description="Enable data encryption"
    )
    
    api_rate_limit: int = Field(
        default=100,
        env="API_RATE_LIMIT",
        description="API rate limit per minute"
    )
    
    session_timeout: int = Field(
        default=3600,
        env="SESSION_TIMEOUT",
        description="Session timeout in seconds"
    )


class Settings(BaseSettings):
    """Main application settings."""
    
    # Environment
    environment: str = Field(
        default="development",
        env="ENVIRONMENT",
        description="Application environment"
    )
    
    debug: bool = Field(
        default=False,
        env="DEBUG",
        description="Enable debug mode"
    )
    
    # Base directories
    base_dir: Path = Path(__file__).parent.parent
    data_dir: Path = base_dir / "data"
    logs_dir: Path = base_dir / "logs"
    sessions_dir: Path = base_dir / "sessions"
    
    # Component settings
    database: DatabaseSettings = DatabaseSettings()
    instagram: InstagramSettings = InstagramSettings()
    telegram: TelegramSettings = TelegramSettings()
    redis: RedisSettings = RedisSettings()
    logging: LoggingSettings = LoggingSettings()
    security: SecuritySettings = SecuritySettings()
    
    # Feature flags
    enable_webhooks: bool = Field(
        default=True,
        env="ENABLE_WEBHOOKS",
        description="Enable webhook support"
    )
    
    enable_sync_service: bool = Field(
        default=True,
        env="ENABLE_SYNC_SERVICE",
        description="Enable Instagram sync service"
    )
    
    enable_telegram_bot: bool = Field(
        default=True,
        env="ENABLE_TELEGRAM_BOT",
        description="Enable Telegram bot"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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