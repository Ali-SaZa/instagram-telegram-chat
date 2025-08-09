"""
Webhook handler service for Instagram-Telegram chat integration.
"""

import asyncio
import logging
import hashlib
import hmac
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from urllib.parse import parse_qs, urlparse
import aiohttp
from aiohttp import web, ClientSession
from aiohttp.web import Request, Response, StreamResponse

from config.settings import get_settings
from database.connection import get_collection
from database.models import InstagramMessage, InstagramUser, InstagramThread, SyncStatus
from .data_processor import get_data_processor
from .sync_service import get_sync_service

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles Instagram webhook events and processes them."""
    
    def __init__(self):
        self.settings = get_settings()
        self.data_processor = None
        self.sync_service = None
        self.event_handlers: Dict[str, Callable] = {}
        self._setup_event_handlers()
        
    async def initialize(self):
        """Initialize webhook handler dependencies."""
        self.data_processor = await get_data_processor()
        self.sync_service = await get_sync_service()
        logger.info("Webhook handler initialized")
    
    def _setup_event_handlers(self):
        """Set up event handlers for different webhook events."""
        self.event_handlers = {
            'message': self._handle_message_event,
            'user': self._handle_user_event,
            'thread': self._handle_thread_event,
            'sync': self._handle_sync_event,
            'error': self._handle_error_event
        }
    
    async def handle_webhook(self, request: Request) -> Response:
        """Main webhook endpoint handler."""
        try:
            # Verify webhook signature if configured
            if not await self._verify_webhook_signature(request):
                logger.warning("Webhook signature verification failed")
                return web.Response(status=401, text="Unauthorized")
            
            # Parse webhook data
            webhook_data = await self._parse_webhook_data(request)
            if not webhook_data:
                return web.Response(status=400, text="Invalid webhook data")
            
            # Process webhook event
            await self._process_webhook_event(webhook_data)
            
            # Return success response
            return web.Response(status=200, text="OK")
            
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            return web.Response(status=500, text="Internal Server Error")
    
    async def _verify_webhook_signature(self, request: Request) -> bool:
        """Verify webhook signature for security."""
        try:
            # Get signature from headers
            signature = request.headers.get('X-Hub-Signature-256')
            if not signature:
                logger.warning("No webhook signature found in headers")
                return False
            
            # Get request body
            body = await request.read()
            
            # Verify signature using Instagram app secret
            app_secret = self.settings.instagram.app_secret if hasattr(self.settings.instagram, 'app_secret') else None
            if not app_secret:
                logger.warning("Instagram app secret not configured, skipping signature verification")
                return True
            
            expected_signature = f"sha256={self._generate_signature(body, app_secret)}"
            
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("Webhook signature verification failed")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    def _generate_signature(self, payload: bytes, secret: str) -> str:
        """Generate HMAC signature for webhook verification."""
        return hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
    
    async def _parse_webhook_data(self, request: Request) -> Optional[Dict[str, Any]]:
        """Parse webhook data from request."""
        try:
            content_type = request.headers.get('Content-Type', '')
            
            if 'application/json' in content_type:
                data = await request.json()
            elif 'application/x-www-form-urlencoded' in content_type:
                form_data = await request.post()
                data = dict(form_data)
            else:
                # Try to parse as JSON anyway
                try:
                    data = await request.json()
                except:
                    # Try to parse as form data
                    form_data = await request.post()
                    data = dict(form_data)
            
            logger.debug(f"Parsed webhook data: {data}")
            return data
            
        except Exception as e:
            logger.error(f"Error parsing webhook data: {e}")
            return None
    
    async def _process_webhook_event(self, webhook_data: Dict[str, Any]):
        """Process webhook event data."""
        try:
            # Extract event type
            event_type = webhook_data.get('event_type', 'unknown')
            
            # Get event handler
            handler = self.event_handlers.get(event_type)
            if handler:
                await handler(webhook_data)
            else:
                logger.warning(f"No handler found for event type: {event_type}")
                await self._handle_unknown_event(webhook_data)
                
        except Exception as e:
            logger.error(f"Error processing webhook event: {e}")
            raise
    
    async def _handle_message_event(self, webhook_data: Dict[str, Any]):
        """Handle Instagram message events."""
        try:
            logger.info("Processing message event from webhook")
            
            # Extract message data
            message_data = webhook_data.get('message', {})
            if not message_data:
                logger.warning("No message data in webhook")
                return
            
            # Process message using data processor
            message = await self.data_processor.process_instagram_message(message_data)
            
            # Store message in database
            await self._store_message(message)
            
            # Trigger sync if needed
            if self.sync_service:
                await self.sync_service.trigger_message_sync(message.thread_id)
            
            # Notify Telegram users about new message
            await self._notify_telegram_users(message)
            
            logger.info(f"Successfully processed message event: {message.message_id}")
            
        except Exception as e:
            logger.error(f"Error handling message event: {e}")
            raise
    
    async def _handle_user_event(self, webhook_data: Dict[str, Any]):
        """Handle Instagram user events."""
        try:
            logger.info("Processing user event from webhook")
            
            # Extract user data
            user_data = webhook_data.get('user', {})
            if not user_data:
                logger.warning("No user data in webhook")
                return
            
            # Process user using data processor
            user = await self.data_processor.process_instagram_user(user_data)
            
            # Store user in database
            await self._store_user(user)
            
            logger.info(f"Successfully processed user event: {user.username}")
            
        except Exception as e:
            logger.error(f"Error handling user event: {e}")
            raise
    
    async def _handle_thread_event(self, webhook_data: Dict[str, Any]):
        """Handle Instagram thread events."""
        try:
            logger.info("Processing thread event from webhook")
            
            # Extract thread data
            thread_data = webhook_data.get('thread', {})
            if not thread_data:
                logger.warning("No thread data in webhook")
                return
            
            # Process thread using data processor
            thread = await self.data_processor.process_instagram_thread(thread_data)
            
            # Store thread in database
            await self._store_thread(thread)
            
            logger.info(f"Successfully processed thread event: {thread.thread_id}")
            
        except Exception as e:
            logger.error(f"Error handling thread event: {e}")
            raise
    
    async def _handle_sync_event(self, webhook_data: Dict[str, Any]):
        """Handle sync-related events."""
        try:
            logger.info("Processing sync event from webhook")
            
            # Extract sync data
            sync_data = webhook_data.get('sync', {})
            if not sync_data:
                logger.warning("No sync data in webhook")
                return
            
            # Update sync status
            await self._update_sync_status(sync_data)
            
            logger.info("Successfully processed sync event")
            
        except Exception as e:
            logger.error(f"Error handling sync event: {e}")
            raise
    
    async def _handle_error_event(self, webhook_data: Dict[str, Any]):
        """Handle error events."""
        try:
            logger.warning("Processing error event from webhook")
            
            error_data = webhook_data.get('error', {})
            if error_data:
                logger.error(f"Instagram webhook error: {error_data}")
            
            # Log error for monitoring
            await self._log_webhook_error(webhook_data)
            
        except Exception as e:
            logger.error(f"Error handling error event: {e}")
    
    async def _handle_unknown_event(self, webhook_data: Dict[str, Any]):
        """Handle unknown event types."""
        logger.info(f"Handling unknown webhook event: {webhook_data}")
        
        # Store unknown event for analysis
        await self._store_unknown_event(webhook_data)
    
    async def _store_message(self, message: InstagramMessage):
        """Store Instagram message in database."""
        try:
            collection = await get_collection('instagram_messages')
            
            # Check if message already exists
            existing = await collection.find_one({'message_id': message.message_id})
            if existing:
                logger.debug(f"Message {message.message_id} already exists, updating")
                await collection.update_one(
                    {'message_id': message.message_id},
                    {'$set': message.dict(exclude={'id'})}
                )
            else:
                logger.debug(f"Storing new message {message.message_id}")
                await collection.insert_one(message.dict(exclude={'id'}))
                
        except Exception as e:
            logger.error(f"Error storing message: {e}")
            raise
    
    async def _store_user(self, user: InstagramUser):
        """Store Instagram user in database."""
        try:
            collection = await get_collection('instagram_users')
            
            # Check if user already exists
            existing = await collection.find_one({'instagram_id': user.instagram_id})
            if existing:
                logger.debug(f"User {user.username} already exists, updating")
                await collection.update_one(
                    {'instagram_id': user.instagram_id},
                    {'$set': user.dict(exclude={'id'})}
                )
            else:
                logger.debug(f"Storing new user {user.username}")
                await collection.insert_one(user.dict(exclude={'id'}))
                
        except Exception as e:
            logger.error(f"Error storing user: {e}")
            raise
    
    async def _store_thread(self, thread: InstagramThread):
        """Store Instagram thread in database."""
        try:
            collection = await get_collection('instagram_threads')
            
            # Check if thread already exists
            existing = await collection.find_one({'thread_id': thread.thread_id})
            if existing:
                logger.debug(f"Thread {thread.thread_id} already exists, updating")
                await collection.update_one(
                    {'thread_id': thread.thread_id},
                    {'$set': thread.dict(exclude={'id'})}
                )
            else:
                logger.debug(f"Storing new thread {thread.thread_id}")
                await collection.insert_one(thread.dict(exclude={'id'}))
                
        except Exception as e:
            logger.error(f"Error storing thread: {e}")
            raise
    
    async def _update_sync_status(self, sync_data: Dict[str, Any]):
        """Update sync status in database."""
        try:
            collection = await get_collection('sync_status')
            
            operation_id = sync_data.get('operation_id')
            if not operation_id:
                logger.warning("No operation ID in sync data")
                return
            
            # Update sync status
            await collection.update_one(
                {'operation_id': operation_id},
                {'$set': sync_data},
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error updating sync status: {e}")
            raise
    
    async def _notify_telegram_users(self, message: InstagramMessage):
        """Notify Telegram users about new Instagram message."""
        try:
            # Get thread participants
            thread_collection = await get_collection('instagram_threads')
            thread = await thread_collection.find_one({'thread_id': message.thread_id})
            
            if not thread:
                logger.warning(f"Thread {message.thread_id} not found")
                return
            
            # Get Telegram users linked to this thread
            chat_collection = await get_collection('chat_sessions')
            chat_sessions = await chat_collection.find({
                'active_thread_id': message.thread_id,
                'is_active': True
            }).to_list(None)
            
            if not chat_sessions:
                logger.debug(f"No active Telegram sessions for thread {message.thread_id}")
                return
            
            # Send notifications to Telegram users
            for session in chat_sessions:
                await self._send_telegram_notification(session, message)
                
        except Exception as e:
            logger.error(f"Error notifying Telegram users: {e}")
    
    async def _send_telegram_notification(self, session: Dict[str, Any], message: InstagramMessage):
        """Send notification to specific Telegram user."""
        try:
            # Get sender user info
            user_collection = await get_collection('instagram_users')
            sender = await user_collection.find_one({'instagram_id': message.sender_id})
            
            if not sender:
                logger.warning(f"Sender user {message.sender_id} not found")
                return
            
            # Format message for Telegram
            formatted_message = await self.data_processor.format_message_for_telegram(message, sender)
            
            # TODO: Implement actual Telegram notification sending
            # This would integrate with the Telegram bot service
            logger.info(f"Would send notification to Telegram user {session['telegram_user_id']}: {formatted_message[:100]}...")
            
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
    
    async def _log_webhook_error(self, webhook_data: Dict[str, Any]):
        """Log webhook error for monitoring."""
        try:
            error_collection = await get_collection('webhook_errors')
            
            error_log = {
                'timestamp': datetime.utcnow(),
                'webhook_data': webhook_data,
                'error_type': webhook_data.get('error', {}).get('type', 'unknown'),
                'error_message': webhook_data.get('error', {}).get('message', ''),
                'processed': False
            }
            
            await error_collection.insert_one(error_log)
            
        except Exception as e:
            logger.error(f"Error logging webhook error: {e}")
    
    async def _store_unknown_event(self, webhook_data: Dict[str, Any]):
        """Store unknown webhook events for analysis."""
        try:
            unknown_collection = await get_collection('unknown_webhook_events')
            
            event_log = {
                'timestamp': datetime.utcnow(),
                'webhook_data': webhook_data,
                'event_type': webhook_data.get('event_type', 'unknown'),
                'analyzed': False
            }
            
            await unknown_collection.insert_one(event_log)
            
        except Exception as e:
            logger.error(f"Error storing unknown event: {e}")
    
    async def get_webhook_stats(self) -> Dict[str, Any]:
        """Get webhook processing statistics."""
        try:
            stats = {}
            
            # Get message count
            message_collection = await get_collection('instagram_messages')
            stats['total_messages'] = await message_collection.count_documents({})
            
            # Get user count
            user_collection = await get_collection('instagram_users')
            stats['total_users'] = await user_collection.count_documents({})
            
            # Get thread count
            thread_collection = await get_collection('instagram_threads')
            stats['total_threads'] = await thread_collection.count_documents({})
            
            # Get error count
            error_collection = await get_collection('webhook_errors')
            stats['total_errors'] = await error_collection.count_documents({})
            
            # Get recent activity
            recent_messages = await message_collection.find().sort('created_at', -1).limit(10).to_list(10)
            stats['recent_messages'] = [
                {
                    'id': msg['message_id'],
                    'content': msg['content'][:100] + '...' if len(msg['content']) > 100 else msg['content'],
                    'timestamp': msg['created_at']
                }
                for msg in recent_messages
            ]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting webhook stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform webhook handler health check."""
        try:
            return {
                "status": "healthy",
                "event_handlers": list(self.event_handlers.keys()),
                "initialized": self.data_processor is not None and self.sync_service is not None,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }


# Global webhook handler instance
webhook_handler = WebhookHandler()


async def get_webhook_handler() -> WebhookHandler:
    """Get the global webhook handler instance."""
    if not webhook_handler.data_processor:
        await webhook_handler.initialize()
    return webhook_handler


async def handle_webhook_request(request: Request) -> Response:
    """Handle webhook request (for use with aiohttp web framework)."""
    handler = await get_webhook_handler()
    return await handler.handle_webhook(request)


async def get_webhook_stats():
    """Get webhook processing statistics."""
    handler = await get_webhook_handler()
    return await handler.get_webhook_stats()


async def health_check():
    """Perform webhook handler health check."""
    handler = await get_webhook_handler()
    return await handler.health_check() 