"""
MQTT Client for sending and receiving messages.
Used for control commands and event publishing.
"""

import os
import json
import threading
import asyncio
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger

# Import message queue
from .message_queue import MessageQueue

# Check for MQTT client
MQTT_AVAILABLE = False
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    logger.warning("MQTT client not available. Install paho-mqtt for MQTT support.")

class MQTTClient:
    """Client for MQTT messaging with reliable delivery."""
    
    def __init__(self):
        """Initialize the MQTT client."""
        self.is_connected = False
        self.client = None
        self.callbacks = {}
        self.reconnect_delay = 1  # Initial delay in seconds
        self.max_reconnect_delay = 60  # Maximum delay in seconds
        self.last_reconnect_attempt = None
        self.connection_error = None
        
        # Load configuration from environment
        self.broker = os.getenv("MQTT_BROKER", "localhost")
        self.port = int(os.getenv("MQTT_PORT", "1883"))
        self.topic_prefix = os.getenv("MQTT_TOPIC_PREFIX", "video_analytics")
        self.enabled = os.getenv("MQTT_ENABLED", "False").lower() in ("true", "1", "t")
        self.username = os.getenv("MQTT_USERNAME", None)
        self.password = os.getenv("MQTT_PASSWORD", None)
        
        # Initialize message queue
        self.message_queue = MessageQueue()
        self.publisher_task = None
        
        # Check if MQTT is available
        if not MQTT_AVAILABLE:
            logger.warning("MQTT client not available, functionality will be disabled")
            self.enabled = False
    
    async def start(self) -> bool:
        """Start the MQTT client."""
        if not self.enabled or not MQTT_AVAILABLE:
            logger.info("MQTT is disabled or not available")
            return False
        
        if self.is_connected:
            logger.warning("MQTT client already connected")
            return True
        
        try:
            # Start message queue
            await self.message_queue.start()
            
            # Create MQTT client
            client_id = f"video_analytics_platform_{os.getpid()}"
            self.client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Set credentials if provided
            if self.username and self.password:
                self.client.username_pw_set(self.username, self.password)
            
            # Enable TLS if configured
            if os.getenv("MQTT_USE_TLS", "False").lower() in ("true", "1", "t"):
                self.client.tls_set()
            
            # Start publisher task
            self.publisher_task = asyncio.create_task(self._publisher_loop())
            
            # Connect to broker
            await self._connect_with_retry()
            
            logger.info(f"Connected to MQTT broker {self.broker}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting MQTT client: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the MQTT client."""
        if not self.enabled or not MQTT_AVAILABLE:
            return True
        
        if not self.is_connected and self.client is None:
            return True
        
        try:
            # Stop publisher task
            if self.publisher_task:
                self.publisher_task.cancel()
                try:
                    await self.publisher_task
                except asyncio.CancelledError:
                    pass
            
            # Stop message queue
            await self.message_queue.stop()
            
            # Disconnect and stop loop
            if self.client:
                self.client.disconnect()
                self.client.loop_stop()
            
            self.is_connected = False
            logger.info("Disconnected from MQTT broker")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping MQTT client: {e}")
            return False
    
    async def _connect_with_retry(self):
        """Connect to broker with exponential backoff."""
        while not self.is_connected:
            try:
                # Check if we should wait before retrying
                if self.last_reconnect_attempt:
                    elapsed = (datetime.now() - self.last_reconnect_attempt).total_seconds()
                    if elapsed < self.reconnect_delay:
                        await asyncio.sleep(self.reconnect_delay - elapsed)
                
                self.last_reconnect_attempt = datetime.now()
                
                # Try to connect
                self.client.connect_async(self.broker, self.port, 60)
                self.client.loop_start()
                
                # Wait for connection
                for _ in range(10):
                    if self.is_connected:
                        # Reset reconnection delay on successful connection
                        self.reconnect_delay = 1
                        self.connection_error = None
                        return
                    await asyncio.sleep(0.1)
                
                raise Exception("Connection timeout")
                
            except Exception as e:
                self.connection_error = str(e)
                logger.warning(f"Failed to connect to MQTT broker: {e}")
                
                # Increase reconnection delay with exponential backoff
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                
                # Stop the loop before retrying
                self.client.loop_stop()
    
    async def _publisher_loop(self):
        """Background task for publishing queued messages."""
        while True:
            try:
                # Check connection
                if not self.is_connected:
                    await asyncio.sleep(1)
                    continue
                
                # Get next message from queue
                message = await self.message_queue.dequeue()
                if message:
                    topic, payload = message
                    # Publish message
                    result = self.client.publish(topic, payload)
                    if result.rc != 0:
                        # Failed to publish, requeue message
                        await self.message_queue.enqueue(topic, payload)
                        logger.warning(f"Failed to publish message, requeued: {result.rc}")
                    await asyncio.sleep(0.01)  # Small delay to prevent CPU hogging
                else:
                    await asyncio.sleep(0.1)  # Longer delay when queue is empty
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in publisher loop: {e}")
                await asyncio.sleep(1)
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.is_connected = True
            logger.info("Connected to MQTT broker")
            
            # Subscribe to command topics
            command_topic = f"{self.topic_prefix}/commands/#"
            client.subscribe(command_topic)
            logger.info(f"Subscribed to {command_topic}")
            
            # Resubscribe to all topics
            for topic in self.callbacks.keys():
                client.subscribe(topic)
                logger.info(f"Resubscribed to {topic}")
        else:
            error_messages = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized"
            }
            error = error_messages.get(rc, f"Unknown error code: {rc}")
            logger.error(f"Failed to connect to MQTT broker: {error}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        self.is_connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker, return code: {rc}")
            # Trigger reconnection
            asyncio.create_task(self._connect_with_retry())
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logger.debug(f"Received MQTT message: {topic} - {payload}")
            
            # Parse topic
            topic_parts = topic.split('/')
            if len(topic_parts) < 3:
                logger.warning(f"Invalid topic format: {topic}")
                return
            
            # Extract command or event type
            if topic_parts[1] == "commands":
                command = topic_parts[2]
                # Process command
                self._handle_command(command, payload)
            
            # Call registered callbacks
            if topic in self.callbacks:
                for callback in self.callbacks[topic]:
                    try:
                        callback(topic, payload)
                    except Exception as e:
                        logger.error(f"Error in MQTT callback: {e}")
            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _handle_command(self, command: str, payload: str):
        """Handle incoming command messages."""
        try:
            data = json.loads(payload)
            
            # Handle different commands
            if command == "source":
                # Handle source commands (start, stop, add, remove)
                action = data.get("action")
                source_id = data.get("source_id")
                
                if action and source_id:
                    logger.info(f"Received source command: {action} for {source_id}")
                    # The actual handling would depend on the application structure
                    # Here we just log the command
            
            elif command == "stream":
                # Handle stream commands
                action = data.get("action")
                stream_id = data.get("stream_id")
                
                if action and stream_id:
                    logger.info(f"Received stream command: {action} for {stream_id}")
            
            elif command == "analytics":
                # Handle analytics commands
                action = data.get("action")
                
                if action:
                    logger.info(f"Received analytics command: {action}")
            
            else:
                logger.warning(f"Unknown command: {command}")
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in command payload: {payload}")
        except Exception as e:
            logger.error(f"Error handling command {command}: {e}")
    
    async def publish(self, topic: str, payload: Any) -> bool:
        """Publish a message to a topic."""
        if not self.enabled or not MQTT_AVAILABLE:
            return False
        
        try:
            # Ensure topic has prefix
            if not topic.startswith(f"{self.topic_prefix}/"):
                topic = f"{self.topic_prefix}/{topic}"
            
            # Convert payload to JSON if it's not a string
            if not isinstance(payload, str):
                payload = json.dumps(payload)
            
            # Add to message queue
            return await self.message_queue.enqueue(topic, payload)
            
        except Exception as e:
            logger.error(f"Error publishing to {topic}: {e}")
            return False
    
    def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> bool:
        """Subscribe to a topic with a callback."""
        if not self.enabled or not MQTT_AVAILABLE:
            return False
        
        try:
            # Ensure topic has prefix
            if not topic.startswith(f"{self.topic_prefix}/"):
                topic = f"{self.topic_prefix}/{topic}"
            
            # Register callback
            if topic not in self.callbacks:
                self.callbacks[topic] = []
            self.callbacks[topic].append(callback)
            
            # Subscribe to topic if connected
            if self.is_connected and self.client:
                result = self.client.subscribe(topic)
                if result[0] != 0:
                    logger.error(f"Failed to subscribe to {topic}, return code: {result[0]}")
                    return False
            
            logger.info(f"Subscribed to {topic}")
            return True
            
        except Exception as e:
            logger.error(f"Error subscribing to {topic}: {e}")
            return False
    
    def unsubscribe(self, topic: str, callback: Optional[Callable] = None) -> bool:
        """Unsubscribe from a topic."""
        if not self.enabled or not MQTT_AVAILABLE:
            return False
        
        try:
            # Ensure topic has prefix
            if not topic.startswith(f"{self.topic_prefix}/"):
                topic = f"{self.topic_prefix}/{topic}"
            
            # Remove specific callback if provided
            if callback is not None and topic in self.callbacks:
                self.callbacks[topic] = [cb for cb in self.callbacks[topic] if cb != callback]
                
                # If no callbacks left, unsubscribe from topic
                if not self.callbacks[topic]:
                    if self.is_connected and self.client:
                        result = self.client.unsubscribe(topic)
                        if result[0] != 0:
                            logger.error(f"Failed to unsubscribe from {topic}, return code: {result[0]}")
                            return False
                    
                    del self.callbacks[topic]
            else:
                # Remove all callbacks
                if topic in self.callbacks:
                    del self.callbacks[topic]
                
                # Unsubscribe from topic if connected
                if self.is_connected and self.client:
                    result = self.client.unsubscribe(topic)
                    if result[0] != 0:
                        logger.error(f"Failed to unsubscribe from {topic}, return code: {result[0]}")
                        return False
            
            logger.info(f"Unsubscribed from {topic}")
            return True
            
        except Exception as e:
            logger.error(f"Error unsubscribing from {topic}: {e}")
            return False
    
    async def publish_detection_event(self, source_id: str, detection: Dict) -> bool:
        """Publish a detection event."""
        topic = f"events/detection/{source_id}"
        return await self.publish(topic, detection)
    
    async def publish_status_update(self, status: Dict) -> bool:
        """Publish a status update."""
        topic = "status"
        return await self.publish(topic, status)
    
    def get_connection_status(self) -> Dict:
        """Get current connection status."""
        return {
            "connected": self.is_connected,
            "broker": f"{self.broker}:{self.port}",
            "last_error": self.connection_error,
            "reconnect_delay": self.reconnect_delay,
            "queue_status": self.message_queue.get_queue_size()
        } 