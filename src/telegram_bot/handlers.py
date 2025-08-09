"""
Command handlers for the Telegram bot.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from database.operations import InstagramOperations

logger = logging.getLogger(__name__)


class CommandHandlers:
    """Handles bot commands and database operations."""
    
    def __init__(self):
        """Initialize the command handlers."""
        self.db_ops = InstagramOperations()
    
    async def get_threads(self) -> List[Dict[str, Any]]:
        """
        Get all Instagram threads.
        
        Returns:
            List of thread information
        """
        try:
            threads = await self.db_ops.get_all_threads()
            
            # Format threads for display
            formatted_threads = []
            for thread in threads:
                formatted_thread = {
                    'id': thread.get('thread_id'),
                    'title': thread.get('title', 'Untitled'),
                    'users': thread.get('users', []),
                    'last_activity': self._format_timestamp(thread.get('last_activity')),
                    'thread_type': thread.get('thread_type'),
                    'is_group': thread.get('is_group', False)
                }
                formatted_threads.append(formatted_thread)
            
            return formatted_threads
            
        except Exception as e:
            logger.error(f"Error getting threads: {e}")
            return []
    
    async def get_thread_messages(self, thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get messages for a specific thread.
        
        Args:
            thread_id: Thread ID
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message information
        """
        try:
            messages = await self.db_ops.get_thread_messages(thread_id, limit)
            
            # Format messages for display
            formatted_messages = []
            for msg in messages:
                # Get user info for the message
                user_info = await self.db_ops.get_user_info(msg.get('user_id'))
                
                formatted_message = {
                    'id': msg.get('message_id'),
                    'thread_id': msg.get('thread_id'),
                    'user_id': msg.get('user_id'),
                    'username': user_info.get('username', 'Unknown') if user_info else 'Unknown',
                    'text': msg.get('text', ''),
                    'timestamp': self._format_timestamp(msg.get('timestamp')),
                    'item_type': msg.get('item_type'),
                    'media_url': msg.get('media_url'),
                    'media_type': msg.get('media_type')
                }
                formatted_messages.append(formatted_message)
            
            # Sort by timestamp (newest first)
            formatted_messages.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return formatted_messages
            
        except Exception as e:
            logger.error(f"Error getting thread messages: {e}")
            return []
    
    async def search_messages(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search messages across all threads.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching messages
        """
        try:
            results = await self.db_ops.search_messages(query, limit)
            
            # Format search results for display
            formatted_results = []
            for result in results:
                # Get user and thread info
                user_info = await self.db_ops.get_user_info(result.get('user_id'))
                thread_info = await self.db_ops.get_thread(result.get('thread_id'))
                
                formatted_result = {
                    'id': result.get('message_id'),
                    'user_id': result.get('user_id'),
                    'username': user_info.get('username', 'Unknown') if user_info else 'Unknown',
                    'text': result.get('text', ''),
                    'timestamp': self._format_timestamp(result.get('timestamp')),
                    'thread_id': result.get('thread_id'),
                    'thread_title': thread_info.get('title', 'Unknown') if thread_info else 'Unknown'
                }
                formatted_results.append(formatted_result)
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            return []
    
    async def get_system_status(self) -> Dict[str, Any]:
        """
        Get system status information.
        
        Returns:
            Dictionary with status information
        """
        try:
            # Get database status
            db_status = await self.db_ops.test_connection()
            
            # Get counts
            thread_count = await self.db_ops.get_thread_count()
            message_count = await self.db_ops.get_message_count()
            
            # Get last sync time (this would come from Instagram monitor)
            last_sync = await self.db_ops.get_last_sync_time()
            
            status = {
                'instagram': 'Connected' if db_status else 'Disconnected',
                'database': 'Connected' if db_status else 'Disconnected',
                'last_sync': self._format_timestamp(last_sync) if last_sync else 'Never',
                'thread_count': thread_count,
                'message_count': message_count
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                'instagram': 'Unknown',
                'database': 'Unknown',
                'last_sync': 'Unknown',
                'thread_count': 'Unknown',
                'message_count': 'Unknown'
            }
    
    def _format_timestamp(self, timestamp) -> str:
        """
        Format timestamp for display.
        
        Args:
            timestamp: Timestamp to format
            
        Returns:
            Formatted timestamp string
        """
        if not timestamp:
            return 'Unknown'
        
        try:
            if isinstance(timestamp, str):
                # Parse ISO format string
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif isinstance(timestamp, datetime):
                dt = timestamp
            else:
                return 'Unknown'
            
            now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
            diff = now - dt
            
            if diff.days > 0:
                return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                return "Just now"
                
        except Exception as e:
            logger.error(f"Error formatting timestamp: {e}")
            return 'Unknown' 