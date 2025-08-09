"""
Chat handlers for managing active chat sessions and message threading.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from ..database.operations import InstagramOperations
from .session import UserSession

logger = logging.getLogger(__name__)


class ChatHandler:
    """Handles active chat sessions and message threading."""
    
    def __init__(self):
        """Initialize the chat handler."""
        self.db_ops = InstagramOperations()
        self.active_chats: Dict[int, Dict[str, Any]] = {}
    
    async def start_chat_session(self, user_id: int, thread_id: str, session: UserSession) -> Dict[str, Any]:
        """
        Start a new chat session for a user.
        
        Args:
            user_id: Telegram user ID
            thread_id: Instagram thread ID
            session: User session object
            
        Returns:
            Dict containing chat session info
        """
        try:
            # Get thread information
            thread = await self.db_ops.get_thread(thread_id)
            if not thread:
                return {"error": "Thread not found"}
            
            # Get recent messages
            messages = await self.db_ops.get_thread_messages(thread_id, limit=20)
            
            # Create chat session
            chat_session = {
                "user_id": user_id,
                "thread_id": thread_id,
                "thread_title": thread.get("title", "Untitled"),
                "started_at": datetime.now(),
                "last_activity": datetime.now(),
                "messages": messages,
                "current_page": 1,
                "is_active": True
            }
            
            # Store in active chats
            self.active_chats[user_id] = chat_session
            
            # Update user session
            session.set_current_thread(thread_id)
            
            logger.info(f"Started chat session for user {user_id} in thread {thread_id}")
            return chat_session
            
        except Exception as e:
            logger.error(f"Error starting chat session: {e}")
            return {"error": f"Failed to start chat session: {str(e)}"}
    
    async def end_chat_session(self, user_id: int, session: UserSession) -> bool:
        """
        End an active chat session.
        
        Args:
            user_id: Telegram user ID
            session: User session object
            
        Returns:
            bool: True if successful
        """
        try:
            if user_id in self.active_chats:
                del self.active_chats[user_id]
                session.clear_session()
                logger.info(f"Ended chat session for user {user_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error ending chat session: {e}")
            return False
    
    async def send_message_to_instagram(self, user_id: int, message_text: str, session: UserSession) -> Dict[str, Any]:
        """
        Send a message to Instagram through the active chat session.
        
        Args:
            user_id: Telegram user ID
            message_text: Message text to send
            session: User session object
            
        Returns:
            Dict containing result info
        """
        try:
            if user_id not in self.active_chats:
                return {"error": "No active chat session"}
            
            chat_session = self.active_chats[user_id]
            thread_id = chat_session["thread_id"]
            
            # Create message data
            message_data = {
                "thread_id": thread_id,
                "user_id": user_id,  # This should be the Instagram user ID
                "text": message_text,
                "timestamp": datetime.now(),
                "item_type": "text",
                "is_from_telegram": True
            }
            
            # Store message in database
            message_id = await self.db_ops.create_message(message_data)
            if not message_id:
                return {"error": "Failed to store message"}
            
            # Update chat session
            chat_session["last_activity"] = datetime.now()
            chat_session["messages"].insert(0, {
                "id": message_id,
                "text": message_text,
                "timestamp": datetime.now(),
                "is_from_telegram": True
            })
            
            # Update user session
            session.update_activity()
            
            logger.info(f"Message sent to Instagram thread {thread_id} by user {user_id}")
            return {"success": True, "message_id": message_id}
            
        except Exception as e:
            logger.error(f"Error sending message to Instagram: {e}")
            return {"error": f"Failed to send message: {str(e)}"}
    
    async def get_chat_history(self, user_id: int, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """
        Get chat history for the active session.
        
        Args:
            user_id: Telegram user ID
            page: Page number for pagination
            limit: Number of messages per page
            
        Returns:
            Dict containing chat history
        """
        try:
            if user_id not in self.active_chats:
                return {"error": "No active chat session"}
            
            chat_session = self.active_chats[user_id]
            thread_id = chat_session["thread_id"]
            
            # Calculate offset
            offset = (page - 1) * limit
            
            # Get messages from database
            messages = await self.db_ops.get_thread_messages(thread_id, limit=limit, offset=offset)
            
            # Update chat session
            chat_session["current_page"] = page
            chat_session["last_activity"] = datetime.now()
            
            return {
                "messages": messages,
                "current_page": page,
                "has_next": len(messages) == limit,
                "has_previous": page > 1
            }
            
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return {"error": f"Failed to get chat history: {str(e)}"}
    
    async def search_in_chat(self, user_id: int, query: str, limit: int = 20) -> Dict[str, Any]:
        """
        Search for messages in the active chat session.
        
        Args:
            user_id: Telegram user ID
            query: Search query
            limit: Maximum number of results
            
        Returns:
            Dict containing search results
        """
        try:
            if user_id not in self.active_chats:
                return {"error": "No active chat session"}
            
            chat_session = self.active_chats[user_id]
            thread_id = chat_session["thread_id"]
            
            # Search messages in the thread
            results = await self.db_ops.search_messages(query, thread_id=thread_id, limit=limit)
            
            # Update chat session
            chat_session["last_activity"] = datetime.now()
            
            return {
                "results": results,
                "query": query,
                "count": len(results)
            }
            
        except Exception as e:
            logger.error(f"Error searching in chat: {e}")
            return {"error": f"Failed to search: {str(e)}"}
    
    async def get_active_chat_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get information about the active chat session.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Dict containing chat session info or None
        """
        if user_id in self.active_chats:
            chat_session = self.active_chats[user_id].copy()
            # Remove sensitive data
            chat_session.pop("messages", None)
            return chat_session
        return None
    
    async def get_all_active_chats(self) -> List[Dict[str, Any]]:
        """
        Get all active chat sessions.
        
        Returns:
            List of active chat sessions
        """
        active_chats = []
        for user_id, chat_session in self.active_chats.items():
            if chat_session["is_active"]:
                chat_info = chat_session.copy()
                chat_info.pop("messages", None)
                active_chats.append(chat_info)
        return active_chats
    
    async def cleanup_inactive_chats(self, max_inactive_hours: int = 24) -> int:
        """
        Clean up inactive chat sessions.
        
        Args:
            max_inactive_hours: Maximum hours of inactivity
            
        Returns:
            int: Number of sessions cleaned up
        """
        try:
            current_time = datetime.now()
            inactive_users = []
            
            for user_id, chat_session in self.active_chats.items():
                last_activity = chat_session["last_activity"]
                if isinstance(last_activity, str):
                    last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                
                inactive_time = current_time - last_activity
                if inactive_time.total_seconds() > (max_inactive_hours * 3600):
                    inactive_users.append(user_id)
            
            # Remove inactive sessions
            for user_id in inactive_users:
                del self.active_chats[user_id]
            
            logger.info(f"Cleaned up {len(inactive_users)} inactive chat sessions")
            return len(inactive_users)
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive chats: {e}")
            return 0
    
    def get_chat_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about active chat sessions.
        
        Returns:
            Dict containing chat statistics
        """
        try:
            total_sessions = len(self.active_chats)
            active_sessions = sum(1 for chat in self.active_chats.values() if chat["is_active"])
            
            # Calculate average session duration
            total_duration = 0
            for chat in self.active_chats.values():
                if chat["started_at"] and chat["last_activity"]:
                    started = chat["started_at"]
                    last_activity = chat["last_activity"]
                    
                    if isinstance(started, str):
                        started = datetime.fromisoformat(started.replace('Z', '+00:00'))
                    if isinstance(last_activity, str):
                        last_activity = datetime.fromisoformat(last_activity.replace('Z', '+00:00'))
                    
                    duration = (last_activity - started).total_seconds()
                    total_duration += duration
            
            avg_duration = total_duration / total_sessions if total_sessions > 0 else 0
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "inactive_sessions": total_sessions - active_sessions,
                "average_session_duration_seconds": avg_duration,
                "average_session_duration_minutes": avg_duration / 60 if avg_duration > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting chat statistics: {e}")
            return {"error": str(e)} 