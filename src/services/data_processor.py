"""
Data processing service for Instagram-Telegram chat integration.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlparse, urljoin
import aiohttp
import hashlib
import os
from pathlib import Path

from config.settings import get_settings
from ..database.models import (
    InstagramMessage, InstagramUser, InstagramThread, 
    MessageType, MessageStatus, SyncStatus
)

logger = logging.getLogger(__name__)


class DataProcessor:
    """Processes and validates Instagram data for storage and transmission."""
    
    def __init__(self):
        self.settings = get_settings()
        self.media_cache_dir = self.settings.data_dir / "media_cache"
        self.media_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Media file extensions mapping
        self.media_extensions = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
            'video': ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'],
            'audio': ['.mp3', '.wav', '.aac', '.ogg', '.m4a'],
            'file': ['.pdf', '.doc', '.docx', '.txt', '.zip', '.rar']
        }
    
    async def process_instagram_message(self, raw_message: Dict[str, Any]) -> InstagramMessage:
        """Process raw Instagram message data into structured format."""
        try:
            # Extract basic message information
            message_id = str(raw_message.get('id', ''))
            thread_id = str(raw_message.get('thread_id', ''))
            sender_id = str(raw_message.get('user_id', ''))
            
            # Determine message type
            message_type = self._determine_message_type(raw_message)
            
            # Extract content
            content = self._extract_message_content(raw_message, message_type)
            
            # Process media files
            media_urls, media_files = await self._process_media_files(raw_message)
            
            # Extract additional metadata
            metadata = self._extract_message_metadata(raw_message)
            
            # Create InstagramMessage instance
            message = InstagramMessage(
                message_id=message_id,
                thread_id=thread_id,
                sender_id=sender_id,
                message_type=message_type,
                content=content,
                media_urls=media_urls,
                media_files=media_files,
                metadata=metadata,
                instagram_timestamp=self._parse_timestamp(raw_message.get('timestamp')),
                status=MessageStatus.SENT
            )
            
            # Validate message
            self._validate_message(message)
            
            logger.debug(f"Processed message {message_id} of type {message_type}")
            return message
            
        except Exception as e:
            logger.error(f"Error processing Instagram message: {e}")
            raise
    
    def _determine_message_type(self, raw_message: Dict[str, Any]) -> MessageType:
        """Determine the type of Instagram message."""
        # Check for media types first
        if raw_message.get('media_type') == 1:
            return MessageType.IMAGE
        elif raw_message.get('media_type') == 2:
            return MessageType.VIDEO
        elif raw_message.get('media_type') == 3:
            return MessageType.AUDIO
        
        # Check for specific message types
        if raw_message.get('story_reply'):
            return MessageType.STORY_REPLY
        elif raw_message.get('reaction'):
            return MessageType.REACTION
        elif raw_message.get('sticker'):
            return MessageType.STICKER
        
        # Check content for file attachments
        if raw_message.get('file_url'):
            return MessageType.FILE
        
        # Default to text
        return MessageType.TEXT
    
    def _extract_message_content(self, raw_message: Dict[str, Any], message_type: MessageType) -> str:
        """Extract message content based on type."""
        if message_type == MessageType.TEXT:
            return raw_message.get('text', '').strip()
        elif message_type == MessageType.IMAGE:
            caption = raw_message.get('caption', '')
            return f"[Image] {caption}".strip() if caption else "[Image]"
        elif message_type == MessageType.VIDEO:
            caption = raw_message.get('caption', '')
            return f"[Video] {caption}".strip() if caption else "[Video]"
        elif message_type == MessageType.AUDIO:
            caption = raw_message.get('caption', '')
            return f"[Audio] {caption}".strip() if caption else "[Audio]"
        elif message_type == MessageType.FILE:
            filename = raw_message.get('file_name', 'Unknown file')
            return f"[File] {filename}"
        elif message_type == MessageType.STICKER:
            return "[Sticker]"
        elif message_type == MessageType.STORY_REPLY:
            return f"[Story Reply] {raw_message.get('text', '')}"
        elif message_type == MessageType.REACTION:
            emoji = raw_message.get('emoji', '❤️')
            return f"[Reaction] {emoji}"
        else:
            return raw_message.get('text', '').strip()
    
    async def _process_media_files(self, raw_message: Dict[str, Any]) -> tuple[List[str], List[Dict[str, Any]]]:
        """Process media files from Instagram message."""
        media_urls = []
        media_files = []
        
        try:
            # Process different types of media
            if raw_message.get('media_type') == 1:  # Image
                media_info = await self._process_image_media(raw_message)
                if media_info:
                    media_urls.append(media_info['url'])
                    media_files.append(media_info)
            
            elif raw_message.get('media_type') == 2:  # Video
                media_info = await self._process_video_media(raw_message)
                if media_info:
                    media_urls.append(media_info['url'])
                    media_files.append(media_info)
            
            elif raw_message.get('media_type') == 3:  # Audio
                media_info = await self._process_audio_media(raw_message)
                if media_info:
                    media_urls.append(media_info['url'])
                    media_files.append(media_info)
            
            # Process file attachments
            if raw_message.get('file_url'):
                file_info = await self._process_file_attachment(raw_message)
                if file_info:
                    media_urls.append(file_info['url'])
                    media_files.append(file_info)
            
        except Exception as e:
            logger.error(f"Error processing media files: {e}")
        
        return media_urls, media_files
    
    async def _process_image_media(self, raw_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process image media from Instagram message."""
        try:
            image_url = raw_message.get('image_url') or raw_message.get('media_url')
            if not image_url:
                return None
            
            # Download and cache image
            cached_path = await self._download_and_cache_media(image_url, 'image')
            if not cached_path:
                return None
            
            return {
                'type': 'image',
                'url': image_url,
                'local_path': str(cached_path),
                'size': cached_path.stat().st_size if cached_path.exists() else 0,
                'format': cached_path.suffix.lower(),
                'dimensions': raw_message.get('dimensions', {}),
                'caption': raw_message.get('caption', '')
            }
            
        except Exception as e:
            logger.error(f"Error processing image media: {e}")
            return None
    
    async def _process_video_media(self, raw_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process video media from Instagram message."""
        try:
            video_url = raw_message.get('video_url') or raw_message.get('media_url')
            if not video_url:
                return None
            
            # Download and cache video
            cached_path = await self._download_and_cache_media(video_url, 'video')
            if not cached_path:
                return None
            
            return {
                'type': 'video',
                'url': video_url,
                'local_path': str(cached_path),
                'size': cached_path.stat().st_size if cached_path.exists() else 0,
                'format': cached_path.suffix.lower(),
                'duration': raw_message.get('duration', 0),
                'dimensions': raw_message.get('dimensions', {}),
                'caption': raw_message.get('caption', '')
            }
            
        except Exception as e:
            logger.error(f"Error processing video media: {e}")
            return None
    
    async def _process_audio_media(self, raw_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process audio media from Instagram message."""
        try:
            audio_url = raw_message.get('audio_url') or raw_message.get('media_url')
            if not audio_url:
                return None
            
            # Download and cache audio
            cached_path = await self._download_and_cache_media(audio_url, 'audio')
            if not cached_path:
                return None
            
            return {
                'type': 'audio',
                'url': audio_url,
                'local_path': str(cached_path),
                'size': cached_path.stat().st_size if cached_path.exists() else 0,
                'format': cached_path.suffix.lower(),
                'duration': raw_message.get('duration', 0),
                'caption': raw_message.get('caption', '')
            }
            
        except Exception as e:
            logger.error(f"Error processing audio media: {e}")
            return None
    
    async def _process_file_attachment(self, raw_message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process file attachments from Instagram message."""
        try:
            file_url = raw_message.get('file_url')
            if not file_url:
                return None
            
            # Download and cache file
            cached_path = await self._download_and_cache_media(file_url, 'file')
            if not cached_path:
                return None
            
            return {
                'type': 'file',
                'url': file_url,
                'local_path': str(cached_path),
                'size': cached_path.stat().st_size if cached_path.exists() else 0,
                'format': cached_path.suffix.lower(),
                'filename': raw_message.get('file_name', 'Unknown file'),
                'mime_type': raw_message.get('mime_type', 'application/octet-stream')
            }
            
        except Exception as e:
            logger.error(f"Error processing file attachment: {e}")
            return None
    
    async def _download_and_cache_media(self, url: str, media_type: str) -> Optional[Path]:
        """Download and cache media file locally."""
        try:
            # Generate cache filename
            url_hash = hashlib.md5(url.encode()).hexdigest()
            file_extension = self._get_file_extension_from_url(url)
            cache_filename = f"{media_type}_{url_hash}{file_extension}"
            cache_path = self.media_cache_dir / cache_filename
            
            # Check if already cached
            if cache_path.exists():
                logger.debug(f"Media already cached: {cache_path}")
                return cache_path
            
            # Download file
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.read()
                        
                        # Save to cache
                        cache_path.write_bytes(content)
                        logger.debug(f"Media cached successfully: {cache_path}")
                        return cache_path
                    else:
                        logger.warning(f"Failed to download media from {url}: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error downloading media from {url}: {e}")
            return None
    
    def _get_file_extension_from_url(self, url: str) -> str:
        """Extract file extension from URL."""
        parsed_url = urlparse(url)
        path = parsed_url.path
        extension = Path(path).suffix.lower()
        
        if not extension:
            # Try to determine from content type or default
            return '.bin'
        
        return extension
    
    def _extract_message_metadata(self, raw_message: Dict[str, Any]) -> Dict[str, Any]:
        """Extract additional metadata from Instagram message."""
        metadata = {}
        
        # Extract common fields
        if raw_message.get('timestamp'):
            metadata['instagram_timestamp'] = raw_message['timestamp']
        
        if raw_message.get('client_context'):
            metadata['client_context'] = raw_message['client_context']
        
        if raw_message.get('device_timestamp'):
            metadata['device_timestamp'] = raw_message['device_timestamp']
        
        # Extract media-specific metadata
        if raw_message.get('media_type'):
            metadata['media_type_code'] = raw_message['media_type']
        
        if raw_message.get('dimensions'):
            metadata['dimensions'] = raw_message['dimensions']
        
        if raw_message.get('duration'):
            metadata['duration'] = raw_message['duration']
        
        # Extract user interaction metadata
        if raw_message.get('like_count'):
            metadata['like_count'] = raw_message['like_count']
        
        if raw_message.get('reply_count'):
            metadata['reply_count'] = raw_message['reply_count']
        
        # Extract business metadata
        if raw_message.get('business_id'):
            metadata['business_id'] = raw_message['business_id']
        
        if raw_message.get('product_id'):
            metadata['product_id'] = raw_message['product_id']
        
        return metadata
    
    def _parse_timestamp(self, timestamp_value: Any) -> Optional[datetime]:
        """Parse timestamp from various formats."""
        if not timestamp_value:
            return None
        
        try:
            if isinstance(timestamp_value, (int, float)):
                # Unix timestamp
                return datetime.fromtimestamp(timestamp_value)
            elif isinstance(timestamp_value, str):
                # Try parsing as ISO format
                return datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            elif isinstance(timestamp_value, datetime):
                return timestamp_value
            else:
                logger.warning(f"Unknown timestamp format: {timestamp_value}")
                return None
        except Exception as e:
            logger.error(f"Error parsing timestamp {timestamp_value}: {e}")
            return None
    
    def _validate_message(self, message: InstagramMessage):
        """Validate processed message data."""
        if not message.message_id:
            raise ValueError("Message ID is required")
        
        if not message.thread_id:
            raise ValueError("Thread ID is required")
        
        if not message.sender_id:
            raise ValueError("Sender ID is required")
        
        if not message.content and not message.media_urls:
            raise ValueError("Message must have content or media")
        
        if message.message_type not in MessageType:
            raise ValueError(f"Invalid message type: {message.message_type}")
    
    async def process_instagram_user(self, raw_user: Dict[str, Any]) -> InstagramUser:
        """Process raw Instagram user data into structured format."""
        try:
            # Extract user information
            instagram_id = str(raw_user.get('pk', ''))
            username = raw_user.get('username', '').lower()
            full_name = raw_user.get('full_name', '')
            profile_picture = raw_user.get('profile_pic_url', '')
            
            # Create InstagramUser instance
            user = InstagramUser(
                instagram_id=instagram_id,
                username=username,
                full_name=full_name,
                profile_picture=profile_picture,
                is_verified=raw_user.get('is_verified', False),
                is_private=raw_user.get('is_private', False),
                is_business=raw_user.get('is_business', False),
                followers_count=raw_user.get('follower_count'),
                following_count=raw_user.get('following_count'),
                posts_count=raw_user.get('media_count'),
                biography=raw_user.get('biography', ''),
                external_url=raw_user.get('external_url', ''),
                last_seen=datetime.utcnow()
            )
            
            # Validate user
            self._validate_user(user)
            
            logger.debug(f"Processed user {username} (ID: {instagram_id})")
            return user
            
        except Exception as e:
            logger.error(f"Error processing Instagram user: {e}")
            raise
    
    def _validate_user(self, user: InstagramUser):
        """Validate processed user data."""
        if not user.instagram_id:
            raise ValueError("Instagram ID is required")
        
        if not user.username:
            raise ValueError("Username is required")
        
        if len(user.username) > 30:
            raise ValueError("Username too long")
    
    async def process_instagram_thread(self, raw_thread: Dict[str, Any]) -> InstagramThread:
        """Process raw Instagram thread data into structured format."""
        try:
            # Extract thread information
            thread_id = str(raw_thread.get('thread_id', ''))
            participants = [str(participant.get('user_id', '')) for participant in raw_thread.get('users', [])]
            
            # Create InstagramThread instance
            thread = InstagramThread(
                thread_id=thread_id,
                participants=participants,
                title=raw_thread.get('thread_title', ''),
                is_group=len(participants) > 2,
                last_activity=self._parse_timestamp(raw_thread.get('last_activity_at')),
                message_count=raw_thread.get('items', []).__len__(),
                unread_count=raw_thread.get('unread_count', 0),
                last_sync=datetime.utcnow()
            )
            
            # Validate thread
            self._validate_thread(thread)
            
            logger.debug(f"Processed thread {thread_id} with {len(participants)} participants")
            return thread
            
        except Exception as e:
            logger.error(f"Error processing Instagram thread: {e}")
            raise
    
    def _validate_thread(self, thread: InstagramThread):
        """Validate processed thread data."""
        if not thread.thread_id:
            raise ValueError("Thread ID is required")
        
        if len(thread.participants) < 2:
            raise ValueError("Thread must have at least 2 participants")
    
    async def format_message_for_telegram(self, message: InstagramMessage, user: InstagramUser) -> str:
        """Format Instagram message for Telegram display."""
        try:
            # Start with sender information
            formatted = f"**{user.full_name or user.username}** (@{user.username})\n\n"
            
            # Add message content
            if message.content:
                formatted += message.content + "\n\n"
            
            # Add media information
            if message.media_urls:
                media_types = [media.get('type', 'unknown') for media in message.media_files]
                formatted += f"📎 **Media**: {', '.join(media_types).title()}\n"
            
            # Add timestamp
            if message.instagram_timestamp:
                formatted += f"🕐 {message.instagram_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
            
            return formatted.strip()
            
        except Exception as e:
            logger.error(f"Error formatting message for Telegram: {e}")
            return f"Error formatting message: {str(e)}"
    
    async def cleanup_old_media_cache(self, max_age_days: int = 7):
        """Clean up old cached media files."""
        try:
            cutoff_time = datetime.utcnow().timestamp() - (max_age_days * 24 * 3600)
            cleaned_count = 0
            
            for cache_file in self.media_cache_dir.iterdir():
                if cache_file.is_file():
                    file_age = cache_file.stat().st_mtime
                    if file_age < cutoff_time:
                        try:
                            cache_file.unlink()
                            cleaned_count += 1
                            logger.debug(f"Cleaned up old cache file: {cache_file}")
                        except Exception as e:
                            logger.warning(f"Failed to clean up cache file {cache_file}: {e}")
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old cache files")
                
        except Exception as e:
            logger.error(f"Error cleaning up media cache: {e}")
    
    async def get_media_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the media cache."""
        try:
            cache_dir = self.media_cache_dir
            total_files = 0
            total_size = 0
            type_counts = {}
            
            for cache_file in cache_dir.iterdir():
                if cache_file.is_file():
                    total_files += 1
                    total_size += cache_file.stat().st_size
                    
                    # Count by type
                    file_type = cache_file.stem.split('_')[0] if '_' in cache_file.stem else 'unknown'
                    type_counts[file_type] = type_counts.get(file_type, 0) + 1
            
            return {
                "total_files": total_files,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "type_counts": type_counts,
                "cache_directory": str(cache_dir)
            }
            
        except Exception as e:
            logger.error(f"Error getting media cache stats: {e}")
            return {"error": str(e)}


# Global data processor instance
data_processor = DataProcessor()


async def get_data_processor() -> DataProcessor:
    """Get the global data processor instance."""
    return data_processor


async def cleanup_media_cache():
    """Clean up old media cache files."""
    await data_processor.cleanup_old_media_cache()


async def get_media_cache_stats():
    """Get media cache statistics."""
    return await data_processor.get_media_cache_stats() 