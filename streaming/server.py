"""
Streaming Server for distributing video streams.
Uses GStreamer to publish RTSP and HLS streams.
"""

import os
import asyncio
import threading
import time
import cv2
import numpy as np
from typing import Dict, List, Optional
from loguru import logger

# Check for GStreamer
GSTREAMER_AVAILABLE = False
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib
    Gst.init(None)
    GSTREAMER_AVAILABLE = True
except (ImportError, ValueError):
    logger.warning("GStreamer Python bindings not available. Some streaming features will be limited.")

class StreamingServer:
    """Server for streaming video to clients."""
    
    def __init__(self):
        """Initialize the streaming server."""
        self.is_running = False
        self.pipelines = {}
        self.lock = threading.Lock()
        
        # Load configuration from environment
        self.stream_host = os.getenv("STREAM_HOST", "0.0.0.0")
        self.rtsp_port = int(os.getenv("STREAM_PORT", "8554"))
        self.hls_port = int(os.getenv("HLS_PORT", "8080"))
        self.stream_path = os.getenv("STREAM_PATH", "/streams")
        
        # Stream options
        self.width = 640
        self.height = 480
        self.framerate = 30
        self.bitrate = 1000
        
        # Fallback streaming options if GStreamer not available
        self.frame_buffers = {}
        self.mjpeg_server = None
    
    async def start(self) -> bool:
        """Start the streaming server."""
        if self.is_running:
            logger.warning("Streaming server already running")
            return True
        
        try:
            if GSTREAMER_AVAILABLE:
                # Initialize GStreamer RTSP server
                success = await self._start_gstreamer_rtsp()
                if not success:
                    logger.warning("Failed to start GStreamer RTSP server, falling back to MJPEG")
                    success = await self._start_mjpeg_server()
            else:
                # Fall back to MJPEG streaming
                success = await self._start_mjpeg_server()
            
            self.is_running = success
            if success:
                logger.info("Started streaming server")
            return success
            
        except Exception as e:
            logger.error(f"Error starting streaming server: {e}")
            return False
    
    async def _start_gstreamer_rtsp(self) -> bool:
        """Start GStreamer RTSP server."""
        try:
            # Import GStreamer RTSP server
            gi.require_version('GstRtspServer', '1.0')
            from gi.repository import GstRtspServer
            
            # Create GLib main loop
            self._glib_loop = GLib.MainLoop()
            self._glib_thread = threading.Thread(target=self._glib_loop.run)
            self._glib_thread.daemon = True
            self._glib_thread.start()
            
            # Create RTSP server
            self.server = GstRtspServer.RTSPServer()
            self.server.set_address(self.stream_host)
            self.server.set_service(str(self.rtsp_port))
            
            # Start server
            self.server.attach(None)
            
            logger.info(f"Started RTSP server at rtsp://{self.stream_host}:{self.rtsp_port}{self.stream_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting GStreamer RTSP server: {e}")
            return False
    
    async def _start_mjpeg_server(self) -> bool:
        """Start MJPEG streaming server as fallback."""
        try:
            # This would be a basic HTTP server that serves MJPEG streams
            # For simplicity, we'll use OpenCV's built-in MJPEG server
            # In a production system, you would use a more robust solution
            
            # Start a separate thread for the HTTP server
            self.mjpeg_thread = threading.Thread(target=self._run_mjpeg_server)
            self.mjpeg_thread.daemon = True
            self.mjpeg_thread.start()
            
            logger.info(f"Started MJPEG server at http://{self.stream_host}:{self.hls_port}/stream")
            return True
            
        except Exception as e:
            logger.error(f"Error starting MJPEG server: {e}")
            return False
    
    def _run_mjpeg_server(self):
        """Run MJPEG server in a separate thread."""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import socket
        
        class MJPEGHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith('/stream'):
                    self.send_response(200)
                    self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
                    self.end_headers()
                    
                    # Extract stream ID from path
                    path_parts = self.path.strip('/').split('/')
                    stream_id = path_parts[1] if len(path_parts) > 1 else None
                    
                    try:
                        while True:
                            frame = None
                            with self.server.streaming_server.lock:
                                if stream_id:
                                    if stream_id in self.server.streaming_server.frame_buffers:
                                        frame = self.server.streaming_server.frame_buffers[stream_id]
                                else:
                                    # If no stream ID specified, use first available
                                    for buffer_id in self.server.streaming_server.frame_buffers:
                                        frame = self.server.streaming_server.frame_buffers[buffer_id]
                                        break
                            
                            if frame is not None:
                                ret, jpg = cv2.imencode('.jpg', frame)
                                if ret:
                                    self.wfile.write(b'--jpgboundary\r\n')
                                    self.send_header('Content-type', 'image/jpeg')
                                    self.send_header('Content-length', str(len(jpg)))
                                    self.end_headers()
                                    self.wfile.write(jpg)
                                    self.wfile.write(b'\r\n')
                            
                            time.sleep(1.0 / self.server.streaming_server.framerate)
                    except (BrokenPipeError, ConnectionResetError):
                        # Client disconnected
                        pass
                else:
                    # Serve HTML page for stream listing
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    
                    html = '<html><head><title>Video Streams</title></head><body>'
                    html += '<h1>Available Streams</h1><ul>'
                    
                    with self.server.streaming_server.lock:
                        for stream_id in self.server.streaming_server.frame_buffers:
                            html += f'<li><a href="/stream/{stream_id}">{stream_id}</a></li>'
                    
                    html += '</ul></body></html>'
                    self.wfile.write(html.encode())
            
            def log_message(self, format, *args):
                # Suppress log messages
                pass
        
        class StreamingHTTPServer(HTTPServer):
            def __init__(self, server_address, RequestHandlerClass, streaming_server):
                self.streaming_server = streaming_server
                super().__init__(server_address, RequestHandlerClass)
        
        try:
            server_address = (self.stream_host, self.hls_port)
            self.mjpeg_server = StreamingHTTPServer(server_address, MJPEGHandler, self)
            self.mjpeg_server.serve_forever()
        except Exception as e:
            logger.error(f"Error in MJPEG server: {e}")
    
    async def stop(self) -> bool:
        """Stop the streaming server."""
        if not self.is_running:
            return True
        
        self.is_running = False
        
        try:
            if GSTREAMER_AVAILABLE:
                # Stop GStreamer server
                if hasattr(self, '_glib_loop') and self._glib_loop.is_running():
                    self._glib_loop.quit()
                if hasattr(self, '_glib_thread') and self._glib_thread.is_alive():
                    self._glib_thread.join(timeout=1.0)
            
            # Stop MJPEG server if running
            if hasattr(self, 'mjpeg_server') and self.mjpeg_server:
                self.mjpeg_server.shutdown()
                self.mjpeg_server.server_close()
            
            if hasattr(self, 'mjpeg_thread') and self.mjpeg_thread.is_alive():
                self.mjpeg_thread.join(timeout=1.0)
            
            logger.info("Stopped streaming server")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping streaming server: {e}")
            return False
    
    async def create_stream(self, stream_id: str, stream_type: str = 'raw') -> bool:
        """Create a new stream."""
        if not self.is_running:
            logger.warning("Streaming server not running")
            return False
        
        with self.lock:
            if stream_id in self.pipelines:
                logger.warning(f"Stream {stream_id} already exists")
                return False
            
            # For MJPEG fallback
            self.frame_buffers[stream_id] = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            
            if GSTREAMER_AVAILABLE:
                try:
                    # Import GStreamer RTSP server
                    gi.require_version('GstRtspServer', '1.0')
                    from gi.repository import GstRtspServer
                    
                    # Create a media factory for this stream
                    factory = GstRtspServer.RTSPMediaFactory()
                    factory.set_launch(
                        f"( appsrc name=source_{stream_id} is-live=true format=time "
                        f"caps=video/x-raw,format=BGR,width={self.width},height={self.height},framerate={self.framerate}/1 ! "
                        f"videoconvert ! video/x-raw,format=I420 ! "
                        f"x264enc tune=zerolatency bitrate={self.bitrate} speed-preset=superfast ! "
                        f"rtph264pay name=pay0 pt=96 )"
                    )
                    
                    # Attach factory to server
                    mount_point = f"{self.stream_path}/{stream_id}"
                    self.server.get_mount_points().add_factory(mount_point, factory)
                    
                    # Store pipeline reference
                    self.pipelines[stream_id] = factory
                    
                    logger.info(f"Created RTSP stream at rtsp://{self.stream_host}:{self.rtsp_port}{mount_point}")
                except Exception as e:
                    logger.error(f"Error creating GStreamer pipeline for stream {stream_id}: {e}")
                    return False
            
            logger.info(f"Created {stream_type} stream: {stream_id}")
            return True
    
    async def remove_stream(self, stream_id: str) -> bool:
        """Remove a stream."""
        if not self.is_running:
            logger.warning("Streaming server not running")
            return False
        
        with self.lock:
            if stream_id not in self.pipelines and stream_id not in self.frame_buffers:
                logger.warning(f"Stream {stream_id} does not exist")
                return False
            
            # Remove from pipelines if using GStreamer
            if stream_id in self.pipelines:
                # Stop and clean up pipeline
                pipeline = self.pipelines[stream_id]
                pipeline.set_state(Gst.State.NULL)
                del self.pipelines[stream_id]
            
            # Remove from frame buffers
            if stream_id in self.frame_buffers:
                del self.frame_buffers[stream_id]
            
            logger.info(f"Removed stream: {stream_id}")
            return True
    
    async def update_stream(self, stream_id: str, frame: np.ndarray) -> bool:
        """Update a stream with a new frame."""
        if not self.is_running:
            return False
        
        try:
            with self.lock:
                if stream_id not in self.frame_buffers:
                    # Create stream if it doesn't exist
                    await self.create_stream(stream_id)
                
                # Update frame buffer
                self.frame_buffers[stream_id] = frame
                
                # Push frame to GStreamer pipeline if available
                if GSTREAMER_AVAILABLE and stream_id in self.pipelines:
                    try:
                        factory = self.pipelines[stream_id]
                        media = factory.get_media()
                        if media and media.is_prepared():
                            # Get appsrc element
                            appsrc = media.get_element(f"source_{stream_id}")
                            if appsrc:
                                # Create GStreamer buffer from frame
                                data = frame.tobytes()
                                gst_buffer = Gst.Buffer.new_wrapped(data)
                                # Set buffer timestamp
                                gst_buffer.pts = Gst.CLOCK_TIME_NONE
                                gst_buffer.dts = Gst.CLOCK_TIME_NONE
                                gst_buffer.duration = Gst.CLOCK_TIME_NONE
                                # Push buffer
                                appsrc.emit('push-buffer', gst_buffer)
                    except Exception as e:
                        logger.error(f"Error pushing frame to GStreamer pipeline: {e}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error updating stream {stream_id}: {e}")
            return False
    
    def get_stream_info(self) -> Dict:
        """Get information about all streams."""
        with self.lock:
            return {
                'rtsp_url': f"rtsp://{self.stream_host}:{self.rtsp_port}{self.stream_path}",
                'hls_url': f"http://{self.stream_host}:{self.hls_port}/stream",
                'active_streams': list(self.frame_buffers.keys()),
                'gstreamer_available': GSTREAMER_AVAILABLE
            } 