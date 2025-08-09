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
        # Use minimal configuration to avoid detection
        # Don't set custom device settings - let instagrapi use defaults
        pass
    
    async def check_account_status(self) -> Dict[str, Any]:
        """
        Check Instagram account status without logging in.
        
        Returns:
            Dict with account status information
        """
        try:
            logger.info("Checking Instagram account status...")
            
            # Try to get public info about the account
            user_info = await asyncio.to_thread(
                self.client.user_info_by_username,
                self.username
            )
            
            if user_info:
                return {
                    "status": "account_exists",
                    "username": user_info.username,
                    "is_private": user_info.is_private,
                    "is_verified": user_info.is_verified,
                    "follower_count": user_info.follower_count,
                    "following_count": user_info.following_count,
                    "media_count": user_info.media_count
                }
            else:
                return {"status": "account_not_found"}
                
        except Exception as e:
            logger.warning(f"Could not check account status: {e}")
            return {"status": "unknown", "error": str(e)}
    
    async def authenticate(self) -> bool:
        """
        Authenticate with Instagram.
        
        Returns:
            bool: True if authentication successful
        """
        try:
            # Try to load existing session first
            if self.session_file.exists():
                logger.info("Loading existing session...")
                try:
                    self.client.load_settings(str(self.session_file))
                    
                    # Test if session is still valid
                    await asyncio.to_thread(self.client.get_timeline_feed)
                    self.is_authenticated = True
                    logger.info("Session loaded successfully")
                    return True
                except Exception as e:
                    logger.info(f"Session expired or invalid: {e}, will re-authenticate...")
            
            # Simple login approach like in the working collector
            logger.info("Authenticating with Instagram...")
            logger.info(f"Username: {self.username}")
            
            # Login with credentials (simple approach)
            await asyncio.to_thread(
                self.client.login, 
                self.username, 
                self.password
            )
            
            # Verify login was successful
            try:
                account_info = await asyncio.to_thread(self.client.account_info)
                if account_info:
                    logger.info(f"✅ Authentication successful! Logged in as: {account_info.username}")
                    
                    # Save session for future use
                    await asyncio.to_thread(
                        self.client.dump_settings, 
                        str(self.session_file)
                    )
                    
                    self.is_authenticated = True
                    return True
                else:
                    logger.error("❌ Login succeeded but couldn't get account info")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Could not verify account info: {e}")
                # Still try to proceed if login succeeded
                self.is_authenticated = True
                return True
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            
            # Check for specific error types
            error_str = str(e).lower()
            if "challenge" in error_str:
                logger.error("🔒 Instagram requires additional verification (challenge)")
                logger.error("Please log into Instagram in your browser and complete any security checks")
            elif "checkpoint" in error_str:
                logger.error("🔒 Instagram account checkpoint - verification required")
                logger.error("Please check your email/SMS for verification codes")
            elif "password" in error_str:
                logger.error("🔑 Password incorrect or account locked")
            elif "rate" in error_str:
                logger.error("⏰ Rate limited - try again later")
            elif "csrf" in error_str:
                logger.error("🛡️ CSRF token issue - Instagram security measure")
                logger.error("Try logging in manually in browser first")
            
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
            
            # Convert to dictionary format with error handling
            thread_data = []
            for thread in threads:
                try:
                    # Clean and validate thread data
                    thread_info = {
                        'id': str(thread.id),
                        'title': getattr(thread, 'title', '') or getattr(thread, 'thread_title', 'Unknown'),
                        'users': [],
                        'last_activity': getattr(thread, 'last_activity', None),
                        'muted': getattr(thread, 'muted', False),
                        'is_pending': getattr(thread, 'is_pending', False),
                        'is_group': getattr(thread, 'is_group', False)
                    }
                    
                    # Safely extract user information
                    if hasattr(thread, 'users') and thread.users:
                        for user in thread.users:
                            try:
                                user_info = {
                                    'id': str(getattr(user, 'id', '')),
                                    'username': getattr(user, 'username', ''),
                                    'full_name': getattr(user, 'full_name', ''),
                                    'profile_pic_url': getattr(user, 'profile_pic_url', ''),
                                    'is_verified': getattr(user, 'is_verified', False),
                                    'is_private': getattr(user, 'is_private', False)
                                }
                                # Clean None values
                                user_info = {k: v if v is not None else '' for k, v in user_info.items()}
                                thread_info['users'].append(user_info)
                            except Exception as user_error:
                                logger.warning(f"Error processing user in thread {thread.id}: {user_error}")
                                continue
                    
                    thread_data.append(thread_info)
                    
                except Exception as thread_error:
                    logger.warning(f"Error processing thread {getattr(thread, 'id', 'unknown')}: {thread_error}")
                    continue
            
            logger.info(f"Successfully fetched {len(thread_data)} threads")
            return thread_data
            
        except Exception as e:
            logger.error(f"Error fetching direct threads: {e}")
            # Return empty list instead of raising to allow partial functionality
            return []
    
    async def get_thread_messages(
        self, 
        thread_id: str, 
        limit: int = 50,
        max_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get messages from a specific thread.
        
        Args:
            thread_id: ID of the thread
            limit: Maximum number of messages to fetch
            max_id: ID of the last message to start from (for pagination)
            
        Returns:
            List of message dictionaries
        """
        if not self.is_authenticated:
            raise ClientLoginRequired("Not authenticated")
        
        try:
            logger.info(f"Fetching up to {limit} messages from thread {thread_id}")
            
            # Get messages from the thread
            messages = await asyncio.to_thread(
                self.client.direct_messages,
                thread_id,
                amount=limit,
                max_id=max_id
            )
            
            # Convert to dictionary format with error handling
            message_data = []
            for message in messages:
                try:
                    # Safely extract message data with error handling
                    message_info = {
                        'id': str(getattr(message, 'id', '')),
                        'thread_id': str(thread_id),
                        'user_id': str(getattr(message, 'user_id', '')),
                        'username': '',
                        'text': getattr(message, 'text', '') or '',
                        'timestamp': getattr(message, 'timestamp', None),
                        'message_type': getattr(message, 'item_type', 'text'),
                        'is_from_me': str(getattr(message, 'user_id', '')) == str(self.client.user_id),
                        'media_type': getattr(message, 'media_type', None),
                        'media_url': getattr(message, 'media_url', None),
                        'thumbnail_url': getattr(message, 'thumbnail_url', None)
                    }
                    
                    # Safely extract username
                    if hasattr(message, 'user') and message.user:
                        message_info['username'] = getattr(message.user, 'username', '')
                    elif hasattr(message, 'username'):
                        message_info['username'] = message.username
                    
                    # Clean None values and convert to safe types
                    message_info = {k: v if v is not None else '' for k, v in message_info.items()}
                    
                    # Handle timestamp conversion
                    if message_info['timestamp'] and hasattr(message_info['timestamp'], 'isoformat'):
                        message_info['timestamp'] = message_info['timestamp'].isoformat()
                    elif message_info['timestamp']:
                        message_info['timestamp'] = str(message_info['timestamp'])
                    else:
                        message_info['timestamp'] = ''
                    
                    message_data.append(message_info)
                    
                except Exception as msg_error:
                    logger.warning(f"Error processing message {getattr(message, 'id', 'unknown')}: {msg_error}")
                    continue
            
            logger.info(f"Successfully fetched {len(message_data)} messages from thread {thread_id}")
            return message_data
            
        except Exception as e:
            logger.error(f"Error fetching messages from thread {thread_id}: {e}")
            # Return empty list instead of raising to allow partial functionality
            return []
    
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