#!/usr/bin/env python3
"""
Basic functionality test script for Instagram-Telegram chat integration.
This script tests the core components without requiring external services.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.settings import get_settings
from database.connection import initialize_database, cleanup_database
from database.models import InstagramUser, InstagramMessage, InstagramThread
from database.operations import InstagramOperations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/test.log')
    ]
)

logger = logging.getLogger(__name__)


async def test_configuration():
    """Test configuration loading."""
    try:
        logger.info("Testing configuration...")
        settings = get_settings()
        
        # Check required settings
        required_settings = [
            'mongodb_uri',
            'mongodb_database',
            'instagram_username',
            'instagram_password',
            'telegram_bot_token'
        ]
        
        for setting in required_settings:
            if hasattr(settings, setting):
                value = getattr(settings, setting)
                if value:
                    logger.info(f"✓ {setting}: {value[:10]}..." if len(str(value)) > 10 else f"✓ {setting}: {value}")
                else:
                    logger.warning(f"⚠ {setting}: Not set")
            else:
                logger.error(f"✗ {setting}: Missing from settings")
        
        logger.info("Configuration test completed")
        return True
        
    except Exception as e:
        logger.error(f"Configuration test failed: {e}")
        return False


async def test_database_connection():
    """Test database connection."""
    try:
        logger.info("Testing database connection...")
        
        # Initialize database
        await initialize_database()
        logger.info("✓ Database connection established")
        
        # Test basic operations
        db_ops = InstagramOperations()
        connection_test = await db_ops.test_connection()
        
        if connection_test:
            logger.info("✓ Database operations test passed")
        else:
            logger.error("✗ Database operations test failed")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False
    finally:
        # Cleanup
        await cleanup_database()


async def test_models():
    """Test data models."""
    try:
        logger.info("Testing data models...")
        
        # Test InstagramUser model
        user_data = {
            "user_id": "test_user_123",
            "username": "testuser",
            "full_name": "Test User",
            "profile_pic_url": "https://example.com/pic.jpg",
            "is_private": False,
            "is_verified": False,
            "follower_count": 100,
            "following_count": 50
        }
        
        user = InstagramUser(**user_data)
        logger.info(f"✓ InstagramUser model: {user.username}")
        
        # Test InstagramThread model
        thread_data = {
            "thread_id": "test_thread_456",
            "title": "Test Thread",
            "users": ["test_user_123"],
            "thread_type": "direct",
            "is_group": False,
            "last_activity": "2024-01-01T00:00:00Z"
        }
        
        thread = InstagramThread(**thread_data)
        logger.info(f"✓ InstagramThread model: {thread.title}")
        
        # Test InstagramMessage model
        message_data = {
            "message_id": "test_msg_789",
            "thread_id": "test_thread_456",
            "user_id": "test_user_123",
            "text": "Hello, this is a test message!",
            "timestamp": "2024-01-01T00:00:00Z",
            "item_type": "text",
            "media_url": None,
            "media_type": None
        }
        
        message = InstagramMessage(**message_data)
        logger.info(f"✓ InstagramMessage model: {message.text[:30]}...")
        
        logger.info("Data models test completed")
        return True
        
    except Exception as e:
        logger.error(f"Data models test failed: {e}")
        return False


async def test_telegram_bot_setup():
    """Test Telegram bot setup (without actually starting the bot)."""
    try:
        logger.info("Testing Telegram bot setup...")
        
        # Import bot components
        from telegram.bot import InstagramTelegramBot
        from telegram.session import TelegramSessionManager
        
        # Test session manager
        session_manager = TelegramSessionManager()
        await session_manager.initialize()
        logger.info("✓ TelegramSessionManager initialized")
        
        # Test bot class creation
        bot = InstagramTelegramBot()
        logger.info("✓ InstagramTelegramBot created")
        
        logger.info("Telegram bot setup test completed")
        return True
        
    except Exception as e:
        logger.error(f"Telegram bot setup test failed: {e}")
        return False


async def main():
    """Run all tests."""
    logger.info("Starting basic functionality tests...")
    
    tests = [
        ("Configuration", test_configuration),
        ("Data Models", test_models),
        ("Database Connection", test_database_connection),
        ("Telegram Bot Setup", test_telegram_bot_setup),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running {test_name} test...")
        logger.info('='*50)
        
        try:
            result = await test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✓ {test_name} test PASSED")
            else:
                logger.error(f"✗ {test_name} test FAILED")
                
        except Exception as e:
            logger.error(f"✗ {test_name} test ERROR: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("TEST SUMMARY")
    logger.info('='*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! The system is ready for basic operation.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the logs and fix the issues.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1) 