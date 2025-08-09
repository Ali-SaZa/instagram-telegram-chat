"""
Database connection manager for Instagram-Telegram chat integration.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, OperationFailure
from pymongo import ASCENDING, DESCENDING

from config.settings import get_settings
from .models import INDEXES

logger = logging.getLogger(__name__)


class DatabaseConnectionManager:
    """Manages MongoDB database connections with connection pooling and error handling."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self._connection_lock = asyncio.Lock()
        self._is_connected = False
        self._connection_attempts = 0
        self._max_connection_attempts = 3
        
    async def connect(self) -> bool:
        """Establish connection to MongoDB."""
        async with self._connection_lock:
            if self._is_connected and self.client:
                return True
            
            try:
                logger.info("Connecting to MongoDB...")
                
                # Create MongoDB client with connection pooling
                self.client = AsyncIOMotorClient(
                    self.settings.database.mongodb_uri,
                    maxPoolSize=self.settings.database.mongodb_max_pool_size,
                    minPoolSize=self.settings.database.mongodb_min_pool_size,
                    maxIdleTimeMS=self.settings.database.mongodb_max_idle_time,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=30000,
                    retryWrites=True,
                    retryReads=True
                )
                
                # Test connection
                await self.client.admin.command('ping')
                
                # Get database
                self.database = self.client[self.settings.database.mongodb_database]
                
                # Set up indexes
                await self._setup_indexes()
                
                self._is_connected = True
                self._connection_attempts = 0
                logger.info("Successfully connected to MongoDB")
                
                return True
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                self._connection_attempts += 1
                logger.error(f"Failed to connect to MongoDB (attempt {self._connection_attempts}): {e}")
                
                if self._connection_attempts >= self._max_connection_attempts:
                    logger.error("Max connection attempts reached. Giving up.")
                    return False
                
                # Wait before retrying
                await asyncio.sleep(2 ** self._connection_attempts)
                return await self.connect()
                
            except Exception as e:
                logger.error(f"Unexpected error connecting to MongoDB: {e}")
                return False
    
    async def disconnect(self):
        """Close MongoDB connection."""
        async with self._connection_lock:
            if self.client:
                try:
                    self.client.close()
                    logger.info("MongoDB connection closed")
                except Exception as e:
                    logger.error(f"Error closing MongoDB connection: {e}")
                finally:
                    self.client = None
                    self.database = None
                    self._is_connected = False
    
    async def _setup_indexes(self):
        """Set up database indexes for performance optimization."""
        try:
            logger.info("Setting up database indexes...")
            
            for collection_name, index_specs in INDEXES.items():
                collection = self.database[collection_name]
                
                # Get existing indexes
                existing_indexes = await collection.list_indexes()
                existing_index_names = [idx['name'] for idx in existing_indexes]
                
                for index_spec in index_specs:
                    if len(index_spec) == 2:
                        fields, options = index_spec
                    else:
                        fields = index_spec[0]
                        options = {}
                    
                    # Create index name from fields
                    index_name = "_".join([f"{field}_{direction}" for field, direction in fields])
                    
                    if index_name not in existing_index_names:
                        try:
                            await collection.create_index(fields, **options)
                            logger.info(f"Created index {index_name} on collection {collection_name}")
                        except Exception as e:
                            logger.warning(f"Failed to create index {index_name}: {e}")
                    else:
                        logger.debug(f"Index {index_name} already exists on collection {collection_name}")
            
            logger.info("Database indexes setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up database indexes: {e}")
            raise
    
    async def get_collection(self, collection_name: str):
        """Get a database collection."""
        if not self._is_connected:
            await self.connect()
        
        if not self.database:
            raise ConnectionError("Database not connected")
        
        return self.database[collection_name]
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        try:
            if not self._is_connected or not self.client:
                return {
                    "status": "disconnected",
                    "error": "Database not connected"
                }
            
            # Test connection with ping
            start_time = asyncio.get_event_loop().time()
            await self.client.admin.command('ping')
            ping_time = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Get database stats
            db_stats = await self.database.command("dbStats")
            
            return {
                "status": "healthy",
                "ping_time_ms": round(ping_time, 2),
                "database_name": self.database.name,
                "collections": db_stats.get("collections", 0),
                "data_size_mb": round(db_stats.get("dataSize", 0) / (1024 * 1024), 2),
                "storage_size_mb": round(db_stats.get("storageSize", 0) / (1024 * 1024), 2),
                "indexes": db_stats.get("indexes", 0)
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def ensure_connection(self):
        """Ensure database connection is active."""
        if not self._is_connected:
            await self.connect()
        
        if not self._is_connected:
            raise ConnectionError("Failed to establish database connection")
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager for database connections."""
        try:
            await self.ensure_connection()
            yield self
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            # Don't disconnect here as other operations might need the connection
            pass
    
    async def execute_transaction(self, callback, session=None):
        """Execute a database transaction."""
        if not self._is_connected:
            await self.connect()
        
        if not self.database:
            raise ConnectionError("Database not connected")
        
        try:
            async with await self.client.start_session() as session:
                async with session.start_transaction():
                    result = await callback(session)
                    await session.commit_transaction()
                    return result
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            if session:
                await session.abort_transaction()
            raise
    
    async def get_database_info(self) -> Dict[str, Any]:
        """Get database information and statistics."""
        try:
            if not self._is_connected:
                return {"error": "Database not connected"}
            
            # Get database stats
            db_stats = await self.database.command("dbStats")
            
            # Get collection stats
            collections = await self.database.list_collection_names()
            collection_stats = {}
            
            for collection_name in collections:
                try:
                    stats = await self.database.command("collStats", collection_name)
                    collection_stats[collection_name] = {
                        "count": stats.get("count", 0),
                        "size_mb": round(stats.get("size", 0) / (1024 * 1024), 2),
                        "avg_obj_size": stats.get("avgObjSize", 0),
                        "storage_size_mb": round(stats.get("storageSize", 0) / (1024 * 1024), 2),
                        "indexes": stats.get("nindexes", 0)
                    }
                except Exception as e:
                    collection_stats[collection_name] = {"error": str(e)}
            
            return {
                "database_name": self.database.name,
                "collections": collections,
                "database_stats": {
                    "collections": db_stats.get("collections", 0),
                    "data_size_mb": round(db_stats.get("dataSize", 0) / (1024 * 1024), 2),
                    "storage_size_mb": round(db_stats.get("storageSize", 0) / (1024 * 1024), 2),
                    "indexes": db_stats.get("indexes", 0),
                    "objects": db_stats.get("objects", 0)
                },
                "collection_stats": collection_stats
            }
            
        except Exception as e:
            return {"error": str(e)}


# Global database manager instance
db_manager = DatabaseConnectionManager()


async def get_mongodb_manager():
    """Get the database manager instance."""
    await db_manager.ensure_connection()
    return db_manager


async def get_database() -> AsyncIOMotorDatabase:
    """Get the database instance."""
    await db_manager.ensure_connection()
    return db_manager.database


async def get_collection(collection_name: str):
    """Get a database collection."""
    return await db_manager.get_collection(collection_name)


async def close_database():
    """Close the database connection."""
    await db_manager.disconnect()


# Initialize database connection on module import
async def initialize_database():
    """Initialize database connection."""
    try:
        await db_manager.connect()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


# Cleanup function for graceful shutdown
async def cleanup_database():
    """Cleanup database resources."""
    await db_manager.disconnect()
    logger.info("Database cleanup completed") 