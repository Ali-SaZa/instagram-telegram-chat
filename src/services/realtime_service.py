"""
Real-time service for WebSocket connections and push notifications.
Handles live updates and message delivery confirmations.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum

import websockets
from websockets.server import WebSocketServerProtocol
from pydantic import BaseModel, Field

from .message_queue import MessageQueueService, MessageType, QueueMessage, get_message_queue_service

logger = logging.getLogger(__name__)


class ConnectionType(str, Enum):
    """Types of WebSocket connections."""
    TELEGRAM_USER = "telegram_user"
    INSTAGRAM_WEBHOOK = "instagram_webhook"
    ADMIN_PANEL = "admin_panel"
    MONITORING = "monitoring"


class ConnectionStatus(str, Enum):
    """Connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class WebSocketConnection:
    """Represents a WebSocket connection."""
    
    def __init__(self, websocket: WebSocketServerProtocol, connection_type: ConnectionType, user_id: str):
        """Initialize a WebSocket connection."""
        self.websocket = websocket
        self.connection_type = connection_type
        self.user_id = user_id
        self.connection_id = str(uuid.uuid4())
        self.status = ConnectionStatus.CONNECTED
        self.connected_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self.metadata: Dict[str, Any] = {}
        
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send a message to the WebSocket client."""
        try:
            if self.status == ConnectionStatus.CONNECTED:
                message_data = json.dumps(message)
                await self.websocket.send(message_data)
                self.last_activity = datetime.now(timezone.utc)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to send message to {self.connection_id}: {e}")
            self.status = ConnectionStatus.ERROR
            return False
    
    async def close(self):
        """Close the WebSocket connection."""
        try:
            self.status = ConnectionStatus.DISCONNECTED
            await self.websocket.close()
        except Exception as e:
            logger.error(f"Error closing connection {self.connection_id}: {e}")
    
    def is_alive(self) -> bool:
        """Check if the connection is still alive."""
        return self.status == ConnectionStatus.CONNECTED and not self.websocket.closed


class NotificationType(str, Enum):
    """Types of notifications."""
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    MESSAGE_DELIVERED = "message_delivered"
    MESSAGE_READ = "message_read"
    USER_ONLINE = "user_online"
    USER_OFFLINE = "user_offline"
    SYNC_UPDATE = "sync_update"
    ERROR_ALERT = "error_alert"
    SYSTEM_UPDATE = "system_update"


class Notification(BaseModel):
    """Notification structure."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    user_id: str = Field(..., description="Target user ID")
    data: Dict[str, Any] = Field(default_factory=dict, description="Additional data")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="Expiration time")
    priority: str = Field(default="normal", description="Notification priority")
    read: bool = Field(default=False, description="Whether notification was read")


