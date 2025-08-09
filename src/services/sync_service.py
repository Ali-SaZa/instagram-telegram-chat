"""
Instagram data synchronization service.
Handles continuous syncing of Instagram data to MongoDB.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

from ..instagram.client import InstagramClient
from ..database.operations import InstagramOperations

logger = logging.getLogger(__name__)


@dataclass
class SyncConfig:
    """Configuration for sync service."""
    sync_interval: int = 300  # 5 minutes
    max_retries: int = 3
    retry_delay: int = 60  # 1 minute
    batch_size: int = 50
    enable_realtime: bool = True


class InstagramSyncService:
    """
    Service for synchronizing Instagram data with MongoDB.
    Handles continuous syncing and real-time updates.
    """
    
    def __init__(self, instagram_client: InstagramClient, db_ops: InstagramOperations, config: SyncConfig = None):
        """
        Initialize sync service.
        
        Args:
            instagram_client: Instagram API client
            db_ops: Database operations instance
            config: Sync configuration
        """
        self.instagram_client = instagram_client
        self.db_ops = db_ops
        self.config = config or SyncConfig()
        self.is_running = False
        self.last_sync_time = None
        self.sync_stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "total_messages_synced": 0,
            "total_threads_synced": 0,
            "total_users_synced": 0
        }
    
    async def start_sync_loop(self):
        """Start the continuous sync loop."""
        if self.is_running:
            logger.warning("Sync service is already running")
            return
        
        self.is_running = True
        logger.info("Starting Instagram sync service...")
        
        try:
            while self.is_running:
                await self._sync_cycle()
                await asyncio.sleep(self.config.sync_interval)
                
        except asyncio.CancelledError:
            logger.info("Sync service cancelled")
        except Exception as e:
            logger.error(f"Sync service error: {e}")
            self.is_running = False
        finally:
            logger.info("Instagram sync service stopped")
    
    async def stop_sync_loop(self):
        """Stop the continuous sync loop."""
        self.is_running = False
        logger.info("Stopping Instagram sync service...")
    
    async def _sync_cycle(self):
        """Execute one sync cycle."""
        start_time = datetime.now()
        logger.info("Starting sync cycle...")
        
        try:
            # Test connection first
            if not await self.instagram_client.test_connection():
                logger.error("Instagram connection failed, skipping sync")
                return
            
            # Sync all data types
            await self._sync_users()
            await self._sync_threads()
            await self._sync_messages()
            
            # Update sync status
            self.last_sync_time = datetime.now()
            self.sync_stats["total_syncs"] += 1
            self.sync_stats["successful_syncs"] += 1
            
            # Log sync completion
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Sync cycle completed in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Sync cycle failed: {e}")
            self.sync_stats["failed_syncs"] += 1
            
            # Implement retry logic
            await self._handle_sync_error(e)
    
    async def _sync_users(self):
        """Sync Instagram users."""
        try:
            logger.info("Syncing users...")
            
            # Get threads to extract user information
            threads = await self.instagram_client.get_direct_threads(limit=100)
            
            for thread in threads:
                for user_data in thread.get("users", []):
                    try:
                        # Create or update user
                        user_id = await self.db_ops.create_user(user_data)
                        if user_id:
                            self.sync_stats["total_users_synced"] += 1
                            
                    except Exception as e:
                        logger.error(f"Error syncing user {user_data.get('username')}: {e}")
            
            logger.info(f"Users sync completed")
            
        except Exception as e:
            logger.error(f"Users sync failed: {e}")
            raise
    
    async def _sync_threads(self):
        """Sync Instagram threads."""
        try:
            logger.info("Syncing threads...")
            
            # Get all direct threads
            threads = await self.instagram_client.get_direct_threads(limit=100)
            
            for thread_data in threads:
                try:
                    # Create or update thread
                    thread_id = await self.db_ops.create_thread(thread_data)
                    if thread_id:
                        self.sync_stats["total_threads_synced"] += 1
                        
                except Exception as e:
                    logger.error(f"Error syncing thread {thread_data.get('thread_id')}: {e}")
            
            logger.info(f"Threads sync completed")
            
        except Exception as e:
            logger.error(f"Threads sync failed: {e}")
            raise
    
    async def _sync_messages(self):
        """Sync Instagram messages."""
        try:
            logger.info("Syncing messages...")
            
            # Get all threads
            threads = await self.db_ops.get_all_threads(limit=100)
            
            for thread in threads:
                try:
                    # Get messages for this thread
                    messages = await self.instagram_client.get_thread_messages(
                        thread["thread_id"], 
                        limit=self.config.batch_size
                    )
                    
                    for message_data in messages:
                        try:
                            # Create or update message
                            message_id = await self.db_ops.create_message(message_data)
                            if message_id:
                                self.sync_stats["total_messages_synced"] += 1
                                
                        except Exception as e:
                            logger.error(f"Error syncing message {message_data.get('message_id')}: {e}")
                    
                except Exception as e:
                    logger.error(f"Error syncing messages for thread {thread.get('thread_id')}: {e}")
            
            logger.info(f"Messages sync completed")
            
        except Exception as e:
            logger.error(f"Messages sync failed: {e}")
            raise
    
    async def _handle_sync_error(self, error: Exception):
        """Handle sync errors with retry logic."""
        logger.error(f"Handling sync error: {error}")
        
        # Implement exponential backoff retry
        retry_count = 0
        while retry_count < self.config.max_retries:
            retry_count += 1
            delay = self.config.retry_delay * (2 ** (retry_count - 1))
            
            logger.info(f"Retrying sync in {delay} seconds (attempt {retry_count}/{self.config.max_retries})")
            await asyncio.sleep(delay)
            
            try:
                # Test connection before retry
                if await self.instagram_client.test_connection():
                    logger.info("Connection restored, retrying sync...")
                    await self._sync_cycle()
                    return
                    
            except Exception as retry_error:
                logger.error(f"Retry attempt {retry_count} failed: {retry_error}")
        
        logger.error(f"Max retries exceeded, sync failed")
    
    async def manual_sync(self) -> Dict[str, Any]:
        """
        Trigger a manual sync.
        
        Returns:
            Sync results and statistics
        """
        logger.info("Manual sync triggered")
        
        start_time = datetime.now()
        
        try:
            await self._sync_cycle()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": True,
                "duration": duration,
                "timestamp": datetime.now(),
                "stats": self.sync_stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Manual sync failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now(),
                "stats": self.sync_stats.copy()
            }
    
    async def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current sync status.
        
        Returns:
            Sync status information
        """
        return {
            "is_running": self.is_running,
            "last_sync_time": self.last_sync_time,
            "next_sync_time": (
                self.last_sync_time + timedelta(seconds=self.config.sync_interval)
                if self.last_sync_time else None
            ),
            "sync_interval": self.config.sync_interval,
            "stats": self.sync_stats.copy(),
            "instagram_connected": await self.instagram_client.test_connection()
        }
    
    async def reset_sync_stats(self):
        """Reset sync statistics."""
        self.sync_stats = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "total_messages_synced": 0,
            "total_threads_synced": 0,
            "total_users_synced": 0
        }
        logger.info("Sync statistics reset")
    
    async def update_sync_config(self, new_config: SyncConfig):
        """
        Update sync configuration.
        
        Args:
            new_config: New configuration
        """
        self.config = new_config
        logger.info(f"Sync configuration updated: {new_config}")
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            await self.stop_sync_loop()
            await self.instagram_client.close()
            logger.info("Sync service cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of the sync service.
        
        Returns:
            Health status information
        """
        try:
            instagram_connected = await self.instagram_client.test_connection()
            db_connected = await self.db_ops.test_connection()
            
            return {
                "status": "healthy" if (instagram_connected and db_connected) else "unhealthy",
                "instagram_connected": instagram_connected,
                "database_connected": db_connected,
                "is_running": self.is_running,
                "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
                "sync_stats": self.sync_stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def get_sync_stats(self) -> Dict[str, Any]:
        """
        Get sync statistics.
        
        Returns:
            Sync statistics information
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "is_running": self.is_running,
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "next_sync_time": (
                (self.last_sync_time + timedelta(seconds=self.config.sync_interval)).isoformat()
                if self.last_sync_time else None
            ),
            "sync_interval": self.config.sync_interval,
            "stats": self.sync_stats.copy()
        }


