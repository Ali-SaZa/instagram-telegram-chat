"""
Main application entry point for Instagram-Telegram chat integration.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import aiohttp
from aiohttp import web
from aiohttp.web import Application, AppRunner, TCPSite

from config.settings import get_settings
from database.connection import initialize_database, cleanup_database, db_manager
from services.sync_service import get_sync_service
from services.webhook_handler import get_webhook_handler, handle_webhook_request
from services.realtime_service import get_realtime_service
from services.message_queue import get_message_queue_service
from services.media_handler import get_media_handler
from telegram_bot.bot import setup_telegram_handlers
from telegram_bot.session import TelegramSessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/app.log')
    ]
)

logger = logging.getLogger(__name__)


class InstagramTelegramApp:
    """Main application class for Instagram-Telegram chat integration."""
    
    def __init__(self):
        self.settings = get_settings()
        self.app: Optional[Application] = None
        self.runner: Optional[AppRunner] = None
        self.site: Optional[TCPSite] = None
        self.telegram_session_manager: Optional[TelegramSessionManager] = None
        self.sync_service = None
        self.webhook_handler = None
        self.realtime_service = None
        self.message_queue_service = None
        self.media_handler = None
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        asyncio.create_task(self.shutdown())
    
    async def initialize(self):
        """Initialize the application and all services."""
        try:
            logger.info("Initializing Instagram-Telegram chat integration application...")
            
            # Initialize database
            logger.info("Initializing database...")
            await initialize_database()
            
            # Initialize services
            logger.info("Initializing services...")
            self.sync_service = await get_sync_service()
            self.webhook_handler = await get_webhook_handler()
            
            # Initialize Phase 4 services (Real-time communication)
            logger.info("Initializing real-time services...")
            self.message_queue_service = await get_message_queue_service()
            self.realtime_service = await get_realtime_service()
            self.media_handler = await get_media_handler()
            
            # Initialize Telegram session manager
            logger.info("Initializing Telegram session manager...")
            self.telegram_session_manager = TelegramSessionManager()
            await self.telegram_session_manager.initialize()
            
            # Setup web application
            logger.info("Setting up web application...")
            await self._setup_web_app()
            
            # Setup Telegram bot handlers
            logger.info("Setting up Telegram bot handlers...")
            await setup_telegram_handlers()
            
            logger.info("Application initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise
    
    async def _setup_web_app(self):
        """Setup the web application and routes."""
        self.app = Application()
        
        # Add routes
        self.app.router.add_post('/webhook/instagram', handle_webhook_request)
        self.app.router.add_get('/health', self._health_check_handler)
        self.app.router.add_get('/status', self._status_handler)
        self.app.router.add_get('/stats', self._stats_handler)
        
        # Add middleware for logging
        self.app.middlewares.append(self._logging_middleware)
        
        # Create runner and site
        self.runner = AppRunner(self.app)
        await self.runner.setup()
        
        # Start the site
        self.site = TCPSite(
            self.runner,
            '0.0.0.0',
            self.settings.telegram.webhook_port
        )
        await self.site.start()
        
        logger.info(f"Web application started on port {self.settings.telegram.webhook_port}")
    
    async def _logging_middleware(self, request, handler):
        """Middleware for logging HTTP requests."""
        start_time = asyncio.get_event_loop().time()
        
        try:
            response = await handler(request)
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.info(f"{request.method} {request.path} - {response.status} - {duration:.2f}ms")
            return response
        except Exception as e:
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.error(f"{request.method} {request.path} - ERROR - {duration:.2f}ms - {e}")
            raise
    
    async def _health_check_handler(self, request):
        """Health check endpoint."""
        try:
            # Check database health
            db_health = await db_manager.health_check()
            
            # Check webhook handler health
            webhook_health = await self.webhook_handler.health_check()
            
            # Check sync service health
            sync_health = await self.sync_service.health_check() if self.sync_service else {"status": "not_initialized"}
            
            # Check Phase 4 services health
            message_queue_health = await self.message_queue_service.health_check() if self.message_queue_service else {"status": "not_initialized"}
            realtime_health = await self.realtime_service.health_check() if self.realtime_service else {"status": "not_initialized"}
            media_handler_health = await self.media_handler.health_check() if self.media_handler else {"status": "not_initialized"}
            
            overall_status = "healthy" if all(
                h.get("status") == "healthy" for h in [db_health, webhook_health, sync_health, message_queue_health, realtime_health, media_handler_health]
            ) else "unhealthy"
            
            return web.json_response({
                "status": overall_status,
                "timestamp": asyncio.get_event_loop().time(),
                "services": {
                    "database": db_health,
                    "webhook_handler": webhook_health,
                    "sync_service": sync_health,
                    "message_queue": message_queue_health,
                    "realtime_service": realtime_health,
                    "media_handler": media_handler_health
                }
            })
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)
    
    async def _status_handler(self, request):
        """Status endpoint for detailed system information."""
        try:
            # Get database info
            db_info = await db_manager.get_database_info()
            
            # Get webhook stats
            webhook_stats = await self.webhook_handler.get_webhook_stats()
            
            # Get sync service status
            sync_status = await self.sync_service.get_sync_status() if self.sync_service else {}
            
            # Get Phase 4 services status
            message_queue_stats = await self.message_queue_service.get_queue_stats() if self.message_queue_service else {}
            realtime_stats = await self.realtime_service.get_connection_stats() if self.realtime_service else {}
            media_stats = await self.media_handler.get_storage_stats() if self.media_handler else {}
            
            return web.json_response({
                "status": "operational",
                "timestamp": asyncio.get_event_loop().time(),
                "database": db_info,
                "webhook": webhook_stats,
                "sync": sync_status,
                "message_queue": message_queue_stats,
                "realtime": realtime_stats,
                "media": media_stats,
                "telegram": {
                    "webhook_port": self.settings.telegram.webhook_port,
                    "webhook_url": self.settings.telegram.webhook_url,
                    "sessions_active": len(await self.telegram_session_manager.get_active_sessions()) if self.telegram_session_manager else 0
                }
            })
            
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            return web.json_response({
                "status": "error",
                "error": str(e)
            }, status=500)
    
    async def _stats_handler(self, request):
        """Statistics endpoint for monitoring."""
        try:
            # Get various statistics
            stats = {
                "timestamp": asyncio.get_event_loop().time(),
                "database": await db_manager.get_database_info(),
                "webhook": await self.webhook_handler.get_webhook_stats(),
                "sync": await self.sync_service.get_sync_stats() if self.sync_service else {},
                "message_queue": await self.message_queue_service.get_queue_stats() if self.message_queue_service else {},
                "realtime": await self.realtime_service.get_connection_stats() if self.realtime_service else {},
                "media": await self.media_handler.get_storage_stats() if self.media_handler else {},
                "telegram": {
                    "active_sessions": len(await self.telegram_session_manager.get_active_sessions()) if self.telegram_session_manager else 0,
                    "total_sessions": len(await self.telegram_session_manager.get_all_sessions()) if self.telegram_session_manager else 0
                }
            }
            
            return web.json_response(stats)
            
        except Exception as e:
            logger.error(f"Stats check failed: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    async def start(self):
        """Start the application."""
        try:
            await self.initialize()
            logger.info("Application started successfully")
            
            # Keep the application running
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Application error: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the application gracefully."""
        try:
            logger.info("Shutting down application...")
            
            # Stop web server
            if self.site:
                await self.site.stop()
                logger.info("Web server stopped")
            
            if self.runner:
                await self.runner.cleanup()
                logger.info("Web runner cleaned up")
            
            # Cleanup services
            if self.telegram_session_manager:
                await self.telegram_session_manager.cleanup()
                logger.info("Telegram session manager cleaned up")
            
            # Cleanup Phase 4 services
            if self.media_handler:
                await self.media_handler.cleanup()
                logger.info("Media handler cleaned up")
            
            if self.realtime_service:
                await self.realtime_service.cleanup()
                logger.info("Real-time service cleaned up")
            
            if self.message_queue_service:
                await self.message_queue_service.cleanup()
                logger.info("Message queue service cleaned up")
            
            # Cleanup database
            await cleanup_database()
            logger.info("Database connection closed")
            
            logger.info("Application shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        finally:
            # Exit the application
            sys.exit(0)


async def main():
    """Main entry point."""
    try:
        app = InstagramTelegramApp()
        await app.start()
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the application
    asyncio.run(main()) 