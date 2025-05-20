#!/usr/bin/env python3
"""
Simple client viewer for the Video Analytics Platform.
Can display multiple video streams with controls.
"""

import os
import sys
import cv2
import numpy as np
import requests
import threading
import time
import argparse
from typing import Dict, List, Optional
import json
import urllib.parse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import MQTT client if available
MQTT_AVAILABLE = False
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    print("MQTT client not available. Install paho-mqtt for MQTT support.")

class Stream:
    """Class representing a video stream."""
    
    def __init__(self, stream_id: str, url: str, name: Optional[str] = None):
        """
        Initialize a stream.
        
        Args:
            stream_id: Unique identifier for the stream
            url: URL of the stream
            name: Display name for the stream
        """
        self.stream_id = stream_id
        self.url = url
        self.name = name or stream_id
        self.frame = None
        self.last_update = 0
        self.is_active = True
        self.lock = threading.Lock()
        
        # FPS measurement
        self.fps = 0
        self.frame_count = 0
        self.fps_start_time = time.time()
    
    def update_frame(self, frame: np.ndarray):
        """Update the stream's frame."""
        with self.lock:
            self.frame = frame
            self.last_update = time.time()
            
            # Update FPS
            self.frame_count += 1
            elapsed = time.time() - self.fps_start_time
            if elapsed >= 1.0:
                self.fps = self.frame_count / elapsed
                self.frame_count = 0
                self.fps_start_time = time.time()
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame."""
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
    
    def is_stale(self, timeout: float = 5.0) -> bool:
        """Check if the stream is stale (no updates for a while)."""
        return time.time() - self.last_update > timeout


class VideoViewer:
    """Video viewer for the analytics platform."""
    
    def __init__(self, api_url: str, mqtt_enabled: bool = False):
        """
        Initialize the video viewer.
        
        Args:
            api_url: URL of the API server
            mqtt_enabled: Whether to enable MQTT
        """
        self.api_url = api_url.rstrip('/')
        self.mqtt_enabled = mqtt_enabled and MQTT_AVAILABLE
        self.mqtt_client = None
        self.mqtt_connected = False
        
        self.streams: Dict[str, Stream] = {}
        self.selected_stream_id = None
        self.is_running = False
        self.show_stats = True
        self.show_detections = True
        
        # Layout options
        self.layout_mode = "grid"  # grid or single
        self.grid_columns = 2
        
        # Window and control state
        self.window_name = "Video Analytics Platform"
        self.window_created = False
        self.fullscreen = False
        
        # Analytics data
        self.analytics_data = {}
        self.last_analytics_update = 0
    
    def start(self):
        """Start the video viewer."""
        if self.is_running:
            print("Video viewer already running")
            return
        
        # Create window
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 1280, 720)
        self.window_created = True
        
        # Connect to MQTT if enabled
        if self.mqtt_enabled:
            self._connect_mqtt()
        
        # Start background thread for API polling
        self.api_thread = threading.Thread(target=self._api_polling_thread)
        self.api_thread.daemon = True
        self.api_thread.start()
        
        # Start main loop
        self.is_running = True
        self._main_loop()
    
    def stop(self):
        """Stop the video viewer."""
        self.is_running = False
        
        # Disconnect MQTT if connected
        if self.mqtt_client is not None:
            self.mqtt_client.disconnect()
        
        # Close window
        if self.window_created:
            cv2.destroyAllWindows()
    
    def _connect_mqtt(self):
        """Connect to MQTT broker."""
        try:
            # Get MQTT configuration from API
            response = requests.get(f"{self.api_url}/status")
            if response.status_code != 200:
                print(f"Failed to get status from API: {response.status_code}")
                return
            
            # Create MQTT client
            client_id = f"video_viewer_{os.getpid()}"
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.on_message = self._on_mqtt_message
            
            # Get broker information (in a real app, this would come from config)
            broker = os.getenv("MQTT_BROKER", "localhost")
            port = int(os.getenv("MQTT_PORT", "1883"))
            
            # Connect to broker
            self.mqtt_client.connect_async(broker, port, 60)
            
            # Start MQTT loop in a separate thread
            self.mqtt_client.loop_start()
            
            print(f"Connecting to MQTT broker {broker}:{port}")
            
        except Exception as e:
            print(f"Error connecting to MQTT: {e}")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            self.mqtt_connected = True
            print("Connected to MQTT broker")
            
            # Subscribe to topics
            topic_prefix = os.getenv("MQTT_TOPIC_PREFIX", "video_analytics")
            client.subscribe(f"{topic_prefix}/events/detection/#")
            client.subscribe(f"{topic_prefix}/status")
            
            print(f"Subscribed to MQTT topics: {topic_prefix}/events/detection/#, {topic_prefix}/status")
        else:
            print(f"Failed to connect to MQTT broker, return code: {rc}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        self.mqtt_connected = False
        if rc != 0:
            print(f"Unexpected disconnection from MQTT broker, return code: {rc}")
        else:
            print("Disconnected from MQTT broker")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Parse topic
            topic_parts = topic.split('/')
            if len(topic_parts) < 3:
                return
            
            # Handle detection events
            if topic_parts[1] == "events" and topic_parts[2] == "detection":
                source_id = topic_parts[3] if len(topic_parts) > 3 else None
                if source_id:
                    try:
                        detection = json.loads(payload)
                        # Update analytics data
                        if source_id not in self.analytics_data:
                            self.analytics_data[source_id] = []
                        
                        # Add timestamp
                        detection['timestamp'] = time.time()
                        
                        # Add to analytics data (keep last 100 detections)
                        self.analytics_data[source_id].append(detection)
                        if len(self.analytics_data[source_id]) > 100:
                            self.analytics_data[source_id].pop(0)
                        
                        self.last_analytics_update = time.time()
                    except json.JSONDecodeError:
                        print(f"Invalid JSON in detection payload: {payload}")
            
            # Handle status updates
            elif topic_parts[1] == "status":
                try:
                    status = json.loads(payload)
                    # Update status information
                    print(f"Received status update: {status}")
                except json.JSONDecodeError:
                    print(f"Invalid JSON in status payload: {payload}")
            
        except Exception as e:
            print(f"Error processing MQTT message: {e}")
    
    def _api_polling_thread(self):
        """Background thread for polling the API."""
        while self.is_running:
            try:
                # Get sources from API
                response = requests.get(f"{self.api_url}/sources")
                if response.status_code == 200:
                    sources = response.json()
                    
                    # Update streams based on sources
                    for source in sources:
                        source_id = source['id']
                        if source_id not in self.streams:
                            # Add new stream
                            stream_url = f"{self.api_url}/sources/{source_id}/frame?annotate={self.show_detections}"
                            self.streams[source_id] = Stream(source_id, stream_url, source_id)
                            
                            if self.selected_stream_id is None:
                                self.selected_stream_id = source_id
                    
                    # Remove streams that no longer exist
                    stream_ids = [source['id'] for source in sources]
                    for stream_id in list(self.streams.keys()):
                        if stream_id not in stream_ids:
                            del self.streams[stream_id]
                            
                            if self.selected_stream_id == stream_id:
                                self.selected_stream_id = next(iter(self.streams)) if self.streams else None
                
                # Get analytics data
                if time.time() - self.last_analytics_update >= 5.0:
                    response = requests.get(f"{self.api_url}/analytics")
                    if response.status_code == 200:
                        self.analytics_data = response.json()
                        self.last_analytics_update = time.time()
                
                # Update stream frames
                for stream_id, stream in self.streams.items():
                    if stream.is_active and (self.layout_mode == "grid" or stream_id == self.selected_stream_id):
                        try:
                            # Update query parameter for annotation
                            url_parts = list(urllib.parse.urlparse(stream.url))
                            query = dict(urllib.parse.parse_qsl(url_parts[4]))
                            query['annotate'] = str(self.show_detections).lower()
                            url_parts[4] = urllib.parse.urlencode(query)
                            url = urllib.parse.urlunparse(url_parts)
                            
                            # Get frame
                            response = requests.get(url, stream=True, timeout=1.0)
                            if response.status_code == 200:
                                # Read image data
                                img_array = np.frombuffer(response.content, dtype=np.uint8)
                                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                                
                                # Update stream
                                stream.update_frame(frame)
                            else:
                                print(f"Failed to get frame for {stream_id}: {response.status_code}")
                        except requests.exceptions.RequestException as e:
                            print(f"Error getting frame for {stream_id}: {e}")
                
                # Sleep to avoid hammering the API
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error in API polling thread: {e}")
                time.sleep(1.0)
    
    def _main_loop(self):
        """Main viewer loop."""
        while self.is_running and self.window_created:
            # Create display frame
            display_frame = self._create_display_frame()
            
            if display_frame is not None:
                # Display frame
                cv2.imshow(self.window_name, display_frame)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            self._handle_key(key)
    
    def _create_display_frame(self) -> Optional[np.ndarray]:
        """Create the display frame."""
        if not self.streams:
            # No streams available
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            text = "No streams available"
            font = cv2.FONT_HERSHEY_SIMPLEX
            textsize = cv2.getTextSize(text, font, 1, 2)[0]
            textX = (frame.shape[1] - textsize[0]) // 2
            textY = (frame.shape[0] + textsize[1]) // 2
            cv2.putText(frame, text, (textX, textY), font, 1, (255, 255, 255), 2)
            return frame
        
        if self.layout_mode == "single" and self.selected_stream_id:
            # Single stream view
            stream = self.streams.get(self.selected_stream_id)
            if stream is None:
                return None
            
            frame = stream.get_frame()
            if frame is None:
                return None
            
            # Add info overlay if enabled
            if self.show_stats:
                self._add_info_overlay(frame, stream)
            
            return frame
        else:
            # Grid view
            active_streams = [s for s in self.streams.values() if s.is_active]
            if not active_streams:
                return None
            
            # Calculate grid dimensions
            n_streams = len(active_streams)
            cols = min(self.grid_columns, n_streams)
            rows = (n_streams + cols - 1) // cols
            
            # Get a frame to determine size
            sample_frame = None
            for stream in active_streams:
                sample_frame = stream.get_frame()
                if sample_frame is not None:
                    break
            
            if sample_frame is None:
                return None
            
            # Calculate cell size
            cell_width = sample_frame.shape[1] // cols
            cell_height = sample_frame.shape[0] // rows
            
            # Create grid frame
            grid_width = cell_width * cols
            grid_height = cell_height * rows
            grid_frame = np.zeros((grid_height, grid_width, 3), dtype=np.uint8)
            
            # Add each stream to the grid
            for i, stream in enumerate(active_streams):
                frame = stream.get_frame()
                if frame is not None:
                    # Resize frame to fit cell
                    frame = cv2.resize(frame, (cell_width, cell_height))
                    
                    # Add info overlay if enabled
                    if self.show_stats:
                        self._add_info_overlay(frame, stream, small=True)
                    
                    # Calculate position in grid
                    row = i // cols
                    col = i % cols
                    
                    # Add to grid
                    y_start = row * cell_height
                    y_end = y_start + cell_height
                    x_start = col * cell_width
                    x_end = x_start + cell_width
                    
                    grid_frame[y_start:y_end, x_start:x_end] = frame
                    
                    # Highlight selected stream
                    if stream.stream_id == self.selected_stream_id:
                        cv2.rectangle(grid_frame, (x_start, y_start), (x_end, y_end), (0, 255, 0), 2)
            
            return grid_frame
    
    def _add_info_overlay(self, frame: np.ndarray, stream: Stream, small: bool = False):
        """Add information overlay to frame."""
        # Get stream info
        name = stream.name
        fps = f"{stream.fps:.1f} FPS"
        
        # Get analytics data
        analytics_info = ""
        if stream.stream_id in self.analytics_data:
            data = self.analytics_data[stream.stream_id]
            if isinstance(data, dict) and 'detection_count' in data:
                analytics_info = f"Detections: {data['detection_count']}"
                
                if 'class_counts' in data:
                    class_counts = []
                    for cls, count in data['class_counts'].items():
                        class_counts.append(f"{cls}: {count}")
                    
                    if class_counts:
                        analytics_info += f" ({', '.join(class_counts)})"
        
        # Add timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Scale for small overlay
        scale = 0.5 if small else 1.0
        thickness = 1 if small else 2
        
        # Add stream name
        cv2.putText(frame, name, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 255, 0), thickness)
        
        # Add FPS
        cv2.putText(frame, fps, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 255, 0), thickness)
        
        # Add analytics info if available
        if analytics_info:
            y_pos = 90
            for line in analytics_info.split('\n'):
                cv2.putText(frame, line, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 255, 0), thickness)
                y_pos += 30 if small else 30
        
        # Add timestamp at bottom
        text_size = cv2.getTextSize(timestamp, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0]
        cv2.putText(frame, timestamp, (frame.shape[1] - text_size[0] - 10, frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 255, 0), thickness)
    
    def _handle_key(self, key: int):
        """Handle keyboard input."""
        if key == ord('q'):
            # Quit
            self.is_running = False
        
        elif key == ord('f'):
            # Toggle fullscreen
            self.fullscreen = not self.fullscreen
            if self.fullscreen:
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
        
        elif key == ord('g'):
            # Toggle layout mode
            self.layout_mode = "grid" if self.layout_mode == "single" else "single"
        
        elif key == ord('s'):
            # Toggle stats overlay
            self.show_stats = not self.show_stats
        
        elif key == ord('d'):
            # Toggle detection overlay
            self.show_detections = not self.show_detections
        
        elif key == ord('c'):
            # Change grid columns
            self.grid_columns = self.grid_columns % 4 + 1
        
        elif key in [ord(str(i)) for i in range(1, 10)]:
            # Select stream by number
            idx = int(chr(key)) - 1
            if idx < len(self.streams):
                self.selected_stream_id = list(self.streams.keys())[idx]
        
        elif key in [ord(' '), 13]:  # Space or Enter
            # Switch to single view of selected stream
            if self.layout_mode == "grid" and self.selected_stream_id:
                self.layout_mode = "single"
        
        elif key == 27:  # ESC
            # Go back to grid view
            if self.layout_mode == "single":
                self.layout_mode = "grid"
            else:
                self.is_running = False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Video Analytics Platform Client Viewer")
    parser.add_argument("--api", type=str, default="http://localhost:8000", help="API server URL")
    parser.add_argument("--mqtt", action="store_true", help="Enable MQTT integration")
    args = parser.parse_args()
    
    viewer = VideoViewer(args.api, args.mqtt)
    try:
        viewer.start()
    except KeyboardInterrupt:
        pass
    finally:
        viewer.stop()


if __name__ == "__main__":
    main() 