class SyncServiceManager:
    """
    Manager for multiple sync services.
    Useful for managing multiple Instagram accounts.
    """
    
    def __init__(self):
        self.services: Dict[str, InstagramSyncService] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
    
    async def add_service(self, service_id: str, service: InstagramSyncService):
        """Add a sync service."""
        self.services[service_id] = service
        logger.info(f"Added sync service: {service_id}")
    
    async def remove_service(self, service_id: str):
        """Remove a sync service."""
        if service_id in self.services:
            await self.services[service_id].cleanup()
            del self.services[service_id]
            
            if service_id in self.tasks:
                self.tasks[service_id].cancel()
                del self.tasks[service_id]
            
            logger.info(f"Removed sync service: {service_id}")
    
    async def start_service(self, service_id: str):
        """Start a specific sync service."""
        if service_id not in self.services:
            raise ValueError(f"Service {service_id} not found")
        
        if service_id in self.tasks and not self.tasks[service_id].done():
            logger.warning(f"Service {service_id} is already running")
            return
        
        service = self.services[service_id]
        task = asyncio.create_task(service.start_sync_loop())
        self.tasks[service_id] = task
        
        logger.info(f"Started sync service: {service_id}")
    
    async def stop_service(self, service_id: str):
        """Stop a specific sync service."""
        if service_id in self.tasks:
            self.tasks[service_id].cancel()
            await self.services[service_id].stop_sync_loop()
            logger.info(f"Stopped sync service: {service_id}")
    
    async def start_all_services(self):
        """Start all sync services."""
        for service_id in self.services:
            await self.start_service(service_id)
    
    async def stop_all_services(self):
        """Stop all sync services."""
        for service_id in list(self.tasks.keys()):
            await self.stop_service(service_id)
    
    async def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all services."""
        status = {}
        for service_id, service in self.services.items():
            status[service_id] = await service.get_sync_status()
        return status
    
    async def cleanup_all(self):
        """Cleanup all services."""
        for service_id in list(self.services.keys()):
            await self.remove_service(service_id) 