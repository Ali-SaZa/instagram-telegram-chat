"""
Database models for Instagram-Telegram chat integration.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic models."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


class MessageType(str, Enum):
    """Types of Instagram messages."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    STICKER = "sticker"
    REACTION = "reaction"
    STORY_REPLY = "story_reply"
    UNKNOWN = "unknown"


class MessageStatus(str, Enum):
    """Status of messages."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    PENDING = "pending"


class SyncStatus(str, Enum):
    """Status of sync operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InstagramUser(BaseModel):
    """Instagram user model."""
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    instagram_id: str = Field(..., description="Instagram user ID")
    username: str = Field(..., description="Instagram username")
    full_name: Optional[str] = Field(None, description="Full name")
    profile_picture: Optional[str] = Field(None, description="Profile picture URL")
    is_verified: bool = Field(default=False, description="Is user verified")
    is_private: bool = Field(default=False, description="Is user private")
    is_business: bool = Field(default=False, description="Is business account")
    followers_count: Optional[int] = Field(None, description="Followers count")
    following_count: Optional[int] = Field(None, description="Following count")
    posts_count: Optional[int] = Field(None, description="Posts count")
    biography: Optional[str] = Field(None, description="User biography")
    external_url: Optional[str] = Field(None, description="External URL")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen: Optional[datetime] = Field(None, description="Last seen timestamp")
    is_active: bool = Field(default=True, description="Is user active")
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "instagram_id": "123456789",
                "username": "johndoe",
                "full_name": "John Doe",
                "profile_picture": "https://example.com/pic.jpg",
                "is_verified": False,
                "is_private": False,
                "is_business": False,
                "followers_count": 1000,
                "following_count": 500,
                "posts_count": 50
            }
        }
    
    @validator('username')
    def validate_username(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Username cannot be empty")
        if len(v) > 30:
            raise ValueError("Username too long")
        return v.strip().lower()
    
    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


class InstagramThread(BaseModel):
    """Instagram direct message thread model."""
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    thread_id: str = Field(..., description="Instagram thread ID")
    participants: List[str] = Field(..., description="List of participant Instagram IDs")
    participant_users: List[PyObjectId] = Field(default_factory=list, description="References to participant users")
    title: Optional[str] = Field(None, description="Thread title")
    is_group: bool = Field(default=False, description="Is group chat")
    is_active: bool = Field(default=True, description="Is thread active")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    message_count: int = Field(default=0, description="Total message count")
    unread_count: int = Field(default=0, description="Unread message count")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_sync: Optional[datetime] = Field(None, description="Last sync timestamp")
    sync_status: SyncStatus = Field(default=SyncStatus.PENDING, description="Sync status")
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "thread_id": "thread_123456",
                "participants": ["123456789", "987654321"],
                "title": "Group Chat",
                "is_group": True,
                "message_count": 150,
                "unread_count": 5
            }
        }
    
    @validator('participants')
    def validate_participants(cls, v):
        if not v or len(v) < 2:
            raise ValueError("Thread must have at least 2 participants")
        return v
    
    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()
    
    def update_activity(self):
        """Update the last_activity timestamp."""
        self.last_activity = datetime.utcnow()


class InstagramMessage(BaseModel):
    """Instagram direct message model."""
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    message_id: str = Field(..., description="Instagram message ID")
    thread_id: str = Field(..., description="Thread ID this message belongs to")
    sender_id: str = Field(..., description="Sender Instagram ID")
    sender_user: Optional[PyObjectId] = Field(None, description="Reference to sender user")
    message_type: MessageType = Field(..., description="Type of message")
    content: str = Field(..., description="Message content")
    media_urls: List[str] = Field(default_factory=list, description="Media file URLs")
    media_files: List[Dict[str, Any]] = Field(default_factory=list, description="Media file metadata")
    reply_to: Optional[str] = Field(None, description="Reply to message ID")
    reactions: List[Dict[str, Any]] = Field(default_factory=list, description="Message reactions")
    status: MessageStatus = Field(default=MessageStatus.SENT, description="Message status")
    is_edited: bool = Field(default=False, description="Is message edited")
    edited_at: Optional[datetime] = Field(None, description="Edit timestamp")
    is_deleted: bool = Field(default=False, description="Is message deleted")
    deleted_at: Optional[datetime] = Field(None, description="Deletion timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    instagram_timestamp: Optional[datetime] = Field(None, description="Original Instagram timestamp")
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "message_id": "msg_123456",
                "thread_id": "thread_123456",
                "sender_id": "123456789",
                "message_type": "text",
                "content": "Hello, how are you?",
                "status": "sent"
            }
        }
    
    @validator('content')
    def validate_content(cls, v):
        if not v and len(v.strip()) == 0:
            raise ValueError("Message content cannot be empty")
        return v.strip()
    
    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


