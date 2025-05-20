#!/usr/bin/env python3
"""
Main entry point for the Video Analytics Platform.
This module initializes and starts all components of the system.
"""

import os
import sys
import signal
import logging
import asyncio
import argparse
from dotenv import load_dotenv
from loguru import logger

# Import internal modules
from ingest.video_source import VideoSourceManager
from analytics.engine import AnalyticsEngine
from streaming.server import StreamingServer
from api.server import APIServer
from mqtt.client import MQTTClient
from monitoring.system_monitor import system_monitor

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("logs/platform.log", rotation="10 MB", level="DEBUG", retention="7 days")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Video Analytics Platform")
    parser.add_argument("--config", type=str, default=".env", help="Path to configuration file")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    return parser.parse_args()

async def shutdown(signal, loop):
    """Cleanup function called on shutdown."""
    logger.info(f"Received exit signal {signal.name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    for task in tasks:
        task.cancel()
    
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()
    logger.info("Shutdown complete.")

async def main():
    """Main function to start all system components."""
    args = parse_arguments()
    
    # Load configuration from .env file
    load_dotenv(args.config)
    
    # Configure debug mode
    debug = os.getenv("DEBUG", "False").lower() in ("true", "1", "t") or args.debug
    if debug:
        logger.info("Debug mode enabled")
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    
    try:
        # Initialize components
        video_manager = VideoSourceManager()
        analytics_engine = AnalyticsEngine()
        streaming_server = StreamingServer()
        api_server = APIServer(video_manager, analytics_engine, streaming_server)
        
        # Initialize MQTT if enabled
        mqtt_client = None
        if os.getenv("MQTT_ENABLED", "False").lower() in ("true", "1", "t"):
            logger.info("Initializing MQTT client")
            mqtt_client = MQTTClient()
            await mqtt_client.start()
        
        # Start API server first to ensure it's available
        await api_server.start()
        logger.info("API server started successfully")
        
        # Start video sources
        video_sources_started = await video_manager.start_all_sources()
        if not video_sources_started:
            logger.warning("Some video sources failed to start, continuing with available sources")
        
        # Start analytics engine
        analytics_started = await analytics_engine.start()
        if not analytics_started:
            logger.warning("Analytics engine failed to start, continuing without analytics")
        
        # Start streaming server
        streaming_started = await streaming_server.start()
        if not streaming_started:
            logger.warning("Streaming server failed to start, continuing without streaming")
        
        # Start system monitor
        if not system_monitor.start():
            logger.error("Failed to start system monitor")
        
        logger.info("Video Analytics Platform started successfully")
        
        # Keep the main function running
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Try to start at least the API server
        try:
            if 'api_server' in locals():
                await api_server.start()
                logger.info("Started API server in fallback mode")
                while True:
                    await asyncio.sleep(1)
        except Exception as api_error:
            logger.error(f"Failed to start API server: {api_error}")
            raise

async def shutdown():
    """Stop all components."""
    try:
        # Stop system monitor
        if not system_monitor.stop():
            logger.error("Failed to stop system monitor")
        
        # Stop other components
        # ... rest of shutdown code ...
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
        raise

if __name__ == "__main__":
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in signals:
        loop.add_signal_handler(s, lambda s=s: asyncio.create_task(shutdown(s, loop)))
    
    try:
        loop.run_until_complete(main())
    except asyncio.CancelledError:
        logger.info("Main task was cancelled")
    finally:
        loop.close()
        logger.info("Successfully shutdown the Video Analytics Platform.") 