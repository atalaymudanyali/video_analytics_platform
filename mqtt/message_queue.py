"""
Message queue system for MQTT messages.
Provides reliable message delivery with persistence and retry logic.
"""

import os
import json
import asyncio
import threading
import queue
from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
import sqlite3
import pickle

class MessageQueue:
    """Queue system for MQTT messages with persistence."""
    
    def __init__(self, max_size: int = 1000, db_path: str = "data/mqtt_queue.db"):
        """
        Initialize the message queue.
        
        Args:
            max_size: Maximum number of messages in memory queue
            db_path: Path to SQLite database for persistence
        """
        self.max_size = max_size
        self.db_path = db_path
        self.memory_queue = queue.Queue(maxsize=max_size)
        self.lock = threading.Lock()
        self.is_running = False
        self.retry_interval = 5  # seconds
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize the SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        topic TEXT NOT NULL,
                        payload BLOB NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        retries INTEGER DEFAULT 0
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Error initializing message queue database: {e}")
    
    async def start(self) -> bool:
        """Start the message queue processor."""
        if self.is_running:
            return True
        
        try:
            self.is_running = True
            # Load persisted messages
            await self._load_persisted_messages()
            logger.info("Started message queue processor")
            return True
        except Exception as e:
            logger.error(f"Error starting message queue: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the message queue processor."""
        if not self.is_running:
            return True
        
        try:
            self.is_running = False
            # Persist any remaining messages
            await self._persist_memory_queue()
            logger.info("Stopped message queue processor")
            return True
        except Exception as e:
            logger.error(f"Error stopping message queue: {e}")
            return False
    
    async def enqueue(self, topic: str, payload: Any) -> bool:
        """
        Add a message to the queue.
        
        Args:
            topic: MQTT topic
            payload: Message payload (will be JSON serialized)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Serialize payload if needed
            if not isinstance(payload, (str, bytes)):
                payload = json.dumps(payload)
            
            # Try to add to memory queue
            try:
                self.memory_queue.put_nowait((topic, payload))
                return True
            except queue.Full:
                # Memory queue is full, persist to database
                return await self._persist_message(topic, payload)
                
        except Exception as e:
            logger.error(f"Error enqueueing message: {e}")
            return False
    
    async def dequeue(self) -> Optional[tuple]:
        """
        Get the next message from the queue.
        
        Returns:
            Tuple of (topic, payload) or None if queue is empty
        """
        try:
            # Try memory queue first
            try:
                return self.memory_queue.get_nowait()
            except queue.Empty:
                # Try database
                return await self._get_persisted_message()
                
        except Exception as e:
            logger.error(f"Error dequeueing message: {e}")
            return None
    
    async def _persist_message(self, topic: str, payload: Any) -> bool:
        """Persist a message to the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (topic, payload) VALUES (?, ?)",
                    (topic, pickle.dumps(payload))
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error persisting message: {e}")
            return False
    
    async def _persist_memory_queue(self):
        """Persist all messages in memory queue to database."""
        try:
            while not self.memory_queue.empty():
                topic, payload = self.memory_queue.get_nowait()
                await self._persist_message(topic, payload)
        except Exception as e:
            logger.error(f"Error persisting memory queue: {e}")
    
    async def _get_persisted_message(self) -> Optional[tuple]:
        """Get the next message from the database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, topic, payload FROM messages ORDER BY timestamp ASC LIMIT 1"
                )
                row = cursor.fetchone()
                
                if row:
                    msg_id, topic, payload = row
                    # Delete the message
                    cursor.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
                    conn.commit()
                    return topic, pickle.loads(payload)
                
            return None
        except Exception as e:
            logger.error(f"Error getting persisted message: {e}")
            return None
    
    async def _load_persisted_messages(self):
        """Load persisted messages into memory queue."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, topic, payload FROM messages ORDER BY timestamp ASC"
                )
                rows = cursor.fetchall()
                
                for msg_id, topic, payload in rows:
                    try:
                        self.memory_queue.put_nowait((topic, pickle.loads(payload)))
                        # Delete loaded message
                        cursor.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
                    except queue.Full:
                        # Memory queue is full, leave remaining messages in database
                        break
                
                conn.commit()
        except Exception as e:
            logger.error(f"Error loading persisted messages: {e}")
    
    def get_queue_size(self) -> Dict[str, int]:
        """
        Get current queue sizes.
        
        Returns:
            Dictionary with memory and persistent queue sizes
        """
        try:
            memory_size = self.memory_queue.qsize()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM messages")
                persistent_size = cursor.fetchone()[0]
            
            return {
                "memory_queue": memory_size,
                "persistent_queue": persistent_size,
                "total": memory_size + persistent_size
            }
        except Exception as e:
            logger.error(f"Error getting queue size: {e}")
            return {"memory_queue": 0, "persistent_queue": 0, "total": 0} 