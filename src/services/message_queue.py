"""
Message queue service for handling real-time message delivery.
Uses Redis for reliable message queuing and delivery tracking.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

import aioredis
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of messages that can be queued."""
    INSTAGRAM_DM = "instagram_dm"
    TELEGRAM_MESSAGE = "telegram_message"
    NOTIFICATION = "notification"
    SYNC_UPDATE = "sync_update"
    MEDIA_UPDATE = "media_update"


class MessagePriority(str, Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class QueueMessage(BaseModel):
    """Message structure for the queue."""
    id: str = Field(..., description="Unique message ID")
    type: MessageType = Field(..., description="Message type")
    priority: MessagePriority = Field(default=MessagePriority.NORMAL, description="Message priority")
    payload: Dict[str, Any] = Field(..., description="Message payload")
    source: str = Field(..., description="Source system")
    target: str = Field(..., description="Target system")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="Message expiration time")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MessageQueueService:
    """Redis-based message queue service."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """Initialize the message queue service."""
        self.redis_url = redis_url
        self.redis: Optional[aioredis.Redis] = None
        self.consumers: Dict[str, Callable] = {}
        self.running = False
        self.worker_tasks: List[asyncio.Task] = []
        
        # Queue names
        self.queues = {
            MessageType.INSTAGRAM_DM: "instagram_dm_queue",
            MessageType.TELEGRAM_MESSAGE: "telegram_message_queue",
            MessageType.NOTIFICATION: "notification_queue",
            MessageType.SYNC_UPDATE: "sync_update_queue",
            MessageType.MEDIA_UPDATE: "media_update_queue"
        }
        
        # Priority queues
        self.priority_queues = {
            MessagePriority.URGENT: "urgent_queue",
            MessagePriority.HIGH: "high_queue",
            MessagePriority.NORMAL: "normal_queue",
            MessagePriority.LOW: "low_queue"
        }
    
    async def initialize(self):
        """Initialize Redis connection and setup queues."""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            
            # Test connection
            await self.redis.ping()
            logger.info("Message queue service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize message queue service: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            self.running = False
            
            # Cancel worker tasks
            for task in self.worker_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Close Redis connection
            if self.redis:
                await self.redis.close()
            
            logger.info("Message queue service cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def enqueue_message(
        self,
        message: QueueMessage,
        priority: Optional[MessagePriority] = None
    ) -> bool:
        """
        Enqueue a message to the appropriate queue.
        
        Args:
            message: Message to enqueue
            priority: Optional priority override
            
        Returns:
            bool: True if successful
        """
        try:
            if not self.redis:
                raise RuntimeError("Message queue service not initialized")
            
            # Determine priority
            msg_priority = priority or message.priority
            
            # Get queue name
            queue_name = self.queues.get(message.type, "default_queue")
            priority_queue_name = self.priority_queues.get(msg_priority, "normal_queue")
            
            # Serialize message
            message_data = message.json()
            
            # Add to type-specific queue
            await self.redis.lpush(queue_name, message_data)
            
            # Add to priority queue
            await self.redis.lpush(priority_queue_name, message_data)
            
            # Set message metadata
            metadata_key = f"msg:{message.id}"
            metadata = {
                "status": "queued",
                "queued_at": datetime.now(timezone.utc).isoformat(),
                "queue": queue_name,
                "priority": msg_priority.value
            }
            await self.redis.hmset(metadata_key, metadata)
            await self.redis.expire(metadata_key, 3600)  # Expire in 1 hour
            
            logger.debug(f"Message {message.id} enqueued to {queue_name} with priority {msg_priority}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue message {message.id}: {e}")
            return False
    
    async def dequeue_message(
        self,
        message_type: MessageType,
        timeout: int = 1
    ) -> Optional[QueueMessage]:
        """
        Dequeue a message from the specified queue.
        
        Args:
            message_type: Type of message to dequeue
            timeout: Timeout in seconds
            
        Returns:
            QueueMessage: Dequeued message or None
        """
        try:
            if not self.redis:
                raise RuntimeError("Message queue service not initialized")
            
            queue_name = self.queues.get(message_type, "default_queue")
            
            # Try to get message from queue
            result = await self.redis.brpop(queue_name, timeout=timeout)
            
            if result:
                _, message_data = result
                message = QueueMessage.parse_raw(message_data)
                
                # Update message status
                metadata_key = f"msg:{message.id}"
                await self.redis.hset(metadata_key, "status", "processing")
                await self.redis.hset(metadata_key, "dequeued_at", datetime.now(timezone.utc).isoformat())
                
                logger.debug(f"Message {message.id} dequeued from {queue_name}")
                return message
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to dequeue message from {message_type}: {e}")
            return None
    
    async def mark_message_completed(self, message_id: str) -> bool:
        """Mark a message as completed."""
        try:
            if not self.redis:
                raise RuntimeError("Message queue service not initialized")
            
            metadata_key = f"msg:{message_id}"
            await self.redis.hset(metadata_key, "status", "completed")
            await self.redis.hset(metadata_key, "completed_at", datetime.now(timezone.utc).isoformat())
            
            logger.debug(f"Message {message_id} marked as completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark message {message_id} as completed: {e}")
            return False
    
    async def mark_message_failed(self, message_id: str, error: str) -> bool:
        """Mark a message as failed."""
        try:
            if not self.redis:
                raise RuntimeError("Message queue service not initialized")
            
            metadata_key = f"msg:{message_id}"
            await self.redis.hset(metadata_key, "status", "failed")
            await self.redis.hset(metadata_key, "failed_at", datetime.now(timezone.utc).isoformat())
            await self.redis.hset(metadata_key, "error", error)
            
            logger.debug(f"Message {message_id} marked as failed: {error}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to mark message {message_id} as failed: {e}")
            return False
    
    async def retry_message(self, message_id: str) -> bool:
        """Retry a failed message."""
        try:
            if not self.redis:
                raise RuntimeError("Message queue service not initialized")
            
            metadata_key = f"msg:{message_id}"
            
            # Get message data
            message_data = await self.redis.hgetall(metadata_key)
            if not message_data:
                logger.warning(f"Message {message_id} metadata not found")
                return False
            
            # Check retry count
            retry_count = int(message_data.get("retry_count", 0))
            max_retries = int(message_data.get("max_retries", 3))
            
            if retry_count >= max_retries:
                logger.warning(f"Message {message_id} exceeded max retries")
                await self.redis.hset(metadata_key, "status", "dead_letter")
                return False
            
            # Increment retry count
            await self.redis.hincrby(metadata_key, "retry_count", 1)
            await self.redis.hset(metadata_key, "status", "retrying")
            await self.redis.hset(metadata_key, "retry_at", datetime.now(timezone.utc).isoformat())
            
            # Re-queue message with lower priority
            # This would require storing the original message data
            logger.debug(f"Message {message_id} scheduled for retry")
            return True
            
        except Exception as e:
            logger.error(f"Failed to retry message {message_id}: {e}")
            return False
    
    def register_consumer(
        self,
        message_type: MessageType,
        handler: Callable[[QueueMessage], asyncio.Awaitable[bool]]
    ):
        """Register a message consumer."""
        self.consumers[message_type] = handler
        logger.info(f"Registered consumer for {message_type}")
    
    async def start_consumers(self):
        """Start message consumers for all registered types."""
        if not self.consumers:
            logger.warning("No consumers registered")
            return
        
        self.running = True
        
        for message_type, handler in self.consumers.items():
            task = asyncio.create_task(self._consumer_worker(message_type, handler))
            self.worker_tasks.append(task)
            logger.info(f"Started consumer worker for {message_type}")
    
    async def _consumer_worker(
        self,
        message_type: MessageType,
        handler: Callable[[QueueMessage], asyncio.Awaitable[bool]]
    ):
        """Worker task for consuming messages."""
        logger.info(f"Consumer worker started for {message_type}")
        
        while self.running:
            try:
                # Dequeue message
                message = await self.dequeue_message(message_type, timeout=1)
                
                if message:
                    try:
                        # Process message
                        success = await handler(message)
                        
                        if success:
                            await self.mark_message_completed(message.id)
                        else:
                            await self.mark_message_failed(message.id, "Handler returned False")
                            
                    except Exception as e:
                        logger.error(f"Error processing message {message.id}: {e}")
                        await self.mark_message_failed(message.id, str(e))
                        
                        # Schedule retry if possible
                        await self.retry_message(message.id)
                
                # Small delay to prevent busy waiting
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer worker error for {message_type}: {e}")
                await asyncio.sleep(1)  # Wait before retrying
        
        logger.info(f"Consumer worker stopped for {message_type}")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about all queues."""
        try:
            if not self.redis:
                return {"error": "Service not initialized"}
            
            stats = {}
            
            for queue_name in self.queues.values():
                length = await self.redis.llen(queue_name)
                stats[queue_name] = length
            
            for priority_name in self.priority_queues.values():
                length = await self.redis.llen(priority_name)
                stats[priority_name] = length
            
            # Get processing stats
            processing_count = 0
            failed_count = 0
            completed_count = 0
            
            # This is a simplified approach - in production you'd want more efficient counting
            pattern = "msg:*"
            async for key in self.redis.scan_iter(match=pattern):
                status = await self.redis.hget(key, "status")
                if status == "processing":
                    processing_count += 1
                elif status == "failed":
                    failed_count += 1
                elif status == "completed":
                    completed_count += 1
            
            stats.update({
                "processing": processing_count,
                "failed": failed_count,
                "completed": completed_count
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the message queue service."""
        try:
            if not self.redis:
                return {"status": "unhealthy", "error": "Redis not connected"}
            
            # Test Redis connection
            await self.redis.ping()
            
            # Get basic stats
            stats = await self.get_queue_stats()
            
            return {
                "status": "healthy",
                "redis_connected": True,
                "consumers_running": len([t for t in self.worker_tasks if not t.done()]),
                "queue_stats": stats
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "redis_connected": False
            }


# Global message queue service instance
_message_queue_service: Optional[MessageQueueService] = None


async def get_message_queue_service() -> MessageQueueService:
    """Get the global message queue service instance."""
    global _message_queue_service
    
    if _message_queue_service is None:
        from config.settings import get_settings
        settings = get_settings()
        
        _message_queue_service = MessageQueueService(
            redis_url=settings.redis_url
        )
        await _message_queue_service.initialize()
    
    return _message_queue_service


async def cleanup_message_queue_service():
    """Cleanup the global message queue service."""
    global _message_queue_service
    
    if _message_queue_service:
        await _message_queue_service.cleanup()
        _message_queue_service = None 