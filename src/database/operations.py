"""
Database operations for Instagram chat data.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bson import ObjectId

from .connection import get_mongodb_manager
from .models import (
    InstagramUser, InstagramMessage, InstagramThread, 
    ChatSession, SyncStatus
)

logger = logging.getLogger(__name__)


class InstagramUserOperations:
    """Operations for Instagram users."""
    
    @staticmethod
    async def create_user(user_data: InstagramUser) -> Optional[str]:
        """
        Create a new Instagram user.
        
        Args:
            user_data: User data to create
            
        Returns:
            str: User ID if successful, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_users")
            
            # Check if user already exists
            existing_user = await collection.find_one(
                {"instagram_id": user_data.instagram_id}
            )
            
            if existing_user:
                logger.info(f"User {user_data.username} already exists, updating...")
                # Update existing user
                result = await collection.update_one(
                    {"instagram_id": user_data.instagram_id},
                    {
                        "$set": {
                            "username": user_data.username,
                            "full_name": user_data.full_name,
                            "profile_picture": user_data.profile_picture,
                            "is_private": user_data.is_private,
                            "is_verified": user_data.is_verified,
                            "followers_count": user_data.followers_count,
                            "following_count": user_data.following_count,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                return str(existing_user["_id"])
            else:
                # Create new user
                user_dict = user_data.dict(by_alias=True)
                user_dict["created_at"] = datetime.now(timezone.utc)
                user_dict["updated_at"] = datetime.now(timezone.utc)
                
                result = await collection.insert_one(user_dict)
                logger.info(f"Created new user: {user_data.username}")
                return str(result.inserted_id)
                
        except Exception as e:
            logger.error(f"Error creating user {user_data.username}: {e}")
            return None
    
    @staticmethod
    async def get_user_by_instagram_id(instagram_user_id: str) -> Optional[InstagramUser]:
        """
        Get user by Instagram user ID.
        
        Args:
            instagram_user_id: Instagram user ID
            
        Returns:
            InstagramUser: User data if found, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_users")
            
            user_data = await collection.find_one({"instagram_id": instagram_user_id})
            
            if user_data:
                return InstagramUser(**user_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting user {instagram_user_id}: {e}")
            return None
    
    @staticmethod
    async def get_user_by_username(username: str) -> Optional[InstagramUser]:
        """
        Get user by username.
        
        Args:
            username: Instagram username
            
        Returns:
            InstagramUser: User data if found, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_users")
            
            user_data = await collection.find_one({"username": username})
            
            if user_data:
                return InstagramUser(**user_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting user by username {username}: {e}")
            return None


class InstagramMessageOperations:
    """Operations for Instagram messages."""
    
    @staticmethod
    async def create_message(message_data: InstagramMessage) -> Optional[str]:
        """
        Create a new message.
        
        Args:
            message_data: Message data to create
            
        Returns:
            str: Message ID if successful, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_messages")
            
            # Check if message already exists
            existing_message = await collection.find_one(
                {"message_id": message_data.message_id}
            )
            
            if existing_message:
                logger.debug(f"Message {message_data.message_id} already exists, skipping...")
                return str(existing_message["_id"])
            
            # Create new message
            message_dict = message_data.dict(by_alias=True)
            message_dict["created_at"] = datetime.now(timezone.utc)
            
            result = await collection.insert_one(message_dict)
            logger.debug(f"Created new message: {message_data.message_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating message {message_data.message_id}: {e}")
            return None
    
    @staticmethod
    async def get_messages_by_thread(
        thread_id: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[InstagramMessage]:
        """
        Get messages from a specific thread.
        
        Args:
            thread_id: Thread ID
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            
        Returns:
            List[InstagramMessage]: List of messages
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_messages")
            
            cursor = collection.find({"thread_id": thread_id}) \
                .sort("created_at", -1) \
                .skip(offset) \
                .limit(limit)
            
            messages = []
            async for message_data in cursor:
                messages.append(InstagramMessage(**message_data))
            
            # Return in chronological order (oldest first)
            messages.reverse()
            return messages
            
        except Exception as e:
            logger.error(f"Error getting messages for thread {thread_id}: {e}")
            return []
    
    @staticmethod
    async def get_latest_messages_by_user(
        instagram_user_id: str, 
        limit: int = 20
    ) -> List[InstagramMessage]:
        """
        Get latest messages from a specific user.
        
        Args:
            instagram_user_id: Instagram user ID
            limit: Maximum number of messages to return
            
        Returns:
            List[InstagramMessage]: List of messages
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_messages")
            
            cursor = collection.find({"sender_id": instagram_user_id}) \
                .sort("created_at", -1) \
                .limit(limit)
            
            messages = []
            async for message_data in cursor:
                messages.append(InstagramMessage(**message_data))
            
            # Return in chronological order (oldest first)
            messages.reverse()
            return messages
            
        except Exception as e:
            logger.error(f"Error getting messages for user {instagram_user_id}: {e}")
            return []
    
    @staticmethod
    async def search_messages(
        query: str, 
        thread_id: Optional[str] = None,
        limit: int = 50
    ) -> List[InstagramMessage]:
        """
        Search messages by text content.
        
        Args:
            query: Search query
            thread_id: Optional thread ID to limit search
            limit: Maximum number of results
            
        Returns:
            List[InstagramMessage]: List of matching messages
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_messages")
            
            # Build search filter
            search_filter = {
                "content": {"$regex": query, "$options": "i"}  # Case-insensitive search
            }
            
            if thread_id:
                search_filter["thread_id"] = thread_id
            
            cursor = collection.find(search_filter) \
                .sort("created_at", -1) \
                .limit(limit)
            
            messages = []
            async for message_data in cursor:
                messages.append(InstagramMessage(**message_data))
            
            return messages
            
        except Exception as e:
            logger.error(f"Error searching messages with query '{query}': {e}")
            return []
    
    @staticmethod
    async def get_message_by_id(message_id: str) -> Optional[InstagramMessage]:
        """
        Get message by ID.
        
        Args:
            message_id: Message ID
            
        Returns:
            InstagramMessage: Message data if found, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_messages")
            
            message_data = await collection.find_one({"message_id": message_id})
            
            if message_data:
                return InstagramMessage(**message_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            return None
    
    @staticmethod
    async def update_message(message_data: InstagramMessage) -> bool:
        """
        Update an existing message.
        
        Args:
            message_data: Message data to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_messages")
            
            # Check if message exists
            existing_message = await collection.find_one(
                {"message_id": message_data.message_id}
            )
            
            if not existing_message:
                logger.warning(f"Message {message_data.message_id} not found for update")
                return False
            
            # Update message
            message_dict = message_data.dict(by_alias=True)
            message_dict["updated_at"] = datetime.now(timezone.utc)
            
            result = await collection.update_one(
                {"message_id": message_data.message_id},
                {"$set": message_dict}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating message {message_data.message_id}: {e}")
            return False

    @staticmethod
    async def get_messages_since(since: datetime, limit: int = 100) -> List[InstagramMessage]:
        """
        Get messages since a specific time.
        
        Args:
            since: Start time for messages
            limit: Maximum number of messages to return
            
        Returns:
            List[InstagramMessage]: List of messages since the specified time
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_messages")
            
            cursor = collection.find({"created_at": {"$gte": since}}) \
                .sort("created_at", -1) \
                .limit(limit)
            
            messages = []
            async for message_data in cursor:
                messages.append(InstagramMessage(**message_data))
            
            # Return in chronological order (oldest first)
            messages.reverse()
            return messages
            
        except Exception as e:
            logger.error(f"Error getting messages since {since}: {e}")
            return []


class InstagramThreadOperations:
    """Operations for Instagram threads."""
    
    @staticmethod
    async def create_thread(thread_data: InstagramThread) -> Optional[str]:
        """
        Create a new thread.
        
        Args:
            thread_data: Thread data to create
            
        Returns:
            str: Thread ID if successful, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_threads")
            
            # Check if thread already exists
            existing_thread = await collection.find_one(
                {"thread_id": thread_data.thread_id}
            )
            
            if existing_thread:
                logger.info(f"Thread {thread_data.thread_id} already exists, updating...")
                # Update existing thread
                result = await collection.update_one(
                    {"thread_id": thread_data.thread_id},
                    {
                        "$set": {
                            "title": thread_data.title,
                            "participants": thread_data.participants,
                            "last_activity": thread_data.last_activity,
                            "message_count": thread_data.message_count,
                            "is_group": thread_data.is_group,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )
                return str(existing_thread["_id"])
            else:
                # Create new thread
                thread_dict = thread_data.dict(by_alias=True)
                thread_dict["created_at"] = datetime.now(timezone.utc)
                thread_dict["updated_at"] = datetime.now(timezone.utc)
                
                result = await collection.insert_one(thread_dict)
                logger.info(f"Created new thread: {thread_data.title}")
                return str(result.inserted_id)
                
        except Exception as e:
            logger.error(f"Error creating thread {thread_data.thread_id}: {e}")
            return None
    
    @staticmethod
    async def get_thread_by_id(thread_id: str) -> Optional[InstagramThread]:
        """
        Get thread by ID.
        
        Args:
            thread_id: Thread ID
            
        Returns:
            InstagramThread: Thread data if found, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_threads")
            
            thread_data = await collection.find_one({"thread_id": thread_id})
            
            if thread_data:
                return InstagramThread(**thread_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting thread {thread_id}: {e}")
            return None
    
    @staticmethod
    async def get_all_threads(limit: int = 100) -> List[InstagramThread]:
        """
        Get all threads ordered by last message.
        
        Args:
            limit: Maximum number of threads to return
            
        Returns:
            List[InstagramThread]: List of threads
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_threads")
            
            cursor = collection.find({}) \
                .sort("last_activity", -1) \
                .limit(limit)
            
            threads = []
            async for thread_data in cursor:
                threads.append(InstagramThread(**thread_data))
            
            return threads
            
        except Exception as e:
            logger.error(f"Error getting threads: {e}")
            return []
    
    @staticmethod
    async def update_thread_message_count(thread_id: str, new_count: int) -> bool:
        """
        Update thread message count.
        
        Args:
            thread_id: Thread ID
            new_count: New message count
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_threads")
            
            result = await collection.update_one(
                {"thread_id": thread_id},
                {
                    "$set": {
                        "message_count": new_count,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating thread {thread_id} message count: {e}")
            return False
    
    @staticmethod
    async def update_thread(thread_data: InstagramThread) -> bool:
        """
        Update an existing thread.
        
        Args:
            thread_data: Thread data to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_threads")
            
            # Check if thread exists
            existing_thread = await collection.find_one(
                {"thread_id": thread_data.thread_id}
            )
            
            if not existing_thread:
                logger.warning(f"Thread {thread_data.thread_id} not found for update")
                return False
            
            # Update thread
            thread_dict = thread_data.dict(by_alias=True)
            thread_dict["updated_at"] = datetime.now(timezone.utc)
            
            result = await collection.update_one(
                {"thread_id": thread_data.thread_id},
                {"$set": thread_dict}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Error updating thread {thread_data.thread_id}: {e}")
            return False


class ChatSessionOperations:
    """Operations for chat sessions."""
    
    @staticmethod
    async def create_or_update_session(
        telegram_user_id: int,
        instagram_user_id: str,
        thread_id: str
    ) -> Optional[str]:
        """
        Create or update a chat session.
        
        Args:
            telegram_user_id: Telegram user ID
            instagram_user_id: Instagram user ID
            thread_id: Thread ID
            
        Returns:
            str: Session ID if successful, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("chat_sessions")
            
            # Check if session exists
            existing_session = await collection.find_one({
                "telegram_user_id": telegram_user_id,
                "instagram_user_id": instagram_user_id
            })
            
            if existing_session:
                # Update existing session
                result = await collection.update_one(
                    {
                        "telegram_user_id": telegram_user_id,
                        "instagram_user_id": instagram_user_id
                    },
                    {
                        "$set": {
                            "active_thread_id": thread_id,
                            "last_activity": datetime.now(timezone.utc)
                        }
                    }
                )
                return str(existing_session["_id"])
            else:
                # Create new session
                session_data = ChatSession(
                    telegram_user_id=telegram_user_id,
                    instagram_user_id=instagram_user_id,
                    active_thread_id=thread_id
                )
                
                session_dict = session_data.dict(by_alias=True)
                result = await collection.insert_one(session_dict)
                logger.info(f"Created new chat session for user {telegram_user_id}")
                return str(result.inserted_id)
                
        except Exception as e:
            logger.error(f"Error creating/updating session: {e}")
            return None
    
    @staticmethod
    async def get_user_sessions(telegram_user_id: int) -> List[ChatSession]:
        """
        Get all sessions for a Telegram user.
        
        Args:
            telegram_user_id: Telegram user ID
            
        Returns:
            List[ChatSession]: List of sessions
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("chat_sessions")
            
            cursor = collection.find({"telegram_user_id": telegram_user_id}) \
                .sort("last_activity", -1)
            
            sessions = []
            async for session_data in cursor:
                sessions.append(ChatSession(**session_data))
            
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting sessions for user {telegram_user_id}: {e}")
            return []


class SyncStatusOperations:
    """Operations for sync status tracking."""
    
    @staticmethod
    async def create_sync_status(sync_data: SyncStatus) -> Optional[str]:
        """
        Create a new sync status record.
        
        Args:
            sync_data: Sync status data
            
        Returns:
            str: Sync status ID if successful, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("sync_status")
            
            sync_dict = sync_data.dict(by_alias=True)
            sync_dict["created_at"] = datetime.now(timezone.utc)
            
            result = await collection.insert_one(sync_dict)
            logger.info(f"Created sync status: {sync_data.status}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error creating sync status: {e}")
            return None
    
    @staticmethod
    async def get_latest_sync_status() -> Optional[SyncStatus]:
        """
        Get the latest sync status.
        
        Returns:
            SyncStatus: Latest sync status if found, None otherwise
        """
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("sync_status")
            
            sync_data = await collection.find_one(
                {},
                sort=[("created_at", -1)]
            )
            
            if sync_data:
                return SyncStatus(**sync_data)
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest sync status: {e}")
            return None 


class InstagramOperations:
    """Unified operations class that combines all Instagram-related operations."""
    
    def __init__(self):
        """Initialize the operations class."""
        self.user_ops = InstagramUserOperations()
        self.message_ops = InstagramMessageOperations()
        self.thread_ops = InstagramThreadOperations()
        self.session_ops = ChatSessionOperations()
        self.sync_ops = SyncStatusOperations()
    
    async def test_connection(self) -> bool:
        """
        Test the database connection.
        
        Returns:
            bool: True if connection successful
        """
        try:
            db = await get_mongodb_manager()
            await db.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    # User operations
    async def create_user(self, user_data: InstagramUser) -> Optional[str]:
        """Create a new Instagram user."""
        return await self.user_ops.create_user(user_data)
    
    async def get_user_info(self, user_id: str) -> Optional[InstagramUser]:
        """Get user information by Instagram user ID."""
        return await self.user_ops.get_user_by_instagram_id(user_id)
    
    async def get_user_by_username(self, username: str) -> Optional[InstagramUser]:
        """Get user information by username."""
        return await self.user_ops.get_user_by_username(username)
    
    # Message operations
    async def create_message(self, message_data: InstagramMessage) -> Optional[str]:
        """Create a new Instagram message."""
        return await self.message_ops.create_message(message_data)
    
    async def get_message(self, message_id: str) -> Optional[InstagramMessage]:
        """Get message by ID."""
        return await self.message_ops.get_message_by_id(message_id)
    
    async def update_message(self, message_data: Dict[str, Any]) -> bool:
        """Update an existing message."""
        try:
            # Convert dict to InstagramMessage model
            message = InstagramMessage(**message_data)
            return await self.message_ops.update_message(message)
        except Exception as e:
            logger.error(f"Error updating message: {e}")
            return False
    
    async def get_thread_messages(self, thread_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages for a specific thread."""
        try:
            messages = await self.message_ops.get_messages_by_thread(thread_id, limit)
            
            # Convert to dict format for easier handling
            message_dicts = []
            for msg in messages:
                msg_dict = msg.dict(by_alias=True)
                # Convert ObjectId to string
                msg_dict['_id'] = str(msg_dict['_id'])
                message_dicts.append(msg_dict)
            
            return message_dicts
        except Exception as e:
            logger.error(f"Error getting thread messages: {e}")
            return []
    
    async def search_messages(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search messages across all threads."""
        try:
            messages = await self.message_ops.search_messages(query, limit=limit)
            
            # Convert to dict format
            message_dicts = []
            for msg in messages:
                msg_dict = msg.dict(by_alias=True)
                msg_dict['_id'] = str(msg_dict['_id'])
                message_dicts.append(msg_dict)
            
            return message_dicts
        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            return []
    
    async def get_messages_since(self, since: datetime, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages since a specific time."""
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_messages")
            
            # Build query for messages since the specified time
            query = {"instagram_timestamp": {"$gte": since}}
            
            # Get messages with limit
            cursor = collection.find(query).sort("instagram_timestamp", -1).limit(limit)
            messages = await cursor.to_list(length=limit)
            
            # Convert to dict format
            message_dicts = []
            for msg in messages:
                msg['_id'] = str(msg['_id'])
                message_dicts.append(msg)
            
            return message_dicts
        except Exception as e:
            logger.error(f"Error getting messages since {since}: {e}")
            return []
    
    # Thread operations
    async def create_thread(self, thread_data: Dict[str, Any]) -> Optional[str]:
        """Create a new Instagram thread."""
        try:
            # Convert dict to InstagramThread model
            thread = InstagramThread(**thread_data)
            return await self.thread_ops.create_thread(thread)
        except Exception as e:
            logger.error(f"Error creating thread: {e}")
            return None
    
    async def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get thread by ID."""
        try:
            thread = await self.thread_ops.get_thread_by_id(thread_id)
            if thread:
                thread_dict = thread.dict(by_alias=True)
                thread_dict['_id'] = str(thread_dict['_id'])
                return thread_dict
            return None
        except Exception as e:
            logger.error(f"Error getting thread: {e}")
            return None
    
    async def update_thread(self, thread_data: Dict[str, Any]) -> bool:
        """Update an existing thread."""
        try:
            # Convert dict to InstagramThread model
            thread = InstagramThread(**thread_data)
            return await self.thread_ops.update_thread(thread)
        except Exception as e:
            logger.error(f"Error updating thread: {e}")
            return False
    
    async def get_all_threads(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all threads."""
        try:
            threads = await self.thread_ops.get_all_threads(limit)
            
            # Convert to dict format
            thread_dicts = []
            for thread in threads:
                thread_dict = thread.dict(by_alias=True)
                thread_dict['_id'] = str(thread_dict['_id'])
                thread_dicts.append(thread_dict)
            
            return thread_dicts
        except Exception as e:
            logger.error(f"Error getting all threads: {e}")
            return []
    
    # Utility operations
    async def get_thread_count(self) -> int:
        """Get total number of threads."""
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_threads")
            return await collection.count_documents({})
        except Exception as e:
            logger.error(f"Error getting thread count: {e}")
            return 0
    
    async def get_message_count(self) -> int:
        """Get total number of messages."""
        try:
            db = await get_mongodb_manager()
            collection = await db.get_collection("instagram_messages")
            return await collection.count_documents({})
        except Exception as e:
            logger.error(f"Error getting message count: {e}")
            return 0
    
    async def get_last_sync_time(self) -> Optional[datetime]:
        """Get the last sync time."""
        try:
            sync_status = await self.sync_ops.get_latest_sync_status()
            return sync_status.created_at if sync_status else None
        except Exception as e:
            logger.error(f"Error getting last sync time: {e}")
            return None 