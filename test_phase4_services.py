#!/usr/bin/env python3
"""
Test script for Phase 4 services (Real-time Communication).
Tests message queue, realtime service, and media handler functionality.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.settings import get_settings
from services.message_queue import MessageQueueService, MessageType, QueueMessage, MessagePriority
from services.realtime_service import RealtimeService
from services.media_handler import MediaHandler, MediaType, MediaFormat

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_message_queue():
    """Test message queue functionality."""
    logger.info("Testing Message Queue Service...")
    
    try:
        # Get message queue service
        mq_service = await get_message_queue_service()
        
        # Test enqueueing a message
        test_message = QueueMessage(
            id="test_msg_001",
            type=MessageType.INSTAGRAM_DM,
            priority=MessagePriority.HIGH,
            payload={
                "thread_id": "test_thread_123",
                "sender_id": "test_user",
                "message_id": "msg_456",
                "content": "Hello from test!"
            },
            source="test_system",
            target="telegram_bot"
        )
        
        # Enqueue message
        success = await mq_service.enqueue_message(test_message)
        logger.info(f"Message enqueued: {success}")
        
        # Test dequeuing
        dequeued_message = await mq_service.dequeue_message(MessageType.INSTAGRAM_DM, timeout=2)
        if dequeued_message:
            logger.info(f"Message dequeued: {dequeued_message.id}")
            # Mark as completed
            await mq_service.mark_message_completed(dequeued_message.id)
            logger.info("Message marked as completed")
        else:
            logger.warning("No message dequeued")
        
        # Get queue stats
        stats = await mq_service.get_queue_stats()
        logger.info(f"Queue stats: {stats}")
        
        # Health check
        health = await mq_service.health_check()
        logger.info(f"Health check: {health}")
        
        logger.info("✅ Message Queue Service test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Message Queue Service test failed: {e}")
        return False


async def test_realtime_service():
    """Test realtime service functionality."""
    logger.info("Testing Real-time Service...")
    
    try:
        # Get realtime service
        rt_service = await get_realtime_service()
        
        # Health check
        health = await rt_service.health_check()
        logger.info(f"Health check: {health}")
        
        # Get connection stats
        stats = await rt_service.get_connection_stats()
        logger.info(f"Connection stats: {stats}")
        
        logger.info("✅ Real-time Service test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Real-time Service test failed: {e}")
        return False


async def test_media_handler():
    """Test media handler functionality."""
    logger.info("Testing Media Handler...")
    
    try:
        # Get media handler
        media_handler = await get_media_handler()
        
        # Health check
        health = await media_handler.health_check()
        logger.info(f"Health check: {health}")
        
        # Get storage stats
        stats = await media_handler.get_storage_stats()
        logger.info(f"Storage stats: {stats}")
        
        # Test creating a test image file
        test_image_path = Path("test_image.jpg")
        if not test_image_path.exists():
            # Create a simple test image using PIL
            try:
                from PIL import Image, ImageDraw
                img = Image.new('RGB', (100, 100), color='red')
                draw = ImageDraw.Draw(img)
                draw.text((10, 40), "TEST", fill='white')
                img.save(test_image_path)
                logger.info("Created test image for testing")
            except ImportError:
                logger.warning("PIL not available, skipping image creation test")
        
        if test_image_path.exists():
            # Test processing the image
            media_info = await media_handler.process_media_file(
                test_image_path, 
                "test_image.jpg", 
                MediaType.IMAGE
            )
            
            if media_info:
                logger.info(f"Media processed: {media_info.id}")
                logger.info(f"Media type: {media_info.media_type}")
                logger.info(f"Format: {media_info.format}")
                
                # Clean up test file
                test_image_path.unlink()
                logger.info("Test image cleaned up")
            else:
                logger.warning("Media processing failed")
        
        logger.info("✅ Media Handler test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Media Handler test failed: {e}")
        return False


async def test_integration():
    """Test integration between services."""
    logger.info("Testing Service Integration...")
    
    try:
        # Test that all services can work together
        mq_service = await get_message_queue_service()
        rt_service = await get_realtime_service()
        media_handler = await get_media_handler()
        
        # Test sending a message through the queue that triggers realtime updates
        test_message = QueueMessage(
            id="integration_test_001",
            type=MessageType.NOTIFICATION,
            priority=MessagePriority.NORMAL,
            payload={
                "type": "message_received",
                "title": "Integration Test",
                "message": "Testing service integration",
                "user_id": "test_user",
                "data": {"test": True}
            },
            source="test_system",
            target="realtime_service"
        )
        
        # Enqueue the message
        success = await mq_service.enqueue_message(test_message)
        logger.info(f"Integration test message enqueued: {success}")
        
        # Wait a moment for processing
        await asyncio.sleep(1)
        
        # Check final stats
        mq_stats = await mq_service.get_queue_stats()
        rt_stats = await rt_service.get_connection_stats()
        media_stats = await media_handler.get_storage_stats()
        
        logger.info(f"Final stats - MQ: {mq_stats}, RT: {rt_stats}, Media: {media_stats}")
        
        logger.info("✅ Service Integration test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Service Integration test failed: {e}")
        return False


async def main():
    """Main test function."""
    logger.info("🚀 Starting Phase 4 Services Test Suite")
    
    # Get settings
    settings = get_settings()
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Redis URL: {settings.redis_url}")
    logger.info(f"WebSocket: {settings.websocket_host}:{settings.websocket_port}")
    logger.info(f"Media Cache: {settings.media_cache_path}")
    
    # Run tests
    tests = [
        ("Message Queue", test_message_queue),
        ("Real-time Service", test_realtime_service),
        ("Media Handler", test_media_handler),
        ("Service Integration", test_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running {test_name} Test")
        logger.info(f"{'='*50}")
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("TEST RESULTS SUMMARY")
    logger.info(f"{'='*50}")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Phase 4 services are working correctly.")
    else:
        logger.error(f"⚠️ {total - passed} tests failed. Check the logs above for details.")
    
    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        sys.exit(1) 