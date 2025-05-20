"""
Database integration for storing analytics data.
Currently supports InfluxDB for time-series analytics data.
"""

import os
import time
import asyncio
import threading
from typing import Dict, List, Optional, Union
from datetime import datetime
from loguru import logger


INFLUXDB_AVAILABLE = False
try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUXDB_AVAILABLE = True
except ImportError:
    logger.warning("InfluxDB client not available. Install influxdb-client for database support.")

class AnalyticsDatabase:
    """Database for storing analytics data."""
    
    def __init__(self):
        """Initialize the analytics database."""
        self.is_connected = False
        self.client = None
        self.write_api = None
        
        self.url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
        self.token = os.getenv("INFLUXDB_ADMIN_TOKEN", "")
        self.org = os.getenv("INFLUXDB_ORG", "")
        self.bucket = os.getenv("INFLUXDB_BUCKET", "video_analytics")
        self.enabled = os.getenv("DB_ENABLED", "False").lower() in ("true", "1", "t")
        
        if not INFLUXDB_AVAILABLE:
            logger.warning("InfluxDB client not available, database functionality will be disabled")
            self.enabled = False
    
    async def connect(self) -> bool:
        if not self.enabled or not INFLUXDB_AVAILABLE:
            logger.info(f"Database is disabled or not available. enabled={self.enabled}, available={INFLUXDB_AVAILABLE}")
            return False
        
        if self.is_connected:
            logger.warning("Database already connected")
            return True
        
        try:
            logger.info(f"Connecting to InfluxDB at {self.url} with org={self.org}, bucket={self.bucket}, token={self.token[:5]}...")
            
            self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            
            health = self.client.health()
            logger.info(f"InfluxDB health status: {health.status}, message: {health.message}")
            
            if health.status != "pass":
                logger.error(f"Failed to connect to InfluxDB: {health.message}")
                self.client = None
                return False
            
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            
            self.is_connected = True
            logger.info(f"Connected to InfluxDB at {self.url}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to InfluxDB: {e}")
            self.client = None
            return False
    
    async def disconnect(self) -> bool:
        if not self.enabled or not INFLUXDB_AVAILABLE:
            return True
        
        if not self.is_connected or self.client is None:
            return True
        
        try:
            # Close client
            self.client.close()
            
            self.is_connected = False
            self.client = None
            self.write_api = None
            
            logger.info("Disconnected from InfluxDB")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from InfluxDB: {e}")
            return False
    
    async def store_detection(self, source_id: str, detection: Dict) -> bool:

        if not self.enabled or not INFLUXDB_AVAILABLE:
            return False
        
        if not self.is_connected or self.write_api is None:
            logger.warning("Not connected to InfluxDB")
            return False
        
        try:
            # Create point
            point = Point("detection") \
                .tag("source_id", source_id) \
                .tag("class_name", detection.get("class_name", "unknown")) \
                .field("confidence", float(detection.get("confidence", 0.0))) \
                .field("x1", detection.get("box", [0, 0, 0, 0])[0]) \
                .field("y1", detection.get("box", [0, 0, 0, 0])[1]) \
                .field("x2", detection.get("box", [0, 0, 0, 0])[2]) \
                .field("y2", detection.get("box", [0, 0, 0, 0])[3]) \
                .time(datetime.utcnow(), WritePrecision.NS)
            
            self.write_api.write(bucket=self.bucket, record=point)
            return True
            
        except Exception as e:
            logger.error(f"Error storing detection in InfluxDB: {e}")
            return False
    
    async def store_analytics_results(self, source_id: str, results: Dict) -> bool:

        if not self.enabled or not INFLUXDB_AVAILABLE:
            logger.warning(f"InfluxDB storage disabled or not available. enabled={self.enabled}, available={INFLUXDB_AVAILABLE}")
            return False
        
        if not self.is_connected or self.write_api is None:
            logger.warning("Not connected to InfluxDB")
            return False
        
        try:
            logger.info(f"Storing analytics results for {source_id}: {results.get('detection_count')} detections, {results.get('frame_count')} frames")
            
            point = Point("analytics") \
                .tag("source_id", source_id) \
                .field("detection_count", results.get("detection_count", 0)) \
                .field("frame_count", results.get("frame_count", 0)) \
                .time(datetime.utcnow(), WritePrecision.NS)
            
            self.write_api.write(bucket=self.bucket, record=point)
            logger.info(f"Stored analytics data for {source_id}")
            
            class_counts = results.get("class_counts", {})
            for class_name, count in class_counts.items():
                class_point = Point("class_count") \
                    .tag("source_id", source_id) \
                    .tag("class_name", class_name) \
                    .field("count", count) \
                    .time(datetime.utcnow(), WritePrecision.NS)
                

                self.write_api.write(bucket=self.bucket, record=class_point)
                logger.info(f"Stored class count for {source_id}: {class_name}={count}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error storing analytics results in InfluxDB: {e}")
            return False
    
    async def get_detection_count(self, source_id: str, start_time: Optional[str] = None, end_time: Optional[str] = None) -> int:

        if not self.enabled or not INFLUXDB_AVAILABLE:
            return 0
        
        if not self.is_connected or self.client is None:
            logger.warning("Not connected to InfluxDB")
            return 0
        
        try:
            # Create query API
            query_api = self.client.query_api()
            
            # Build time range
            time_range = ""
            if start_time and end_time:
                time_range = f'range(start: {start_time}, stop: {end_time})'
            elif start_time:
                time_range = f'range(start: {start_time})'
            else:
                time_range = 'range(start: -1h)'  # Default to last hour
            
            # Build query
            query = f'''
            from(bucket: "{self.bucket}")
              |> {time_range}
              |> filter(fn: (r) => r._measurement == "detection")
              |> filter(fn: (r) => r.source_id == "{source_id}")
              |> count()
            '''
            
            # Execute query
            result = query_api.query(query=query, org=self.org)
            
            # Parse result
            count = 0
            for table in result:
                for record in table.records:
                    count = record.get_value()
                    break
            
            return count
            
        except Exception as e:
            logger.error(f"Error querying InfluxDB: {e}")
            return 0
    
    async def get_class_distribution(self, source_id: str, start_time: Optional[str] = None, end_time: Optional[str] = None) -> Dict[str, int]:

        if not self.enabled or not INFLUXDB_AVAILABLE:
            return {}
        
        if not self.is_connected or self.client is None:
            logger.warning("Not connected to InfluxDB")
            return {}
        
        try:
            # Create query API
            query_api = self.client.query_api()
            
            # Build time range
            time_range = ""
            if start_time and end_time:
                time_range = f'range(start: {start_time}, stop: {end_time})'
            elif start_time:
                time_range = f'range(start: {start_time})'
            else:
                time_range = 'range(start: -1h)'  # Default to last hour
            
            # Build query
            query = f'''
            from(bucket: "{self.bucket}")
              |> {time_range}
              |> filter(fn: (r) => r._measurement == "detection")
              |> filter(fn: (r) => r.source_id == "{source_id}")
              |> group(columns: ["class_name"])
              |> count()
            '''
            
            # Execute query
            result = query_api.query(query=query, org=self.org)
            
            # Parse result
            class_counts = {}
            for table in result:
                for record in table.records:
                    class_name = record.values.get("class_name", "unknown")
                    count = record.get_value()
                    class_counts[class_name] = count
            
            return class_counts
            
        except Exception as e:
            logger.error(f"Error querying InfluxDB: {e}")
            return {} 