class RealtimeService:
    """Real-time service for WebSocket connections and notifications."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        """Initialize the real-time service."""
        self.host = host
        self.port = port
        self.connections: Dict[str, WebSocketConnection] = {}
        self.connection_groups: Dict[str, Set[str]] = {}
        self.message_queue: Optional[MessageQueueService] = None
        self.websocket_server = None
        self.running = False
        
        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # Statistics
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "notifications_sent": 0
        }
    
    async def initialize(self):
        """Initialize the real-time service."""
        try:
            # Get message queue service
            self.message_queue = await get_message_queue_service()
            
            # Register message queue consumers
            await self._setup_message_queue_consumers()
            
            logger.info("Real-time service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize real-time service: {e}")
            raise
    
    async def _setup_message_queue_consumers(self):
        """Setup message queue consumers for real-time updates."""
        if not self.message_queue:
            return
        
        # Register consumer for Instagram DM updates
        self.message_queue.register_consumer(
            MessageType.INSTAGRAM_DM,
            self._handle_instagram_dm_update
        )
        
        # Register consumer for notification updates
        self.message_queue.register_consumer(
            MessageType.NOTIFICATION,
            self._handle_notification_update
        )
        
        # Start consumers
        await self.message_queue.start_consumers()
    
    async def _handle_instagram_dm_update(self, message: QueueMessage) -> bool:
        """Handle Instagram DM updates from the message queue."""
        try:
            payload = message.payload
            thread_id = payload.get("thread_id")
            sender_id = payload.get("sender_id")
            
            # Notify all connected users about the new message
            notification = Notification(
                type=NotificationType.MESSAGE_RECEIVED,
                title="New Instagram Message",
                message=f"New message from {sender_id}",
                user_id="broadcast",  # Broadcast to all users
                data={
                    "thread_id": thread_id,
                    "sender_id": sender_id,
                    "message_id": payload.get("message_id"),
                    "content": payload.get("content", "")
                }
            )
            
            # Send to all connected Telegram users
            await self.broadcast_notification(notification, ConnectionType.TELEGRAM_USER)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling Instagram DM update: {e}")
            return False
    
    async def _handle_notification_update(self, message: QueueMessage) -> bool:
        """Handle notification updates from the message queue."""
        try:
            payload = message.payload
            notification_type = payload.get("type")
            user_id = payload.get("user_id")
            
            # Create notification object
            notification = Notification(
                type=NotificationType(notification_type),
                title=payload.get("title", "Notification"),
                message=payload.get("message", ""),
                user_id=user_id,
                data=payload.get("data", {})
            )
            
            # Send notification to specific user or broadcast
            if user_id == "broadcast":
                await self.broadcast_notification(notification, ConnectionType.TELEGRAM_USER)
            else:
                await self.send_notification_to_user(user_id, notification)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling notification update: {e}")
            return False
    
    async def start_websocket_server(self):
        """Start the WebSocket server."""
        try:
            self.running = True
            
            # Start WebSocket server
            self.websocket_server = await websockets.serve(
                self._handle_websocket_connection,
                self.host,
                self.port
            )
            
            logger.info(f"WebSocket server started on {self.host}:{self.port}")
            
            # Keep the server running
            await self.websocket_server.wait_closed()
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
            raise
    
    async def _handle_websocket_connection(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket connections."""
        connection = None
        
        try:
            # Wait for connection handshake
            handshake = await websocket.recv()
            handshake_data = json.loads(handshake)
            
            connection_type = ConnectionType(handshake_data.get("type", "telegram_user"))
            user_id = handshake_data.get("user_id", "unknown")
            
            # Create connection object
            connection = WebSocketConnection(websocket, connection_type, user_id)
            self.connections[connection.connection_id] = connection
            
            # Add to connection groups
            if connection_type not in self.connection_groups:
                self.connection_groups[connection_type] = set()
            self.connection_groups[connection_type].add(connection.connection_id)
            
            # Update statistics
            self.stats["total_connections"] += 1
            self.stats["active_connections"] += 1
            
            # Send connection confirmation
            await connection.send_message({
                "type": "connection_established",
                "connection_id": connection.connection_id,
                "status": "connected"
            })
            
            logger.info(f"WebSocket connection established: {connection.connection_id} ({connection_type})")
            
            # Handle incoming messages
            async for message in websocket:
                await self._handle_incoming_message(connection, message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"WebSocket connection closed: {connection.connection_id if connection else 'unknown'}")
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
        finally:
            if connection:
                await self._cleanup_connection(connection)
    
    async def _handle_incoming_message(self, connection: WebSocketConnection, message: str):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "ping":
                # Respond to ping
                await connection.send_message({"type": "pong"})
                
            elif message_type == "subscribe":
                # Handle subscription to specific events
                events = data.get("events", [])
                for event in events:
                    if event not in self.event_handlers:
                        self.event_handlers[event] = []
                    self.event_handlers[event].append(connection.connection_id)
                
                await connection.send_message({
                    "type": "subscribed",
                    "events": events
                })
                
            elif message_type == "unsubscribe":
                # Handle unsubscription from events
                events = data.get("events", [])
                for event in events:
                    if event in self.event_handlers:
                        self.event_handlers[event].discard(connection.connection_id)
                
                await connection.send_message({
                    "type": "unsubscribed",
                    "events": events
                })
                
            else:
                # Handle other message types
                await self._process_custom_message(connection, data)
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON message from {connection.connection_id}")
        except Exception as e:
            logger.error(f"Error handling incoming message: {e}")
    
    async def _process_custom_message(self, connection: WebSocketConnection, data: Dict[str, Any]):
        """Process custom message types."""
        # This can be extended to handle specific message types
        logger.debug(f"Processing custom message: {data}")
    
    async def _cleanup_connection(self, connection: WebSocketConnection):
        """Cleanup a closed connection."""
        try:
            # Remove from connections
            if connection.connection_id in self.connections:
                del self.connections[connection.connection_id]
            
            # Remove from connection groups
            if connection.connection_type in self.connection_groups:
                self.connection_groups[connection.connection_type].discard(connection.connection_id)
            
            # Update statistics
            self.stats["active_connections"] = max(0, self.stats["active_connections"] - 1)
            
            logger.info(f"Connection cleaned up: {connection.connection_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up connection: {e}")
    
    async def send_notification_to_user(self, user_id: str, notification: Notification) -> bool:
        """Send a notification to a specific user."""
        try:
            # Find connections for the user
            user_connections = [
                conn for conn in self.connections.values()
                if conn.user_id == user_id and conn.connection_type == ConnectionType.TELEGRAM_USER
            ]
            
            if not user_connections:
                logger.debug(f"No active connections for user {user_id}")
                return False
            
            # Send notification to all user connections
            success_count = 0
            for connection in user_connections:
                if await connection.send_message({
                    "type": "notification",
                    "notification": notification.dict()
                }):
                    success_count += 1
            
            self.stats["notifications_sent"] += success_count
            
            logger.debug(f"Notification sent to {success_count}/{len(user_connections)} connections for user {user_id}")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending notification to user {user_id}: {e}")
            return False
    
    async def broadcast_notification(self, notification: Notification, connection_type: Optional[ConnectionType] = None) -> int:
        """Broadcast a notification to all connections or specific type."""
        try:
            target_connections = []
            
            if connection_type:
                # Send to specific connection type
                if connection_type in self.connection_groups:
                    for conn_id in self.connection_groups[connection_type]:
                        if conn_id in self.connections:
                            target_connections.append(self.connections[conn_id])
            else:
                # Send to all connections
                target_connections = list(self.connections.values())
            
            if not target_connections:
                logger.debug("No target connections for broadcast")
                return 0
            
            # Send notification to all target connections
            success_count = 0
            for connection in target_connections:
                if await connection.send_message({
                    "type": "notification",
                    "notification": notification.dict()
                }):
                    success_count += 1
            
            self.stats["notifications_sent"] += success_count
            
            logger.debug(f"Notification broadcasted to {success_count}/{len(target_connections)} connections")
            return success_count
            
        except Exception as e:
            logger.error(f"Error broadcasting notification: {e}")
            return 0
    
    async def send_message_to_user(self, user_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific user."""
        try:
            # Find connections for the user
            user_connections = [
                conn for conn in self.connections.values()
                if conn.user_id == user_id and conn.connection_type == ConnectionType.TELEGRAM_USER
            ]
            
            if not user_connections:
                logger.debug(f"No active connections for user {user_id}")
                return False
            
            # Send message to all user connections
            success_count = 0
            for connection in user_connections:
                if await connection.send_message(message):
                    success_count += 1
            
            self.stats["messages_sent"] += success_count
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending message to user {user_id}: {e}")
            return False
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        try:
            stats = self.stats.copy()
            
            # Add connection type counts
            type_counts = {}
            for conn_type, connections in self.connection_groups.items():
                type_counts[conn_type.value] = len(connections)
            
            stats["connection_types"] = type_counts
            stats["total_connections"] = len(self.connections)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting connection stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the real-time service."""
        try:
            # Check WebSocket server
            server_status = "running" if self.running and self.websocket_server else "stopped"
            
            # Check message queue
            queue_status = "unknown"
            if self.message_queue:
                queue_health = await self.message_queue.health_check()
                queue_status = queue_health.get("status", "unknown")
            
            # Get connection stats
            connection_stats = await self.get_connection_stats()
            
            return {
                "status": "healthy" if server_status == "running" and queue_status == "healthy" else "unhealthy",
                "websocket_server": server_status,
                "message_queue": queue_status,
                "connections": connection_stats
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def cleanup(self):
        """Cleanup the real-time service."""
        try:
            self.running = False
            
            # Close all connections
            for connection in list(self.connections.values()):
                await connection.close()
            
            # Stop WebSocket server
            if self.websocket_server:
                self.websocket_server.close()
                await self.websocket_server.wait_closed()
            
            # Cleanup message queue
            if self.message_queue:
                await self.message_queue.cleanup()
            
            logger.info("Real-time service cleaned up")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Global real-time service instance
_realtime_service: Optional[RealtimeService] = None


async def get_realtime_service() -> RealtimeService:
    """Get the global real-time service instance."""
    global _realtime_service
    
    if _realtime_service is None:
        from config.settings import get_settings
        settings = get_settings()
        
        _realtime_service = RealtimeService(
            host=settings.websocket_host,
            port=settings.websocket_port
        )
        await _realtime_service.initialize()
    
    return _realtime_service


async def cleanup_realtime_service():
    """Cleanup the global real-time service."""
    global _realtime_service
    
    if _realtime_service:
        await _realtime_service.cleanup()
        _realtime_service = None 