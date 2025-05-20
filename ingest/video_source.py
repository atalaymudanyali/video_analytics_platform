"""
Video Source Manager for handling multiple video sources.
Supports webcams, RTSP streams, and other GStreamer-compatible sources.
"""

import os
import asyncio
import cv2
import gi
import numpy as np
import threading
from typing import Dict, List, Optional, Tuple, Union
from loguru import logger

# Import GStreamer
GSTREAMER_AVAILABLE = False
try:
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib
    Gst.init(None)
    GSTREAMER_AVAILABLE = True
    logger.info("GStreamer initialized successfully")
except (ImportError, ValueError) as e:
    logger.warning(f"GStreamer Python bindings not available: {e}. Fallback to OpenCV only.")
except Exception as e:
    logger.error(f"Error initializing GStreamer: {e}. Fallback to OpenCV only.")

class VideoSource:
    """Class representing a single video source (webcam, IP camera, etc.)"""
    
    def __init__(self, source_id: str, source_url: str, width: int = 640, height: int = 480):
        """
        Initialize a video source.
        
        Args:
            source_id: Unique identifier for this source
            source_url: URL/path to the video source
            width: Desired width for processing
            height: Desired height for processing
        """
        self.source_id = source_id
        self.source_url = source_url
        self.width = width
        self.height = height
        self.is_running = False
        self.latest_frame = None
        self.frame_count = 0
        self.fps = 0
        self.lock = threading.Lock()
        self.pipeline = None
        self.loop = None
        self._glib_loop = None
        self._glib_thread = None
        
        # Detect source type
        if source_url.startswith(('rtsp://', 'http://', 'https://')):
            self.source_type = 'network'
        elif source_url.startswith(('v4l2://', '/dev/video')):
            self.source_type = 'webcam'
            # Handle "/dev/videoX" format by converting to v4l2
            if source_url.startswith('/dev/video'):
                self.source_url = f"v4l2://{source_url}"
        elif source_url.startswith(('file://', '/')):
            self.source_type = 'file'
        else:
            # Try to interpret as a device index (0, 1, etc.)
            try:
                self.device_index = int(source_url)
                self.source_type = 'webcam'
                self.source_url = f"v4l2:///dev/video{self.device_index}"
            except ValueError:
                self.source_type = 'unknown'
    
    async def start(self) -> bool:
        """Start capturing from the video source."""
        if self.is_running:
            logger.warning(f"Video source {self.source_id} already running")
            return True
            
        if GSTREAMER_AVAILABLE:
            try:
                return await self._start_gstreamer()
            except Exception as e:
                logger.error(f"GStreamer start failed: {e}. Falling back to OpenCV.")
                return await self._start_opencv()
        else:
            return await self._start_opencv()
    
    async def _start_gstreamer(self) -> bool:
        """Start capturing using GStreamer."""
        try:
            if self.source_type == 'webcam':
                # V4L2 source pipeline
                pipeline_str = (
                    f"v4l2src device={self.source_url.replace('v4l2://', '')} ! "
                    f"video/x-raw,width={self.width},height={self.height} ! "
                    f"videoconvert ! video/x-raw,format=RGB ! "
                    f"appsink name=sink emit-signals=true"
                )
            elif self.source_type == 'network':
                # RTSP source pipeline
                pipeline_str = (
                    f"rtspsrc location={self.source_url} latency=100 ! "
                    f"rtph264depay ! h264parse ! avdec_h264 ! "
                    f"videoscale ! video/x-raw,width={self.width},height={self.height} ! "
                    f"videoconvert ! video/x-raw,format=RGB ! "
                    f"appsink name=sink emit-signals=true"
                )
            elif self.source_type == 'file':
                # Proper file source pipeline with filesrc
                file_path = self.source_url
                if file_path.startswith('file://'):
                    file_path = file_path[7:]  # Remove file:// prefix
                
                logger.info(f"Opening local file: {file_path}")
                
                pipeline_str = (
                    f"filesrc location=\"{file_path}\" ! "
                    f"decodebin ! videoscale ! videoconvert ! "
                    f"video/x-raw,width={self.width},height={self.height},format=RGB ! "
                    f"queue max-size-buffers=2 ! videorate ! video/x-raw,framerate=30/1 ! "
                    f"appsink name=sink emit-signals=true max-buffers=2 drop=true sync=true"
                )
            else:
                # Generic pipeline with decodebin
                # Make sure we have a proper URI
                if not self.source_url.startswith(('file://', 'http://', 'https://', 'rtsp://')):
                    # If it's a local file path, add file:// prefix
                    if os.path.exists(self.source_url):
                        uri = f"file://{self.source_url}"
                    else:
                        uri = self.source_url
                else:
                    uri = self.source_url
                    
                pipeline_str = (
                    f"uridecodebin uri=\"{uri}\" ! "
                    f"videoscale ! video/x-raw,width={self.width},height={self.height} ! "
                    f"videoconvert ! video/x-raw,format=RGB ! "
                    f"appsink name=sink emit-signals=true"
                )
            
            logger.info(f"Starting GStreamer pipeline for source {self.source_id}: {pipeline_str}")
            
            # Create GStreamer pipeline
            self.pipeline = Gst.parse_launch(pipeline_str)
            sink = self.pipeline.get_by_name('sink')
            sink.connect('new-sample', self._on_new_sample)
            
            # Start pipeline
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error(f"Failed to start GStreamer pipeline for {self.source_id}")
                return False
            
            # Create and start GLib main loop in a separate thread
            self._glib_loop = GLib.MainLoop()
            self._glib_thread = threading.Thread(target=self._run_glib_loop)
            self._glib_thread.daemon = True
            self._glib_thread.start()
                
            self.is_running = True
            logger.info(f"Started GStreamer pipeline for source {self.source_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting GStreamer pipeline: {e}")
            return False
    
    def _run_glib_loop(self):
        """Run the GLib main loop with error handling."""
        try:
            self._glib_loop.run()
        except Exception as e:
            logger.error(f"Error in GLib main loop: {e}")
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
    
    def _on_new_sample(self, sink):
        """Callback for new GStreamer sample."""
        try:
            sample = sink.emit('pull-sample')
            if sample:
                buf = sample.get_buffer()
                caps = sample.get_caps()
                
                # Get buffer data
                success, map_info = buf.map(Gst.MapFlags.READ)
                if success:
                    # Get image dimensions from caps
                    structure = caps.get_structure(0)
                    width = structure.get_value('width')
                    height = structure.get_value('height')
                    
                    # Create numpy array from buffer data
                    frame = np.ndarray(
                        shape=(height, width, 3),
                        dtype=np.uint8,
                        buffer=map_info.data
                    )
                    
                    # Update latest frame
                    with self.lock:
                        self.latest_frame = frame.copy()
                        self.frame_count += 1
                    
                    buf.unmap(map_info)
                    return Gst.FlowReturn.OK
            else:
                # End of stream, restart pipeline for looping
                if self.source_type == 'file':
                    self.pipeline.seek_simple(
                        Gst.Format.TIME,
                        Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                        0
                    )
                    return Gst.FlowReturn.OK
            
            return Gst.FlowReturn.ERROR
        except Exception as e:
            logger.error(f"Error in GStreamer sample callback: {e}")
            return Gst.FlowReturn.ERROR
    
    async def _start_opencv(self) -> bool:
        """Start capturing using OpenCV as fallback."""
        try:
            # Try to convert GStreamer URL to OpenCV compatible format
            if self.source_type == 'webcam' and self.source_url.startswith('v4l2://'):
                source_url = int(self.source_url.replace('v4l2:///', '').replace('/dev/video', ''))
            else:
                source_url = self.source_url
            
            # Create OpenCV capture object
            self.cap = cv2.VideoCapture(source_url)
            if not self.cap.isOpened():
                logger.error(f"Failed to open video source {self.source_id}")
                return False
            
            # Set properties if possible
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            # Start capture thread
            self.is_running = True
            self.capture_thread = threading.Thread(target=self._opencv_capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            logger.info(f"Started OpenCV capture for source {self.source_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting OpenCV capture: {e}")
            return False
    
    def _opencv_capture_loop(self):
        """Background thread for OpenCV capture."""
        last_time = cv2.getTickCount()
        frame_counter = 0
        
        while self.is_running:
            try:
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.latest_frame = frame
                        self.frame_count += 1
                        
                    # Calculate FPS
                    frame_counter += 1
                    if frame_counter >= 10:
                        current_time = cv2.getTickCount()
                        time_diff = (current_time - last_time) / cv2.getTickFrequency()
                        self.fps = frame_counter / time_diff
                        last_time = current_time
                        frame_counter = 0
                else:
                    # Handle reconnection for network streams
                    if self.source_type == 'network':
                        logger.warning(f"Lost connection to {self.source_id}, attempting to reconnect")
                        self.cap.release()
                        self.cap = cv2.VideoCapture(self.source_url)
                    else:
                        logger.error(f"Failed to read frame from {self.source_id}")
                        break
                        
                # Small sleep to prevent CPU hogging
                cv2.waitKey(1)
            
            except Exception as e:
                logger.error(f"Error in OpenCV capture loop: {e}")
                break
        
        # Cleanup
        if hasattr(self, 'cap'):
            self.cap.release()
    
    async def stop(self) -> bool:
        """Stop capturing from the video source."""
        if not self.is_running:
            return True
            
        self.is_running = False
        
        try:
            if GSTREAMER_AVAILABLE and self.pipeline:
                # Stop GStreamer pipeline
                self.pipeline.set_state(Gst.State.NULL)
                if self._glib_loop and self._glib_loop.is_running():
                    self._glib_loop.quit()
                if self._glib_thread and self._glib_thread.is_alive():
                    self._glib_thread.join(timeout=1.0)
            
            # For OpenCV cleanup
            if hasattr(self, 'capture_thread') and self.capture_thread.is_alive():
                self.capture_thread.join(timeout=1.0)
            
            logger.info(f"Stopped video source {self.source_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error stopping video source {self.source_id}: {e}")
            return False
    
    async def get_frame(self) -> Optional[np.ndarray]:
        """Get the latest frame from the video source."""
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
        return None
    
    def get_info(self) -> Dict:
        """Get information about the video source."""
        return {
            'id': self.source_id,
            'url': self.source_url,
            'type': self.source_type,
            'is_running': self.is_running,
            'frame_count': self.frame_count,
            'fps': self.fps,
            'resolution': f"{self.width}x{self.height}"
        }


class VideoSourceManager:
    """Manager for multiple video sources."""
    
    def __init__(self):
        """Initialize the video source manager."""
        self.sources: Dict[str, VideoSource] = {}
        self.lock = threading.Lock()
    
    def add_source(self, source_id: str, source_url: str, width: int = 640, height: int = 480) -> bool:
        """Add a new video source."""
        with self.lock:
            if source_id in self.sources:
                logger.warning(f"Video source {source_id} already exists")
                return False
            
            self.sources[source_id] = VideoSource(source_id, source_url, width, height)
            logger.info(f"Added video source {source_id}: {source_url}")
            return True
    
    def remove_source(self, source_id: str) -> bool:
        """Remove a video source."""
        with self.lock:
            if source_id not in self.sources:
                logger.warning(f"Video source {source_id} does not exist")
                return False
            
            source = self.sources[source_id]
            asyncio.create_task(source.stop())
            del self.sources[source_id]
            logger.info(f"Removed video source {source_id}")
            return True
    
    async def start_source(self, source_id: str) -> bool:
        """Start a specific video source."""
        with self.lock:
            if source_id not in self.sources:
                logger.warning(f"Video source {source_id} does not exist")
                return False
            
            source = self.sources[source_id]
            return await source.start()
    
    async def start_all_sources(self) -> Dict[str, bool]:
        """Start all video sources."""
        results = {}
        with self.lock:
            source_ids = list(self.sources.keys())
        
        for source_id in source_ids:
            results[source_id] = await self.start_source(source_id)
        
        logger.info(f"Started {sum(results.values())}/{len(results)} video sources")
        return results
    
    async def stop_source(self, source_id: str) -> bool:
        """Stop a specific video source."""
        with self.lock:
            if source_id not in self.sources:
                logger.warning(f"Video source {source_id} does not exist")
                return False
            
            source = self.sources[source_id]
            return await source.stop()
    
    async def stop_all_sources(self) -> Dict[str, bool]:
        """Stop all video sources."""
        results = {}
        with self.lock:
            source_ids = list(self.sources.keys())
        
        for source_id in source_ids:
            results[source_id] = await self.stop_source(source_id)
        
        logger.info(f"Stopped {sum(results.values())}/{len(results)} video sources")
        return results
    
    async def get_frame(self, source_id: str) -> Optional[np.ndarray]:
        """Get the latest frame from a specific video source."""
        with self.lock:
            if source_id not in self.sources:
                logger.warning(f"Video source {source_id} does not exist")
                return None
            
            source = self.sources[source_id]
            return await source.get_frame()
    
    def get_source_info(self, source_id: str) -> Optional[Dict]:
        """Get information about a specific video source."""
        with self.lock:
            if source_id not in self.sources:
                logger.warning(f"Video source {source_id} does not exist")
                return None
            
            source = self.sources[source_id]
            return source.get_info()
    
    def get_all_sources_info(self) -> List[Dict]:
        """Get information about all video sources."""
        with self.lock:
            return [source.get_info() for source in self.sources.values()]
    
    def load_sources_from_env(self) -> int:
        """Load video sources from environment variables."""
        sources_str = os.getenv("VIDEO_SOURCES", "")
        if not sources_str:
            logger.warning("No video sources defined in environment variables")
            return 0
        
        count = 0
        sources = sources_str.split(",")
        for source in sources:
            if "=" not in source:
                logger.warning(f"Invalid source format: {source}")
                continue
            
            name, url = source.split("=", 1)
            if self.add_source(name.strip(), url.strip()):
                count += 1
        
        logger.info(f"Loaded {count} video sources from environment variables")
        return count 