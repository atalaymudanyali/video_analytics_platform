"""
System monitoring module for collecting and storing system metrics.
"""

import os
import psutil
import time
import threading
from datetime import datetime
from typing import Dict, Optional
from loguru import logger

try:
    from influxdb_client import InfluxDBClient, Point, WritePrecision
    from influxdb_client.client.write_api import SYNCHRONOUS
    INFLUXDB_AVAILABLE = True
except ImportError:
    INFLUXDB_AVAILABLE = False
    logger.warning("InfluxDB client not available. Install influxdb-client for monitoring support.")

class SystemMonitor:
    """System monitoring class for collecting and storing metrics."""
    
    def __init__(self):
        """Initialize the system monitor."""
        self.is_running = False
        self.monitoring_thread = None
        self.collection_interval = int(os.getenv("MONITORING_INTERVAL", "5"))
        
        # InfluxDB configuration
        self.influxdb_enabled = os.getenv("DB_ENABLED", "True").lower() in ("true", "1", "t")
        self.influxdb_url = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
        self.influxdb_token = os.getenv("INFLUXDB_ADMIN_TOKEN")
        self.influxdb_org = os.getenv("INFLUXDB_ORG")
        self.influxdb_bucket = os.getenv("INFLUXDB_BUCKET")
        
        # Initialize InfluxDB client
        self.client = None
        self.write_api = None
        if self.influxdb_enabled and INFLUXDB_AVAILABLE:
            if not all([self.influxdb_token, self.influxdb_org, self.influxdb_bucket]):
                logger.error("Missing required InfluxDB configuration")
                return
            try:
                self.client = InfluxDBClient(
                    url=self.influxdb_url,
                    token=self.influxdb_token,
                    org=self.influxdb_org
                )
                self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
                logger.info("Connected to InfluxDB")
            except Exception as e:
                logger.error(f"Failed to connect to InfluxDB: {e}")
    
    def start(self) -> bool:
        """Start the system monitor."""
        if self.is_running:
            logger.warning("System monitor already running")
            return True
        
        try:
            self.is_running = True
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            
            logger.info("Started system monitor")
            return True
            
        except Exception as e:
            logger.error(f"Error starting system monitor: {e}")
            return False
    
    def stop(self) -> bool:
        """Stop the system monitor."""
        if not self.is_running:
            return True
        
        try:
            self.is_running = False
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=3.0)
            
            if self.client:
                self.client.close()
            
            logger.info("Stopped system monitor")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping system monitor: {e}")
            return False
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_running:
            try:
                # Collect metrics
                metrics = self._collect_metrics()
                
                # Store metrics
                if self.influxdb_enabled and INFLUXDB_AVAILABLE and self.write_api:
                    self._store_metrics(metrics)
                
                # Sleep for collection interval
                time.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(1.0)
    
    def _collect_metrics(self) -> Dict:
        """Collect system metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available
            memory_total = memory.total
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free = disk.free
            disk_total = disk.total
            
            # Network metrics
            net_io = psutil.net_io_counters()
            bytes_sent = net_io.bytes_sent
            bytes_recv = net_io.bytes_recv
            
            return {
                'cpu': {
                    'usage': cpu_percent,
                    'count': cpu_count
                },
                'memory': {
                    'usage': memory_percent,
                    'available': memory_available,
                    'total': memory_total
                },
                'disk': {
                    'usage': disk_percent,
                    'free': disk_free,
                    'total': disk_total
                },
                'network': {
                    'bytes_sent': bytes_sent,
                    'bytes_recv': bytes_recv
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            return {}
    
    def _store_metrics(self, metrics: Dict):
        """Store metrics in InfluxDB."""
        try:
            if not metrics:
                return
            
            # Create points for each metric type
            points = []
            
            # CPU metrics
            if 'cpu' in metrics:
                cpu = metrics['cpu']
                points.append(
                    Point("system")
                    .tag("metric", "cpu")
                    .field("cpu_usage", float(cpu['usage']))
                    .field("cpu_count", int(cpu['count']))
                    .time(datetime.utcnow(), WritePrecision.NS)
                )
            
            # Memory metrics
            if 'memory' in metrics:
                memory = metrics['memory']
                points.append(
                    Point("system")
                    .tag("metric", "memory")
                    .field("memory_usage", float(memory['usage']))
                    .field("memory_available", int(memory['available']))
                    .field("memory_total", int(memory['total']))
                    .time(datetime.utcnow(), WritePrecision.NS)
                )
            
            # Disk metrics
            if 'disk' in metrics:
                disk = metrics['disk']
                points.append(
                    Point("system")
                    .tag("metric", "disk")
                    .field("disk_usage", float(disk['usage']))
                    .field("disk_free", int(disk['free']))
                    .field("disk_total", int(disk['total']))
                    .time(datetime.utcnow(), WritePrecision.NS)
                )
            
            # Network metrics
            if 'network' in metrics:
                network = metrics['network']
                points.append(
                    Point("system")
                    .tag("metric", "network")
                    .field("bytes_sent", int(network['bytes_sent']))
                    .field("bytes_recv", int(network['bytes_recv']))
                    .time(datetime.utcnow(), WritePrecision.NS)
                )
            
            # Write all points
            if points:
                self.write_api.write(bucket=self.influxdb_bucket, record=points)
            
        except Exception as e:
            logger.error(f"Error storing metrics in InfluxDB: {e}")

# Create singleton instance
system_monitor = SystemMonitor() 