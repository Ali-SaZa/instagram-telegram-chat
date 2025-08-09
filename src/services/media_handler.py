"""
Media handling service for processing Instagram media files.
Handles image/video processing, storage management, and media caching.
"""

import asyncio
import hashlib
import logging
import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from urllib.parse import urlparse
import uuid

from PIL import Image, ImageOps
import magic
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class MediaType(str, Enum):
    """Types of media files."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"
    UNKNOWN = "unknown"


class MediaFormat(str, Enum):
    """Supported media formats."""
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    MP4 = "mp4"
    MOV = "mov"
    AVI = "avi"
    MP3 = "mp3"
    WAV = "wav"
    PDF = "pdf"
    TXT = "txt"


class MediaInfo(BaseModel):
    """Media file information."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_filename: str = Field(..., description="Original filename")
    media_type: MediaType = Field(..., description="Type of media")
    format: MediaFormat = Field(..., description="Media format")
    mime_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="File size in bytes")
    dimensions: Optional[Tuple[int, int]] = Field(None, description="Image/video dimensions")
    duration: Optional[float] = Field(None, description="Video/audio duration in seconds")
    hash: str = Field(..., description="File hash for deduplication")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class MediaHandler:
    """Media handling service for Instagram media files."""
    
    def __init__(self, base_path: str = "data/media_cache", max_file_size: int = 100 * 1024 * 1024):
        """Initialize the media handler."""
        self.base_path = Path(base_path)
        self.max_file_size = max_file_size
        
        # Create directory structure
        self._create_directories()
        
        # Supported formats
        self.supported_formats = {
            MediaType.IMAGE: [MediaFormat.JPEG, MediaFormat.PNG, MediaFormat.GIF],
            MediaType.VIDEO: [MediaFormat.MP4, MediaFormat.MOV, MediaFormat.AVI],
            MediaType.AUDIO: [MediaFormat.MP3, MediaFormat.WAV],
            MediaType.DOCUMENT: [MediaFormat.PDF, MediaFormat.TXT]
        }
        
        # File type detection
        self.mime_detector = magic.Magic(mime=True)
        
        # Statistics
        self.stats = {
            "files_processed": 0,
            "files_stored": 0,
            "files_compressed": 0,
            "errors": 0
        }
    
    def _create_directories(self):
        """Create necessary directories."""
        try:
            # Create base directory
            self.base_path.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories for each media type
            for media_type in MediaType:
                media_dir = self.base_path / media_type.value
                media_dir.mkdir(exist_ok=True)
                
                # Create format subdirectories
                for format_type in MediaFormat:
                    format_dir = media_dir / format_type.value
                    format_dir.mkdir(exist_ok=True)
            
            # Create temp directory
            temp_dir = self.base_path / "temp"
            temp_dir.mkdir(exist_ok=True)
            
            logger.info(f"Media directories created at {self.base_path}")
            
        except Exception as e:
            logger.error(f"Failed to create media directories: {e}")
            raise
    
    async def process_media_file(
        self,
        file_path: Union[str, Path],
        original_filename: str,
        media_type: Optional[MediaType] = None
    ) -> Optional[MediaInfo]:
        """
        Process a media file and store it in the cache.
        
        Args:
            file_path: Path to the media file
            original_filename: Original filename
            media_type: Optional media type override
            
        Returns:
            MediaInfo: Media information if successful, None otherwise
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None
            
            # Check file size
            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                logger.warning(f"File too large: {file_path} ({file_size} bytes)")
                return None
            
            # Detect media type and format
            detected_info = await self._detect_media_info(file_path, original_filename)
            
            if not detected_info:
                logger.error(f"Failed to detect media info for: {file_path}")
                return None
            
            # Override media type if specified
            if media_type:
                detected_info.media_type = media_type
            
            # Generate file hash
            file_hash = await self._generate_file_hash(file_path)
            detected_info.hash = file_hash
            
            # Check if file already exists (deduplication)
            existing_file = await self._find_existing_file(file_hash, detected_info.media_type, detected_info.format)
            if existing_file:
                logger.info(f"File already exists: {existing_file}")
                return await self._get_media_info(existing_file)
            
            # Store the file
            stored_path = await self._store_media_file(file_path, detected_info)
            if not stored_path:
                logger.error(f"Failed to store media file: {file_path}")
                return None
            
            # Update file path
            detected_info.metadata["stored_path"] = str(stored_path)
            
            # Update statistics
            self.stats["files_processed"] += 1
            self.stats["files_stored"] += 1
            
            logger.info(f"Media file processed and stored: {stored_path}")
            return detected_info
            
        except Exception as e:
            logger.error(f"Error processing media file {file_path}: {e}")
            self.stats["errors"] += 1
            return None
    
    async def _detect_media_info(self, file_path: Path, original_filename: str) -> Optional[MediaInfo]:
        """Detect media file information."""
        try:
            # Get MIME type
            mime_type = self.mime_detector.from_file(str(file_path))
            
            # Determine media type and format
            media_type, format_type = self._classify_media(mime_type, original_filename)
            
            if not media_type or not format_type:
                logger.warning(f"Unsupported media type: {mime_type}")
                return None
            
            # Get file size
            file_size = file_path.stat().st_size
            
            # Get dimensions and duration for supported types
            dimensions = None
            duration = None
            
            if media_type == MediaType.IMAGE:
                dimensions = await self._get_image_dimensions(file_path)
            elif media_type in [MediaType.VIDEO, MediaType.AUDIO]:
                duration = await self._get_media_duration(file_path)
                if media_type == MediaType.VIDEO:
                    dimensions = await self._get_video_dimensions(file_path)
            
            return MediaInfo(
                original_filename=original_filename,
                media_type=media_type,
                format=format_type,
                mime_type=mime_type,
                file_size=file_size,
                dimensions=dimensions,
                duration=duration
            )
            
        except Exception as e:
            logger.error(f"Error detecting media info: {e}")
            return None
    
    def _classify_media(self, mime_type: str, filename: str) -> Tuple[Optional[MediaType], Optional[MediaFormat]]:
        """Classify media based on MIME type and filename."""
        # MIME type classification
        mime_to_type = {
            "image/": MediaType.IMAGE,
            "video/": MediaType.VIDEO,
            "audio/": MediaType.AUDIO,
            "application/": MediaType.DOCUMENT
        }
        
        # Determine media type
        media_type = None
        for mime_prefix, type_enum in mime_to_type.items():
            if mime_type.startswith(mime_prefix):
                media_type = type_enum
                break
        
        if not media_type:
            return None, None
        
        # Determine format
        format_type = None
        
        if media_type == MediaType.IMAGE:
            if mime_type == "image/jpeg":
                format_type = MediaFormat.JPEG
            elif mime_type == "image/png":
                format_type = MediaFormat.PNG
            elif mime_type == "image/gif":
                format_type = MediaFormat.GIF
        elif media_type == MediaType.VIDEO:
            if mime_type == "video/mp4":
                format_type = MediaFormat.MP4
            elif mime_type == "video/quicktime":
                format_type = MediaFormat.MOV
            elif mime_type == "video/x-msvideo":
                format_type = MediaFormat.AVI
        elif media_type == MediaType.AUDIO:
            if mime_type == "audio/mpeg":
                format_type = MediaFormat.MP3
            elif mime_type == "audio/wav":
                format_type = MediaFormat.WAV
        elif media_type == MediaType.DOCUMENT:
            if mime_type == "application/pdf":
                format_type = MediaFormat.PDF
            elif mime_type == "text/plain":
                format_type = MediaFormat.TXT
        
        # Fallback to filename extension if MIME type classification fails
        if not format_type:
            ext = Path(filename).suffix.lower()
            ext_to_format = {
                ".jpg": MediaFormat.JPEG,
                ".jpeg": MediaFormat.JPEG,
                ".png": MediaFormat.PNG,
                ".gif": MediaFormat.GIF,
                ".mp4": MediaFormat.MP4,
                ".mov": MediaFormat.MOV,
                ".avi": MediaFormat.AVI,
                ".mp3": MediaFormat.MP3,
                ".wav": MediaFormat.WAV,
                ".pdf": MediaFormat.PDF,
                ".txt": MediaFormat.TXT
            }
            format_type = ext_to_format.get(ext)
        
        return media_type, format_type
    
    async def _generate_file_hash(self, file_path: Path) -> str:
        """Generate SHA-256 hash of the file."""
        try:
            hash_sha256 = hashlib.sha256()
            
            # Read file in chunks to handle large files
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            
            return hash_sha256.hexdigest()
            
        except Exception as e:
            logger.error(f"Error generating file hash: {e}")
            # Fallback to filename-based hash
            return hashlib.sha256(str(file_path).encode()).hexdigest()
    
    async def _find_existing_file(self, file_hash: str, media_type: MediaType, format_type: MediaFormat) -> Optional[Path]:
        """Find existing file with the same hash."""
        try:
            # Look in the appropriate directory
            search_dir = self.base_path / media_type.value / format_type.value
            
            if not search_dir.exists():
                return None
            
            # Search for files with matching hash
            for file_path in search_dir.iterdir():
                if file_path.is_file():
                    try:
                        existing_hash = await self._generate_file_hash(file_path)
                        if existing_hash == file_hash:
                            return file_path
                    except Exception:
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding existing file: {e}")
            return None
    
    async def _store_media_file(self, source_path: Path, media_info: MediaInfo) -> Optional[Path]:
        """Store the media file in the appropriate directory."""
        try:
            # Determine target directory
            target_dir = self.base_path / media_info.media_type.value / media_info.format.value
            
            # Generate target filename
            target_filename = f"{media_info.hash}.{media_info.format.value}"
            target_path = target_dir / target_filename
            
            # Copy file to target location
            shutil.copy2(source_path, target_path)
            
            # Verify file was copied correctly
            if not target_path.exists():
                logger.error(f"File copy failed: {target_path}")
                return None
            
            logger.info(f"Media file stored: {target_path}")
            return target_path
            
        except Exception as e:
            logger.error(f"Error storing media file: {e}")
            return None
    
    async def _get_image_dimensions(self, file_path: Path) -> Optional[Tuple[int, int]]:
        """Get image dimensions."""
        try:
            with Image.open(file_path) as img:
                return img.size
        except Exception as e:
            logger.debug(f"Could not get image dimensions: {e}")
            return None
    
    async def _get_video_dimensions(self, file_path: Path) -> Optional[Tuple[int, int]]:
        """Get video dimensions (placeholder implementation)."""
        # This would require video processing libraries like ffmpeg
        # For now, return None
        return None
    
    async def _get_media_duration(self, file_path: Path) -> Optional[float]:
        """Get media duration (placeholder implementation)."""
        # This would require audio/video processing libraries
        # For now, return None
        return None
    
    async def _get_media_info(self, file_path: Path) -> Optional[MediaInfo]:
        """Get media information from stored file."""
        try:
            # Extract information from file path
            parts = file_path.parts
            if len(parts) < 4:
                return None
            
            media_type = MediaType(parts[-3])
            format_type = MediaFormat(parts[-2])
            filename = parts[-1]
            
            # Get file stats
            stat = file_path.stat()
            file_size = stat.st_size
            created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
            
            # Generate hash
            file_hash = await self._generate_file_hash(file_path)
            
            # Get MIME type
            mime_type = self.mime_detector.from_file(str(file_path))
            
            # Get dimensions and duration
            dimensions = None
            duration = None
            
            if media_type == MediaType.IMAGE:
                dimensions = await self._get_image_dimensions(file_path)
            elif media_type == MediaType.VIDEO:
                dimensions = await self._get_video_dimensions(file_path)
                duration = await self._get_media_duration(file_path)
            elif media_type == MediaType.AUDIO:
                duration = await self._get_media_duration(file_path)
            
            return MediaInfo(
                original_filename=filename,
                media_type=media_type,
                format=format_type,
                mime_type=mime_type,
                file_size=file_size,
                dimensions=dimensions,
                duration=duration,
                hash=file_hash,
                created_at=created_at,
                metadata={"stored_path": str(file_path)}
            )
            
        except Exception as e:
            logger.error(f"Error getting media info: {e}")
            return None
    
    async def compress_image(
        self,
        file_path: Union[str, Path],
        quality: int = 85,
        max_width: Optional[int] = None,
        max_height: Optional[int] = None
    ) -> Optional[Path]:
        """
        Compress and resize an image.
        
        Args:
            file_path: Path to the image file
            quality: JPEG quality (1-100)
            max_width: Maximum width
            max_height: Maximum height
            
        Returns:
            Path: Path to compressed image
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                logger.error(f"Image file not found: {file_path}")
                return None
            
            # Open image
            with Image.open(file_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if dimensions specified
                if max_width or max_height:
                    img = ImageOps.fit(img, (max_width or img.width, max_height or img.height))
                
                # Create output path
                output_dir = self.base_path / "temp"
                output_filename = f"compressed_{file_path.stem}.jpg"
                output_path = output_dir / output_filename
                
                # Save compressed image
                img.save(output_path, 'JPEG', quality=quality, optimize=True)
                
                # Update statistics
                self.stats["files_compressed"] += 1
                
                logger.info(f"Image compressed: {output_path}")
                return output_path
                
        except Exception as e:
            logger.error(f"Error compressing image {file_path}: {e}")
            self.stats["errors"] += 1
            return None
    
    async def get_media_file(self, media_id: str, media_type: MediaType, format_type: MediaFormat) -> Optional[Path]:
        """Get a stored media file by ID."""
        try:
            # Look for file with the ID as filename
            file_path = self.base_path / media_type.value / format_type.value / f"{media_id}.{format_type.value}"
            
            if file_path.exists():
                return file_path
            
            # If not found, search by hash
            search_dir = self.base_path / media_type.value / format_type.value
            for file_path in search_dir.iterdir():
                if file_path.is_file() and file_path.stem == media_id:
                    return file_path
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting media file: {e}")
            return None
    
    async def delete_media_file(self, media_id: str, media_type: MediaType, format_type: MediaFormat) -> bool:
        """Delete a stored media file."""
        try:
            file_path = await self.get_media_file(media_id, media_type, format_type)
            
            if file_path and file_path.exists():
                file_path.unlink()
                logger.info(f"Media file deleted: {file_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting media file: {e}")
            return False
    
    async def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """Clean up temporary files older than specified age."""
        try:
            temp_dir = self.base_path / "temp"
            if not temp_dir.exists():
                return 0
            
            cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
            deleted_count = 0
            
            for file_path in temp_dir.iterdir():
                if file_path.is_file():
                    try:
                        if file_path.stat().st_ctime < cutoff_time:
                            file_path.unlink()
                            deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Could not delete temp file {file_path}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} temporary files")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up temp files: {e}")
            return 0
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            stats = {
                "total_size": 0,
                "file_count": 0,
                "by_type": {},
                "by_format": {}
            }
            
            # Calculate statistics for each media type
            for media_type in MediaType:
                media_dir = self.base_path / media_type.value
                if media_dir.exists():
                    type_stats = {"size": 0, "count": 0}
                    
                    for format_dir in media_dir.iterdir():
                        if format_dir.is_dir():
                            format_stats = {"size": 0, "count": 0}
                            
                            for file_path in format_dir.iterdir():
                                if file_path.is_file():
                                    try:
                                        file_size = file_path.stat().st_size
                                        format_stats["size"] += file_size
                                        format_stats["count"] += 1
                                        type_stats["size"] += file_size
                                        type_stats["count"] += 1
                                    except Exception:
                                        continue
                            
                            # Add format stats
                            if format_stats["count"] > 0:
                                stats["by_format"][format_dir.name] = format_stats
                    
                    # Add type stats
                    if type_stats["count"] > 0:
                        stats["by_type"][media_type.value] = type_stats
                        stats["total_size"] += type_stats["size"]
                        stats["file_count"] += type_stats["count"]
            
            # Add service stats
            stats.update(self.stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the media handler."""
        try:
            # Check if base directory exists and is writable
            base_writable = os.access(self.base_path, os.W_OK)
            
            # Get storage stats
            storage_stats = await self.get_storage_stats()
            
            return {
                "status": "healthy" if base_writable else "unhealthy",
                "base_directory": str(self.base_path),
                "writable": base_writable,
                "storage_stats": storage_stats
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global media handler instance
_media_handler: Optional[MediaHandler] = None


async def get_media_handler() -> MediaHandler:
    """Get the global media handler instance."""
    global _media_handler
    
    if _media_handler is None:
        from config.settings import get_settings
        settings = get_settings()
        
        _media_handler = MediaHandler(
            base_path=settings.media_cache_path,
            max_file_size=settings.max_media_file_size
        )
    
    return _media_handler


async def cleanup_media_handler():
    """Cleanup the global media handler."""
    global _media_handler
    
    if _media_handler:
        # Cleanup temp files
        await _media_handler.cleanup_temp_files()
        _media_handler = None 