class ChatSession(BaseModel):
    """Telegram chat session model."""
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    telegram_user_id: int = Field(..., description="Telegram user ID")
    telegram_chat_id: int = Field(..., description="Telegram chat ID")
    instagram_user_id: Optional[str] = Field(None, description="Linked Instagram user ID")
    active_thread_id: Optional[str] = Field(None, description="Currently active thread ID")
    is_active: bool = Field(default=True, description="Is session active")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="User preferences")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "telegram_user_id": 123456789,
                "telegram_chat_id": 123456789,
                "instagram_user_id": "123456789",
                "active_thread_id": "thread_123456",
                "preferences": {"notifications": True, "language": "en"}
            }
        }
    
    def update_activity(self):
        """Update the last_activity timestamp."""
        self.last_activity = datetime.utcnow()
        self.updated_at = datetime.utcnow()


class SyncStatus(BaseModel):
    """Sync operation status model."""
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    operation_id: str = Field(..., description="Unique operation ID")
    operation_type: str = Field(..., description="Type of sync operation")
    status: SyncStatus = Field(..., description="Current status")
    target_id: Optional[str] = Field(None, description="Target ID (user/thread)")
    target_type: Optional[str] = Field(None, description="Target type (user/thread)")
    progress: float = Field(default=0.0, description="Progress percentage (0-100)")
    total_items: Optional[int] = Field(None, description="Total items to process")
    processed_items: int = Field(default=0, description="Processed items count")
    failed_items: int = Field(default=0, description="Failed items count")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Retry attempt count")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "operation_id": "sync_123456",
                "operation_type": "user_sync",
                "status": "in_progress",
                "target_id": "123456789",
                "target_type": "user",
                "progress": 75.0,
                "total_items": 100,
                "processed_items": 75
            }
        }
    
    @validator('progress')
    def validate_progress(cls, v):
        if v < 0 or v > 100:
            raise ValueError("Progress must be between 0 and 100")
        return v
    
    def is_completed(self) -> bool:
        """Check if operation is completed."""
        return self.status in [SyncStatus.COMPLETED, SyncStatus.FAILED, SyncStatus.CANCELLED]
    
    def can_retry(self) -> bool:
        """Check if operation can be retried."""
        return self.status == SyncStatus.FAILED and self.retry_count < self.max_retries


class UserPreference(BaseModel):
    """User preferences model."""
    
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    telegram_user_id: int = Field(..., description="Telegram user ID")
    instagram_user_id: Optional[str] = Field(None, description="Linked Instagram user ID")
    language: str = Field(default="en", description="Preferred language")
    timezone: str = Field(default="UTC", description="Preferred timezone")
    notifications_enabled: bool = Field(default=True, description="Enable notifications")
    notification_types: List[str] = Field(default_factory=lambda: ["message", "mention"], description="Notification types")
    auto_sync: bool = Field(default=True, description="Enable auto-sync")
    sync_interval: int = Field(default=300, description="Sync interval in seconds")
    privacy_level: str = Field(default="standard", description="Privacy level")
    theme: str = Field(default="light", description="UI theme preference")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "telegram_user_id": 123456789,
                "language": "en",
                "timezone": "UTC",
                "notifications_enabled": True,
                "notification_types": ["message", "mention"],
                "auto_sync": True,
                "sync_interval": 300
            }
        }
    
    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


# Index definitions for performance optimization
INDEXES = {
    "instagram_users": [
        [("instagram_id", 1), {"unique": True}],
        [("username", 1), {"unique": True}],
        [("is_active", 1)],
        [("last_seen", -1)]
    ],
    "instagram_threads": [
        [("thread_id", 1), {"unique": True}],
        [("participants", 1)],
        [("is_active", 1)],
        [("last_activity", -1)],
        [("sync_status", 1)]
    ],
    "instagram_messages": [
        [("message_id", 1), {"unique": True}],
        [("thread_id", 1)],
        [("sender_id", 1)],
        [("created_at", -1)],
        [("instagram_timestamp", -1)],
        [("status", 1)]
    ],
    "chat_sessions": [
        [("telegram_user_id", 1)],
        [("telegram_chat_id", 1)],
        [("instagram_user_id", 1)],
        [("is_active", 1)],
        [("last_activity", -1)]
    ],
    "sync_status": [
        [("operation_id", 1), {"unique": True}],
        [("status", 1)],
        [("target_id", 1)],
        [("started_at", -1)]
    ],
    "user_preferences": [
        [("telegram_user_id", 1), {"unique": True}],
        [("instagram_user_id", 1)]
    ]
} 