
import os
import sys
import cv2
import json
import asyncio
import threading
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime
from loguru import logger
import paho.mqtt.client as mqtt

class VideoClient:

    
    def __init__(self, source_id: str, broker_host: str = "localhost", broker_port: int = 1883):
        """
        Initialize the video client.
        
        Args:
            source_id: ID of the video source to connect to
            broker_host: MQTT broker hostname
            broker_port: MQTT broker port
        """
        self.source_id = source_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.mqtt_client = None
        self.is_connected = False
        self.is_running = False
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.detections = []
        self.detection_lock = threading.Lock()
        self.display_thread = None
        self.last_frame_time = None
        self.fps = 0
        
        # Window name for display
        self.window_name = f"Video Analytics - {source_id}"
        
        # Configure logging
        logger.remove()
        logger.add(sys.stderr, level="INFO")
        logger.add(f"logs/client_{source_id}.log", rotation="10 MB", level="DEBUG")
    
    async def start(self) -> bool:
        """Start the video client."""
        if self.is_running:
            logger.warning("Client already running")
            return True
        
        try:
            # Connect to MQTT broker
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_message = self._on_message
            self.mqtt_client.on_disconnect = self._on_disconnect
            
            # Connect to broker
            self.mqtt_client.connect_async(self.broker_host, self.broker_port, 60)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            for _ in range(10):
                if self.is_connected:
                    break
                await asyncio.sleep(0.1)
            
            if not self.is_connected:
                logger.error("Failed to connect to MQTT broker")
                self.mqtt_client.loop_stop()
                return False
            
            # Subscribe to topics
            self.mqtt_client.subscribe(f"video_analytics/events/detection/{self.source_id}")
            self.mqtt_client.subscribe(f"video_analytics/sources/{self.source_id}/status")
            
            # Start display thread
            self.is_running = True
            self.display_thread = threading.Thread(target=self._display_loop)
            self.display_thread.daemon = True
            self.display_thread.start()
            
            logger.info("Started video client")
            return True
            
        except Exception as e:
            logger.error(f"Error starting video client: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the video client."""
        if not self.is_running:
            return True
        
        try:
            # Stop display thread
            self.is_running = False
            if self.display_thread and self.display_thread.is_alive():
                self.display_thread.join(timeout=3.0)
            
            # Disconnect from MQTT
            if self.mqtt_client:
                self.mqtt_client.disconnect()
                self.mqtt_client.loop_stop()
            
            # Close OpenCV windows
            cv2.destroyAllWindows()
            
            logger.info("Stopped video client")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping video client: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.is_connected = True
            logger.info("Connected to MQTT broker")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        self.is_connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode('utf-8'))
            
            if "detection" in topic:
                # Update detections
                with self.detection_lock:
                    self.detections = payload.get("detections", [])
            
            elif "status" in topic:
                # Handle status updates
                logger.debug(f"Received status update: {payload}")
            
        except json.JSONDecodeError:
            logger.error("Invalid JSON in message payload")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _display_loop(self):
        """Main display loop."""
        try:
            # Create window
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            
            frame_count = 0
            start_time = datetime.now()
            
            while self.is_running:
                try:
                    # Get latest frame
                    with self.frame_lock:
                        if self.current_frame is None:
                            # No frame available yet
                            frame = np.zeros((480, 640, 3), dtype=np.uint8)
                            cv2.putText(frame, "Waiting for video...", (50, 240),
                                      cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                        else:
                            frame = self.current_frame.copy()
                    
                    # Get current detections
                    with self.detection_lock:
                        current_detections = self.detections.copy()
                    
                    # Draw detections
                    for detection in current_detections:
                        box = detection.get("box", [0, 0, 0, 0])
                        confidence = detection.get("confidence", 0)
                        class_name = detection.get("class_name", "unknown")
                        
                        # Draw bounding box
                        x1, y1, x2, y2 = map(int, box)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                        # Draw label
                        label = f"{class_name}: {confidence:.2f}"
                        cv2.putText(frame, label, (x1, y1 - 10),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    
                    # Calculate and display FPS
                    frame_count += 1
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= 1.0:
                        self.fps = frame_count / elapsed
                        frame_count = 0
                        start_time = datetime.now()
                    
                    # Add FPS counter
                    cv2.putText(frame, f"FPS: {self.fps:.1f}", (10, 30),
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                    
                    # Display frame
                    cv2.imshow(self.window_name, frame)
                    
                    # Check for exit
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:  # ESC key
                        self.is_running = False
                        break
                    
                except Exception as e:
                    logger.error(f"Error in display loop: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"Error in display thread: {e}")
        finally:
            cv2.destroyAllWindows()
    
    async def update_frame(self, frame: np.ndarray):
        """
        Update the current frame.
        
        Args:
            frame: New frame to display
        """
        try:
            with self.frame_lock:
                self.current_frame = frame.copy()
                self.last_frame_time = datetime.now()
        except Exception as e:
            logger.error(f"Error updating frame: {e}")
    
    def get_status(self) -> Dict:
        """Get current client status."""
        return {
            "source_id": self.source_id,
            "connected": self.is_connected,
            "running": self.is_running,
            "fps": self.fps,
            "detection_count": len(self.detections),
            "last_frame_time": self.last_frame_time.isoformat() if self.last_frame_time else None
        }

async def main():
    """Main function for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenCV Video Analytics Client")
    parser.add_argument("--source", required=True, help="Video source ID")
    parser.add_argument("--broker", default="localhost", help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    args = parser.parse_args()
    
    # Create and start client
    client = VideoClient(args.source, args.broker, args.port)
    if not await client.start():
        logger.error("Failed to start client")
        return
    
    try:
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main()) 