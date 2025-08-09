"""
User management for the Telegram bot.
"""

import logging
import hashlib
import secrets
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

from ..database.operations import InstagramOperations

logger = logging.getLogger(__name__)


@dataclass
class UserPreferences:
    """User preferences and settings."""
    language: str = "en"
    timezone: str = "UTC"
    notifications_enabled: bool = True
    auto_sync_enabled: bool = True
    message_format: str = "compact"  # compact, detailed
    theme: str = "default"  # default, dark, light
    max_messages_per_page: int = 20
    search_history_enabled: bool = True


@dataclass
class UserPermissions:
    """User permissions and access levels."""
    can_send_messages: bool = True
    can_read_messages: bool = True
    can_search_messages: bool = True
    can_manage_threads: bool = False
    can_manage_users: bool = False
    can_access_admin: bool = False
    can_export_data: bool = False


class UserManager:
    """Manages user registration, authentication, and permissions."""
    
    def __init__(self):
        """Initialize the user manager."""
        self.db_ops = InstagramOperations()
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.auth_tokens: Dict[str, Dict[str, Any]] = {}
        
    async def register_user(self, telegram_user_id: int, username: str, full_name: str) -> Dict[str, Any]:
        """
        Register a new user.
        
        Args:
            telegram_user_id: Telegram user ID
            username: Telegram username
            full_name: User's full name
            
        Returns:
            Dict containing registration result
        """
        try:
            # Check if user already exists
            if telegram_user_id in self.user_sessions:
                return {"error": "User already registered"}
            
            # Create user session
            user_session = {
                "telegram_user_id": telegram_user_id,
                "username": username,
                "full_name": full_name,
                "registered_at": datetime.now(),
                "last_login": datetime.now(),
                "is_active": True,
                "preferences": asdict(UserPreferences()),
                "permissions": asdict(UserPermissions()),
                "login_count": 1,
                "last_activity": datetime.now()
            }
            
            # Store user session
            self.user_sessions[telegram_user_id] = user_session
            
            # Generate authentication token
            auth_token = self._generate_auth_token()
            self.auth_tokens[auth_token] = {
                "telegram_user_id": telegram_user_id,
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=30)
            }
            
            logger.info(f"Registered new user: {username} (ID: {telegram_user_id})")
            
            return {
                "success": True,
                "user_id": telegram_user_id,
                "auth_token": auth_token,
                "message": "User registered successfully"
            }
            
        except Exception as e:
            logger.error(f"Error registering user {telegram_user_id}: {e}")
            return {"error": f"Registration failed: {str(e)}"}
    
    async def authenticate_user(self, telegram_user_id: int) -> Dict[str, Any]:
        """
        Authenticate a user.
        
        Args:
            telegram_user_id: Telegram user ID
            
        Returns:
            Dict containing authentication result
        """
        try:
            # Check if user exists
            if telegram_user_id not in self.user_sessions:
                return {"error": "User not registered"}
            
            user_session = self.user_sessions[telegram_user_id]
            
            # Check if user is active
            if not user_session["is_active"]:
                return {"error": "User account is deactivated"}
            
            # Update login information
            user_session["last_login"] = datetime.now()
            user_session["login_count"] += 1
            user_session["last_activity"] = datetime.now()
            
            # Generate new auth token
            auth_token = self._generate_auth_token()
            self.auth_tokens[auth_token] = {
                "telegram_user_id": telegram_user_id,
                "created_at": datetime.now(),
                "expires_at": datetime.now() + timedelta(days=30)
            }
            
            # Clean up old tokens
            self._cleanup_expired_tokens()
            
            logger.info(f"User {telegram_user_id} authenticated successfully")
            
            return {
                "success": True,
                "user_id": telegram_user_id,
                "auth_token": auth_token,
                "preferences": user_session["preferences"],
                "permissions": user_session["permissions"]
            }
            
        except Exception as e:
            logger.error(f"Error authenticating user {telegram_user_id}: {e}")
            return {"error": f"Authentication failed: {str(e)}"}
    
    async def get_user_info(self, telegram_user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get user information.
        
        Args:
            telegram_user_id: Telegram user ID
            
        Returns:
            Dict containing user info or None
        """
        if telegram_user_id in self.user_sessions:
            user_info = self.user_sessions[telegram_user_id].copy()
            # Remove sensitive data
            user_info.pop("auth_token", None)
            return user_info
        return None
    
    async def update_user_preferences(self, telegram_user_id: int, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user preferences.
        
        Args:
            telegram_user_id: Telegram user ID
            preferences: New preferences to set
            
        Returns:
            Dict containing update result
        """
        try:
            if telegram_user_id not in self.user_sessions:
                return {"error": "User not found"}
            
            user_session = self.user_sessions[telegram_user_id]
            
            # Update preferences
            for key, value in preferences.items():
                if hasattr(UserPreferences, key):
                    user_session["preferences"][key] = value
            
            user_session["last_activity"] = datetime.now()
            
            logger.info(f"Updated preferences for user {telegram_user_id}")
            
            return {
                "success": True,
                "message": "Preferences updated successfully",
                "preferences": user_session["preferences"]
            }
            
        except Exception as e:
            logger.error(f"Error updating preferences for user {telegram_user_id}: {e}")
            return {"error": f"Failed to update preferences: {str(e)}"}
    
    async def update_user_permissions(self, telegram_user_id: int, permissions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update user permissions (admin only).
        
        Args:
            telegram_user_id: Telegram user ID
            permissions: New permissions to set
            
        Returns:
            Dict containing update result
        """
        try:
            if telegram_user_id not in self.user_sessions:
                return {"error": "User not found"}
            
            user_session = self.user_sessions[telegram_user_id]
            
            # Check if user has admin permissions
            if not user_session["permissions"]["can_access_admin"]:
                return {"error": "Insufficient permissions"}
            
            # Update permissions
            for key, value in permissions.items():
                if hasattr(UserPermissions, key):
                    user_session["permissions"][key] = value
            
            user_session["last_activity"] = datetime.now()
            
            logger.info(f"Updated permissions for user {telegram_user_id}")
            
            return {
                "success": True,
                "message": "Permissions updated successfully",
                "permissions": user_session["permissions"]
            }
            
        except Exception as e:
            logger.error(f"Error updating permissions for user {telegram_user_id}: {e}")
            return {"error": f"Failed to update permissions: {str(e)}"}
    
    async def deactivate_user(self, telegram_user_id: int) -> Dict[str, Any]:
        """
        Deactivate a user account.
        
        Args:
            telegram_user_id: Telegram user ID
            
        Returns:
            Dict containing deactivation result
        """
        try:
            if telegram_user_id not in self.user_sessions:
                return {"error": "User not found"}
            
            user_session = self.user_sessions[telegram_user_id]
            user_session["is_active"] = False
            user_session["deactivated_at"] = datetime.now()
            user_session["last_activity"] = datetime.now()
            
            # Remove auth tokens
            self._remove_user_tokens(telegram_user_id)
            
            logger.info(f"Deactivated user {telegram_user_id}")
            
            return {
                "success": True,
                "message": "User deactivated successfully"
            }
            
        except Exception as e:
            logger.error(f"Error deactivating user {telegram_user_id}: {e}")
            return {"error": f"Failed to deactivate user: {str(e)}"}
    
    async def reactivate_user(self, telegram_user_id: int) -> Dict[str, Any]:
        """
        Reactivate a deactivated user account.
        
        Args:
            telegram_user_id: Telegram user ID
            
        Returns:
            Dict containing reactivation result
        """
        try:
            if telegram_user_id not in self.user_sessions:
                return {"error": "User not found"}
            
            user_session = self.user_sessions[telegram_user_id]
            user_session["is_active"] = True
            user_session["reactivated_at"] = datetime.now()
            user_session["last_activity"] = datetime.now()
            
            logger.info(f"Reactivated user {telegram_user_id}")
            
            return {
                "success": True,
                "message": "User reactivated successfully"
            }
            
        except Exception as e:
            logger.error(f"Error reactivating user {telegram_user_id}: {e}")
            return {"error": f"Failed to reactivate user: {str(e)}"}
    
    async def get_user_activity(self, telegram_user_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get user activity statistics.
        
        Args:
            telegram_user_id: Telegram user ID
            days: Number of days to look back
            
        Returns:
            Dict containing activity statistics
        """
        try:
            if telegram_user_id not in self.user_sessions:
                return {"error": "User not found"}
            
            user_session = self.user_sessions[telegram_user_id]
            
            # Calculate activity metrics
            registered_days = (datetime.now() - user_session["registered_at"]).days
            last_activity_days = (datetime.now() - user_session["last_activity"]).days
            
            activity_stats = {
                "user_id": telegram_user_id,
                "username": user_session["username"],
                "registered_days_ago": registered_days,
                "last_activity_days_ago": last_activity_days,
                "total_logins": user_session["login_count"],
                "is_active": user_session["is_active"],
                "preferences": user_session["preferences"],
                "permissions": user_session["permissions"]
            }
            
            return activity_stats
            
        except Exception as e:
            logger.error(f"Error getting activity for user {telegram_user_id}: {e}")
            return {"error": f"Failed to get activity: {str(e)}"}
    
    async def get_all_users(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Get all users (admin only).
        
        Args:
            include_inactive: Whether to include inactive users
            
        Returns:
            List of user information
        """
        try:
            users = []
            for user_id, user_session in self.user_sessions.items():
                if include_inactive or user_session["is_active"]:
                    user_info = user_session.copy()
                    # Remove sensitive data
                    user_info.pop("auth_token", None)
                    users.append(user_info)
            
            return users
            
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
    
    async def cleanup_inactive_users(self, max_inactive_days: int = 90) -> int:
        """
        Clean up inactive users.
        
        Args:
            max_inactive_days: Maximum days of inactivity
            
        Returns:
            int: Number of users cleaned up
        """
        try:
            current_time = datetime.now()
            inactive_users = []
            
            for user_id, user_session in self.user_sessions.items():
                if not user_session["is_active"]:
                    last_activity = user_session["last_activity"]
                    inactive_days = (current_time - last_activity).days
                    
                    if inactive_days > max_inactive_days:
                        inactive_users.append(user_id)
            
            # Remove inactive users
            for user_id in inactive_users:
                del self.user_sessions[user_id]
                self._remove_user_tokens(user_id)
            
            logger.info(f"Cleaned up {len(inactive_users)} inactive users")
            return len(inactive_users)
            
        except Exception as e:
            logger.error(f"Error cleaning up inactive users: {e}")
            return 0
    
    def _generate_auth_token(self) -> str:
        """Generate a secure authentication token."""
        return secrets.token_urlsafe(32)
    
    def _remove_user_tokens(self, telegram_user_id: int):
        """Remove all auth tokens for a user."""
        tokens_to_remove = []
        for token, token_data in self.auth_tokens.items():
            if token_data["telegram_user_id"] == telegram_user_id:
                tokens_to_remove.append(token)
        
        for token in tokens_to_remove:
            del self.auth_tokens[token]
    
    def _cleanup_expired_tokens(self):
        """Remove expired authentication tokens."""
        current_time = datetime.now()
        expired_tokens = []
        
        for token, token_data in self.auth_tokens.items():
            if token_data["expires_at"] < current_time:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del self.auth_tokens[token]
        
        if expired_tokens:
            logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
    
    def get_user_statistics(self) -> Dict[str, Any]:
        """
        Get user management statistics.
        
        Returns:
            Dict containing user statistics
        """
        try:
            total_users = len(self.user_sessions)
            active_users = sum(1 for user in self.user_sessions.values() if user["is_active"])
            inactive_users = total_users - active_users
            
            # Calculate average user age
            total_age = 0
            for user in self.user_sessions.values():
                age = (datetime.now() - user["registered_at"]).days
                total_age += age
            
            avg_age = total_age / total_users if total_users > 0 else 0
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": inactive_users,
                "average_user_age_days": avg_age,
                "total_auth_tokens": len(self.auth_tokens)
            }
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {e}")
            return {"error": str(e)} 