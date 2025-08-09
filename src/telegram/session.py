"""
User session management for the Telegram bot.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class UserSession:
    """Manages user session state and preferences."""
    
    def __init__(self, user_id: int):
        """
        Initialize a user session.
        
        Args:
            user_id: Telegram user ID
        """
        self.user_id = user_id
        self.created_at = datetime.now()
        self.last_activity = datetime.now()
        
        # Session state
        self.current_thread_id = None
        self.current_page = 1
        self.search_query = None
        self.preferences = {}
        
        # Rate limiting
        self.command_count = 0
        self.last_command_time = None
        self.rate_limit_window = 60  # 1 minute
        self.max_commands_per_window = 30
    
    def update_activity(self):
        """Update the last activity timestamp."""
        self.last_activity = datetime.now()
    
    def is_active(self, max_inactive_hours: int = 24) -> bool:
        """
        Check if the session is still active.
        
        Args:
            max_inactive_hours: Maximum hours of inactivity
            
        Returns:
            bool: True if session is active
        """
        if not self.last_activity:
            return False
        
        inactive_time = datetime.now() - self.last_activity
        return inactive_time.total_seconds() < (max_inactive_hours * 3600)
    
    def set_current_thread(self, thread_id: str):
        """Set the current thread being viewed."""
        self.current_thread_id = thread_id
        self.current_page = 1
        self.update_activity()
    
    def get_current_thread(self) -> Optional[str]:
        """Get the current thread ID."""
        return self.current_thread_id
    
    def set_page(self, page: int):
        """Set the current page for pagination."""
        if page > 0:
            self.current_page = page
            self.update_activity()
    
    def get_page(self) -> int:
        """Get the current page."""
        return self.current_page
    
    def next_page(self) -> int:
        """Go to the next page."""
        self.current_page += 1
        self.update_activity()
        return self.current_page
    
    def previous_page(self) -> int:
        """Go to the previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self.update_activity()
        return self.current_page
    
    def set_search_query(self, query: str):
        """Set the current search query."""
        self.search_query = query
        self.current_page = 1
        self.update_activity()
    
    def get_search_query(self) -> Optional[str]:
        """Get the current search query."""
        return self.search_query
    
    def set_preference(self, key: str, value: Any):
        """Set a user preference."""
        self.preferences[key] = value
        self.update_activity()
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return self.preferences.get(key, default)
    
    def can_execute_command(self) -> bool:
        """
        Check if the user can execute a command (rate limiting).
        
        Returns:
            bool: True if command can be executed
        """
        now = datetime.now()
        
        # Reset counter if window has passed
        if (self.last_command_time and 
            (now - self.last_command_time).total_seconds() > self.rate_limit_window):
            self.command_count = 0
        
        # Check if under limit
        if self.command_count < self.max_commands_per_window:
            self.command_count += 1
            self.last_command_time = now
            self.update_activity()
            return True
        
        return False
    
    def get_rate_limit_info(self) -> Dict[str, Any]:
        """
        Get rate limiting information.
        
        Returns:
            Dictionary with rate limit info
        """
        if not self.last_command_time:
            return {
                'commands_used': 0,
                'commands_remaining': self.max_commands_per_window,
                'window_resets_in': 0
            }
        
        now = datetime.now()
        time_since_last = (now - self.last_command_time).total_seconds()
        window_resets_in = max(0, self.rate_limit_window - time_since_last)
        
        return {
            'commands_used': self.command_count,
            'commands_remaining': max(0, self.max_commands_per_window - self.command_count),
            'window_resets_in': int(window_resets_in)
        }
    
    def reset_rate_limit(self):
        """Reset the rate limit counter."""
        self.command_count = 0
        self.last_command_time = None
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get session information.
        
        Returns:
            Dictionary with session info
        """
        return {
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'current_thread_id': self.current_thread_id,
            'current_page': self.current_page,
            'search_query': self.search_query,
            'preferences': self.preferences,
            'is_active': self.is_active(),
            'rate_limit_info': self.get_rate_limit_info()
        }
    
    def clear_session(self):
        """Clear all session data."""
        self.current_thread_id = None
        self.current_page = 1
        self.search_query = None
        self.preferences = {}
        self.command_count = 0
        self.last_command_time = None
        self.update_activity()
    
    def __str__(self) -> str:
        """String representation of the session."""
        return f"UserSession(user_id={self.user_id}, active={self.is_active()})"
    
    def __repr__(self) -> str:
        """Detailed string representation of the session."""
        return (f"UserSession(user_id={self.user_id}, "
                f"created_at={self.created_at}, "
                f"last_activity={self.last_activity}, "
                f"active={self.is_active()})") 