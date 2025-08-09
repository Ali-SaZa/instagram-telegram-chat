"""
Instagram API client using instagrapi library.
Handles authentication, direct messages, and data synchronization.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Generator
from datetime import datetime, timedelta
from pathlib import Path

from instagrapi import Client
from instagrapi.types import DirectMessage, DirectThread, User
from instagrapi.exceptions import (
    LoginRequired, ClientError, ClientLoginRequired, 
    ClientThrottledError, ClientConnectionError
)

logger = logging.getLogger(__name__)


class InstagramClient:
    """
    Instagram API client wrapper using instagrapi.
    Handles authentication, rate limiting, and data fetching.
    """
    
    def __init__(self, username: str, password: str, session_file: str = "instagram_session.json"):
        """
        Initialize Instagram client.
        
        Args:
            username: Instagram username
            password: Instagram password
            session_file: Path to session file for persistence
        """
        self.username = username
        self.password = password
        self.session_file = Path(session_file)
        self.client = Client()
        self.is_authenticated = False
        
        # Configure client settings
        self._configure_client()
    
    def _configure_client(self):
        """Configure instagrapi client settings."""
        # Set user agent to avoid detection
        self.client.set_user_agent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        
        # Set proxy if needed (uncomment and configure as needed)
        # self.client.set_proxy("http://proxy:port")
        
        # Set device settings
        self.client.set_device({
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "dpi": "480dpi",
            "resolution": "1080x1920",
            "manufacturer": "Huawei",
            "device": "HUAWEI",
            "model": "HUAWEI P10",
            "cpu": "hi3660",
            "version_code": "314665256"
        })
    
    async def authenticate(self) -> bool:
        """
        Authenticate with Instagram.
        
        Returns:
            bool: True if authentication successful
        """
        try:
            # Try to load existing session
            if self.session_file.exists():
                logger.info("Loading existing session...")
                self.client.load_settings(str(self.session_file))
                
                # Test if session is still valid
                try:
                    await asyncio.to_thread(self.client.get_timeline_feed)
                    self.is_authenticated = True
                    logger.info("Session loaded successfully")
                    return True
                except (LoginRequired, ClientLoginRequired):
                    logger.info("Session expired, re-authenticating...")
            
            # Login with credentials
            logger.info("Authenticating with Instagram...")
            await asyncio.to_thread(
                self.client.login, 
                self.username, 
                self.password
            )
            
            # Save session for future use
            await asyncio.to_thread(
                self.client.dump_settings, 
                str(self.session_file)
            )
            
            self.is_authenticated = True
            logger.info("Authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            self.is_authenticated = False
            return False
    
    async def get_direct_threads(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all direct message threads.
        
        Args:
            limit: Maximum number of threads to fetch
            
        Returns:
            List of thread information
        """
        if not self.is_authenticated:
            raise ClientLoginRequired("Not authenticated")
        
        try:
            logger.info(f"Fetching up to {limit} direct threads...")
            
            # Get direct threads
            threads = await asyncio.to_thread(
                self.client.direct_threads, 
                amount=limit
            )
            
            # Convert to dictionary format
            thread_data = []
            for thread in threads:
                thread_info = {
                    "thread_id": str(thread.id),
                    "title": thread.title or "Untitled",
                    "users": [
                        {
                            "user_id": str(user.pk),
                            "username": user.username,
                            "full_name": user.full_name,
                            "profile_pic_url": user.profile_pic_url
                        }
                        for user in thread.users
                    ],
                    "last_message_at": thread.last_activity,
                    "message_count": thread.messages_count,
                    "is_group_chat": thread.is_group,
                    "thread_type": "group" if thread.is_group else "direct",
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                thread_data.append(thread_info)
            
            logger.info(f"Fetched {len(thread_data)} threads")
            return thread_data
            
        except Exception as e:
            logger.error(f"Error fetching direct threads: {e}")
            raise
    
    async def get_thread_messages(
        self, 
        thread_id: str, 
        limit: int = 50,
        max_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get messages from a specific thread.
        
        Args:
            thread_id: Thread ID
            limit: Maximum number of messages to fetch
            max_id: Maximum message ID for pagination
            
        Returns:
            List of message information
        """
        if not self.is_authenticated:
            raise ClientLoginRequired("Not authenticated")
        
        try:
            logger.info(f"Fetching messages for thread {thread_id}")
            
            # Get messages from thread
            messages = await asyncio.to_thread(
                self.client.direct_messages,
                thread_id=int(thread_id),
                amount=limit,
                max_id=max_id
            )
            
            # Convert to dictionary format
            message_data = []
            for msg in messages:
                message_info = {
                    "message_id": str(msg.id),
                    "thread_id": str(msg.thread_id),
                    "user_id": str(msg.user_id),
                    "text": msg.text or "",
                    "timestamp": msg.timestamp,
                    "item_type": msg.item_type,
                    "media_url": getattr(msg, 'media_url', None),
                    "media_type": getattr(msg, 'media_type', None),
                    "is_from_me": msg.user_id == self.client.user_id,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                message_data.append(message_info)
            
            logger.info(f"Fetched {len(message_data)} messages")
            return message_data
            
        except Exception as e:
            logger.error(f"Error fetching messages for thread {thread_id}: {e}")
            raise
    
    async def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user information by username.
        
        Args:
            username: Instagram username
            
        Returns:
            User information dictionary
        """
        if not self.is_authenticated:
            raise ClientLoginRequired("Not authenticated")
        
        try:
            logger.info(f"Fetching user info for {username}")
            
            # Get user info
            user = await asyncio.to_thread(
                self.client.user_info_by_username, 
                username
            )
            
            user_info = {
                "instagram_user_id": str(user.pk),
                "username": user.username,
                "full_name": user.full_name,
                "profile_pic_url": user.profile_pic_url,
                "is_private": user.is_private,
                "is_verified": user.is_verified,
                "follower_count": user.follower_count,
                "following_count": user.following_count,
                "biography": user.biography,
                "external_url": user.external_url,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            return user_info
            
        except Exception as e:
            logger.error(f"Error fetching user info for {username}: {e}")
            return None
    
    async def send_direct_message(
        self, 
        thread_id: str, 
        message: str,
        user_ids: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Send a direct message to a thread.
        
        Args:
            thread_id: Thread ID
            message: Message text
            user_ids: List of user IDs (for new threads)
            
        Returns:
            Message ID if successful, None otherwise
        """
        if not self.is_authenticated:
            raise ClientLoginRequired("Not authenticated")
        
        try:
            logger.info(f"Sending message to thread {thread_id}")
            
            if user_ids:
                # Send to specific users (creates new thread if needed)
                result = await asyncio.to_thread(
                    self.client.direct_send,
                    message,
                    user_ids=[int(uid) for uid in user_ids]
                )
            else:
                # Send to existing thread
                result = await asyncio.to_thread(
                    self.client.direct_send,
                    message,
                    thread_ids=[int(thread_id)]
                )
            
            if result:
                logger.info("Message sent successfully")
                return str(result[0].id) if result else None
            
            return None
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    async def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current account information.
        
        Returns:
            Account information dictionary
        """
        if not self.is_authenticated:
            raise ClientLoginRequired("Not authenticated")
        
        try:
            logger.info("Fetching account info")
            
            # Get account info
            account = await asyncio.to_thread(self.client.account_info)
            
            account_info = {
                "instagram_user_id": str(account.pk),
                "username": account.username,
                "full_name": account.full_name,
                "profile_pic_url": account.profile_pic_url,
                "is_private": account.is_private,
                "is_verified": account.is_verified,
                "follower_count": account.follower_count,
                "following_count": account.following_count,
                "biography": account.biography,
                "external_url": account.external_url,
                "email": getattr(account, 'email', None),
                "phone_number": getattr(account, 'phone_number', None),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            return account_info
            
        except Exception as e:
            logger.error(f"Error fetching account info: {e}")
            return None
    
    async def test_connection(self) -> bool:
        """
        Test Instagram connection.
        
        Returns:
            bool: True if connection successful
        """
        try:
            if not self.is_authenticated:
                return False
            
            # Try to get timeline feed as a connection test
            await asyncio.to_thread(self.client.get_timeline_feed)
            return True
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    async def close(self):
        """Close the Instagram client."""
        try:
            # Save session before closing
            if self.is_authenticated and self.session_file:
                await asyncio.to_thread(
                    self.client.dump_settings, 
                    str(self.session_file)
                )
            
            logger.info("Instagram client closed")
            
        except Exception as e:
            logger.error(f"Error closing client: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        asyncio.create_task(self.close()) 