"""
REST API Server for controlling the video analytics platform.
Built with FastAPI for high performance and automatic documentation.
"""

import os
import asyncio
import threading
import uvicorn
from typing import Dict, List, Optional, Union
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

class VideoSourceConfig(BaseModel):
    """Configuration for a video source."""
    url: str
    width: Optional[int] = 640
    height: Optional[int] = 480

class StreamConfig(BaseModel):
    """Configuration for a video stream."""
    source_id: str
    stream_type: Optional[str] = "raw"  # raw or annotated
    width: Optional[int] = 640
    height: Optional[int] = 480
    framerate: Optional[int] = 30
    bitrate: Optional[int] = 1000

class APIServer:
    """REST API server for the video analytics platform."""
    
    def __init__(self, video_manager, analytics_engine, streaming_server):
        """
        Initialize the API server.
        
        Args:
            video_manager: VideoSourceManager instance
            analytics_engine: AnalyticsEngine instance
            streaming_server: StreamingServer instance
        """
        self.video_manager = video_manager
        self.analytics_engine = analytics_engine
        self.streaming_server = streaming_server
        self.app = FastAPI(title="Video Analytics Platform API", 
                          description="REST API for video analytics platform",
                          version="1.0.0")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Load configuration from environment
        self.host = os.getenv("API_HOST", "0.0.0.0")
        self.port = int(os.getenv("API_PORT", "8000"))
        
        # Setup routes
        self._setup_routes()
        
        # Server instance
        self.server = None
        self.is_running = False
    
    def _setup_routes(self):
        """Setup API routes."""
        app = self.app
        
        @app.get("/")
        async def root():
            """Root endpoint returning API information."""
            return {
                "name": "Video Analytics Platform API",
                "version": "1.0.0",
                "documentation": "/docs"
            }
        
        @app.get("/status")
        async def get_status():
            """Get platform status."""
            return {
                "video_sources": len(self.video_manager.sources),
                "analytics_running": self.analytics_engine.is_running,
                "streaming_server_running": self.streaming_server.is_running
            }
        
        # Video source endpoints
        @app.get("/sources")
        async def get_sources():
            """Get all video sources."""
            return self.video_manager.get_all_sources_info()
        
        @app.get("/sources/{source_id}")
        async def get_source(source_id: str):
            """Get information about a specific video source."""
            info = self.video_manager.get_source_info(source_id)
            if info is None:
                raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
            return info
        
        @app.post("/sources/{source_id}")
        async def add_source(source_id: str, config: VideoSourceConfig):
            """Add a new video source."""
            success = self.video_manager.add_source(
                source_id, config.url, config.width, config.height
            )
            if not success:
                raise HTTPException(status_code=400, detail=f"Failed to add source {source_id}")
            return {"status": "success", "message": f"Added source {source_id}"}
        
        @app.delete("/sources/{source_id}")
        async def remove_source(source_id: str):
            """Remove a video source."""
            success = self.video_manager.remove_source(source_id)
            if not success:
                raise HTTPException(status_code=404, detail=f"Source {source_id} not found")
            return {"status": "success", "message": f"Removed source {source_id}"}
        
        @app.post("/sources/{source_id}/start")
        async def start_source(source_id: str):
            """Start a video source."""
            success = await self.video_manager.start_source(source_id)
            if not success:
                raise HTTPException(status_code=400, detail=f"Failed to start source {source_id}")
            return {"status": "success", "message": f"Started source {source_id}"}
        
        @app.post("/sources/{source_id}/stop")
        async def stop_source(source_id: str):
            """Stop a video source."""
            success = await self.video_manager.stop_source(source_id)
            if not success:
                raise HTTPException(status_code=400, detail=f"Failed to stop source {source_id}")
            return {"status": "success", "message": f"Stopped source {source_id}"}
        
        @app.get("/sources/{source_id}/frame")
        async def get_frame(source_id: str, annotate: bool = False):
            """Get the latest frame from a video source."""
            frame = await self.video_manager.get_frame(source_id)
            if frame is None:
                raise HTTPException(status_code=404, detail=f"No frame available for source {source_id}")
            
            # Apply analytics if requested
            if annotate:
                frame, _ = await self.analytics_engine.process_frame(source_id, frame)
            
            # Convert frame to JPEG
            import cv2
            import io
            ret, jpeg = cv2.imencode('.jpg', frame)
            if not ret:
                raise HTTPException(status_code=500, detail="Failed to encode frame")
            
            return StreamingResponse(io.BytesIO(jpeg.tobytes()), media_type="image/jpeg")
        
        # Analytics endpoints
        @app.get("/analytics")
        async def get_analytics():
            """Get analytics results for all sources."""
            return self.analytics_engine.get_all_analytics_results()
        
        @app.get("/analytics/{source_id}")
        async def get_source_analytics(source_id: str):
            """Get analytics results for a specific source."""
            results = self.analytics_engine.get_analytics_results(source_id)
            if not results:
                raise HTTPException(status_code=404, detail=f"No analytics results for source {source_id}")
            return results
        
        # Streaming endpoints
        @app.get("/streams")
        async def get_streams():
            """Get information about all streams."""
            return self.streaming_server.get_stream_info()
        
        @app.post("/streams/{stream_id}")
        async def create_stream(stream_id: str, config: StreamConfig):
            """Create a new stream."""
            success = await self.streaming_server.create_stream(stream_id, config.stream_type)
            if not success:
                raise HTTPException(status_code=400, detail=f"Failed to create stream {stream_id}")
            return {"status": "success", "message": f"Created stream {stream_id}"}
        
        @app.delete("/streams/{stream_id}")
        async def remove_stream(stream_id: str):
            """Remove a stream."""
            success = await self.streaming_server.remove_stream(stream_id)
            if not success:
                raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
            return {"status": "success", "message": f"Removed stream {stream_id}"}
        
        # System endpoints
        @app.post("/system/start")
        async def start_system():
            """Start all components of the system."""
            results = {
                "sources": await self.video_manager.start_all_sources(),
                "analytics": await self.analytics_engine.start(),
                "streaming": await self.streaming_server.start()
            }
            return {"status": "success", "results": results}
        
        @app.post("/system/stop")
        async def stop_system():
            """Stop all components of the system."""
            results = {
                "sources": await self.video_manager.stop_all_sources(),
                "analytics": await self.analytics_engine.stop(),
                "streaming": await self.streaming_server.stop()
            }
            return {"status": "success", "results": results}
    
    async def start(self) -> bool:
        """Start the API server."""
        if self.is_running:
            logger.warning("API server already running")
            return True
        
        try:
            # Start Uvicorn server in a separate thread
            config = uvicorn.Config(
                app=self.app,
                host=self.host,
                port=self.port,
                log_level="info"
            )
            server = uvicorn.Server(config)
            
            # Run server in a thread
            self.server_thread = threading.Thread(target=server.run)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            self.server = server
            self.is_running = True
            
            logger.info(f"Started API server at http://{self.host}:{self.port}")
            logger.info(f"API documentation available at http://{self.host}:{self.port}/docs")
            return True
            
        except Exception as e:
            logger.error(f"Error starting API server: {e}")
            return False
    
    async def stop(self) -> bool:
        """Stop the API server."""
        if not self.is_running:
            return True
        
        try:
            # This is a bit tricky as uvicorn doesn't have a clean shutdown method
            # when run in a thread. In a real implementation, you might use a proper
            # signal handling mechanism.
            
            if self.server:
                self.server.should_exit = True
            
            self.is_running = False
            logger.info("Stopped API server")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping API server: {e}")
            return False 