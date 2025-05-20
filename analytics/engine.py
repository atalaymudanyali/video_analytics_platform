"""
Video Analytics Engine for processing video frames.
Supports object detection, tracking, and motion analysis.
"""

import os
import asyncio
import cv2
import numpy as np
import threading
import time
from typing import Dict, List, Optional, Tuple, Union
from loguru import logger

# Import ML framework conditionally
try:
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logger.warning("TensorFlow not available, some ML features will be disabled.")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not available, some ML features will be disabled.")

# Import database
from .database import AnalyticsDatabase

class AnalyticsEngine:
    
    def __init__(self):
        self.is_running = False
        self.models = {}
        self.processors = {}
        self.results = {}
        self.lock = threading.Lock()
        self.processing_thread = None
        self.detection_interval = int(os.getenv("DETECTION_INTERVAL", "1"))
        self.detection_confidence = float(os.getenv("DETECTION_CONFIDENCE", "0.4"))
        self.detection_model = os.getenv("DETECTION_MODEL", "yolov5s")
        self.tracking_enabled = os.getenv("TRACKING_ENABLED", "True").lower() in ("true", "1", "t")
        self.heatmap_enabled = os.getenv("HEATMAP_ENABLED", "True").lower() in ("true", "1", "t")
        self.analytics_enabled = os.getenv("ANALYTICS_ENABLED", "True").lower() in ("true", "1", "t")
        
        self.database = AnalyticsDatabase()
        
    async def start(self) -> bool:
        """Start the analytics engine."""
        if self.is_running:
            logger.warning("Analytics engine already running")
            return True
        
        if not self.analytics_enabled:
            logger.info("Analytics are disabled in configuration")
            return False
        
        try:
            await self._load_models()
            
            if not await self.database.connect():
                logger.warning("Failed to connect to database, continuing without storage")
            
            self.is_running = True
            self.processing_thread = threading.Thread(target=self._processing_loop)
            self.processing_thread.daemon = True
            self.processing_thread.start()
            
            logger.info("Started analytics engine")
            return True
            
        except Exception as e:
            logger.error(f"Error starting analytics engine: {e}")
            return False
    
    async def stop(self) -> bool:
        if not self.is_running:
            return True
        
        self.is_running = False
        
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=3.0)
        
        await self.database.disconnect()
        
        with self.lock:
            self.models = {}
        
        logger.info("Stopped analytics engine")
        return True
    
    async def _load_models(self) -> bool:
        if self.detection_model.startswith("yolov5"):
            return await self._load_yolov5_model()
        elif self.detection_model.startswith("ssd"):
            return await self._load_ssd_model()
        else:
            logger.error(f"Unsupported detection model: {self.detection_model}")
            return False
    
    async def _load_yolov5_model(self) -> bool:
        try:
            if not TORCH_AVAILABLE:
                logger.error("PyTorch is required for YOLOv5")
                return False
            
            import torch
            
            model_path = f"models/{self.detection_model}.pt"
            if os.path.exists(model_path):
                logger.info(f"Loading YOLOv5 model from {model_path}")
                model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path)
            else:
                try:
                    logger.info(f"Loading YOLOv5 model {self.detection_model} from torch hub")
                    model = torch.hub.load('ultralytics/yolov5', self.detection_model)
                except Exception as e:
                    logger.error(f"Failed to load YOLOv5 model from torch hub: {e}")
                    logger.info("Falling back to dummy model for testing")
                    class DummyModel:
                        def __init__(self):
                            self.conf = self.detection_confidence
                            self.iou = 0.45
                            self.classes = None
                        def __call__(self, *args, **kwargs):
                            return type('obj', (object,), {
                                'xyxy': torch.zeros((0, 4)),
                                'conf': torch.zeros(0),
                                'cls': torch.zeros(0),
                                'names': {}
                            })
                    model = DummyModel()
            
            model.conf = self.detection_confidence  # NMS confidence threshold
            model.iou = 0.45  # NMS IoU threshold
            model.classes = None  # Filter by class
            
            with self.lock:
                self.models['detection'] = model
            
            logger.info(f"Loaded YOLOv5 model: {self.detection_model}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading YOLOv5 model: {e}")
            return False
    
    async def _load_ssd_model(self) -> bool:
        """Load SSD MobileNet model."""
        try:
            if not TENSORFLOW_AVAILABLE:
                logger.error("TensorFlow is required for SSD MobileNet")
                return False
            
            import tensorflow as tf
            
            model_dir = "models/ssd_mobilenet"
            if not os.path.exists(model_dir):
                os.makedirs(model_dir, exist_ok=True)
            
            if os.path.exists(f"{model_dir}/saved_model"):
                model = tf.saved_model.load(f"{model_dir}/saved_model")
            else:
                logger.warning("SSD MobileNet model not found locally - this is a placeholder")
                return False
            
            with self.lock:
                self.models['detection'] = model
            
            logger.info("Loaded SSD MobileNet model")
            return True
            
        except Exception as e:
            logger.error(f"Error loading SSD MobileNet model: {e}")
            return False
    
    def _processing_loop(self):
        """Background thread for frame processing."""
        frame_count = 0
        while self.is_running:
            try:

                time.sleep(0.01)  # Small sleep to prevent CPU hogging
                
            except Exception as e:
                logger.error(f"Error in analytics processing loop: {e}")
    
    async def process_frame(self, source_id: str, frame: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """
        Process a video frame with analytics.
        
        Args:
            source_id: ID of the video source
            frame: Frame to process
            
        Returns:
            Tuple of (annotated frame, metadata)
        """
        if not self.is_running or not self.analytics_enabled:
            return frame, {}
        
        try:
            with self.lock:
                if source_id not in self.results:
                    self.results[source_id] = {
                        'frame_count': 0,
                        'detections': [],
                        'last_frame': None,
                        'heatmap': np.zeros((frame.shape[0], frame.shape[1]), dtype=np.float32),
                        'detection_count': 0,
                        'class_counts': {}
                    }
                
                result = self.results[source_id]
                result['frame_count'] += 1
                
                if result['frame_count'] % self.detection_interval != 0:
                    if result['last_frame'] is not None:
                        return result['last_frame'], {'detections': result['detections']}
                    return frame, {}
            
            detections = await self._detect_objects(frame)
            
            if self.tracking_enabled and len(detections) > 0:
                tracked_detections = await self._track_objects(source_id, detections)
                detections = tracked_detections
            
            if self.heatmap_enabled:
                await self._update_heatmap(source_id, detections)
            
            with self.lock:
                result = self.results[source_id]
                result['detections'] = detections
                result['detection_count'] += len(detections)
                
                for detection in detections:
                    class_name = detection.get('class_name', 'unknown')
                    result['class_counts'][class_name] = result['class_counts'].get(class_name, 0) + 1
                
                await self.database.store_analytics_results(source_id, result)
                
                for detection in detections:
                    await self.database.store_detection(source_id, detection)
            
            annotated_frame = self._annotate_frame(frame.copy(), detections)
            
            if self.heatmap_enabled:
                annotated_frame = self._add_heatmap_overlay(annotated_frame, source_id)
            
            with self.lock:
                self.results[source_id]['last_frame'] = annotated_frame
            
            return annotated_frame, {'detections': detections}
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return frame, {}
    
    async def _detect_objects(self, frame: np.ndarray) -> List[Dict]:
        """Detect objects in a frame."""
        detections = []
        
        try:
            with self.lock:
                model = self.models.get('detection')
                
            if model is None:
                return detections
            
            # Different processing depending on model type
            if self.detection_model.startswith("yolov5"):
                # YOLOv5 processing
                results = model(frame)
                
                # Convert results to standard format
                pred = results.xyxy[0].cpu().numpy()  # pred is (n, 6) array: x1, y1, x2, y2, conf, cls
                for x1, y1, x2, y2, conf, cls in pred:
                    if conf >= self.detection_confidence:
                        class_id = int(cls)
                        class_name = results.names[class_id]
                        detections.append({
                            'box': [int(x1), int(y1), int(x2), int(y2)],
                            'confidence': float(conf),
                            'class_id': class_id,
                            'class_name': class_name
                        })
                
                logger.info(f"Detected {len(detections)} objects: {[d['class_name'] for d in detections]}")
                        
            elif self.detection_model.startswith("ssd"):
                # SSD processing
                # Placeholder for SSD MobileNet processing
                # This would process the frame through TensorFlow model
                pass
                
        except Exception as e:
            logger.error(f"Error in object detection: {e}")
        
        return detections
    
    async def _track_objects(self, source_id: str, detections: List[Dict]) -> List[Dict]:
        """Track objects across frames."""
        # Basic tracking placeholder - in a real implementation, you would use a dedicated
        # tracking algorithm like SORT, DeepSORT, ByteTrack, etc.
        return detections
    
    async def _update_heatmap(self, source_id: str, detections: List[Dict]):
        """Update the motion heatmap for a source."""
        try:
            with self.lock:
                if source_id not in self.results:
                    return
                
                heatmap = self.results[source_id]['heatmap']
                
                # Add detection regions to heatmap
                for detection in detections:
                    box = detection['box']
                    x1, y1, x2, y2 = box
                    
                    # Create a Gaussian blob around the center of the detection
                    x_center = (x1 + x2) // 2
                    y_center = (y1 + y2) // 2
                    width = x2 - x1
                    height = y2 - y1
                    
                    # Size of blob proportional to detection size
                    sigma = max(width, height) / 4
                    
                    # Create coordinates grid
                    y, x = np.mgrid[0:heatmap.shape[0], 0:heatmap.shape[1]]
                    
                    # Create gaussian blob
                    blob = np.exp(-((x - x_center) ** 2 + (y - y_center) ** 2) / (2 * sigma ** 2))
                    
                    # Add to heatmap
                    heatmap += blob
                
                # Apply decay to existing heatmap
                heatmap *= 0.95
                
                # Normalize heatmap
                if np.max(heatmap) > 0:
                    heatmap = heatmap / np.max(heatmap)
                
                # Update heatmap in results
                self.results[source_id]['heatmap'] = heatmap
                
        except Exception as e:
            logger.error(f"Error updating heatmap: {e}")
    
    def _annotate_frame(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """Annotate a frame with detection results."""
        annotated_frame = frame.copy()
        
        for detection in detections:
            # Get detection info
            box = detection['box']
            confidence = detection['confidence']
            class_name = detection.get('class_name', 'object')
            
            # Draw bounding box
            x1, y1, x2, y2 = box
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label
            label = f"{class_name}: {confidence:.2f}"
            cv2.putText(annotated_frame, label, (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        return annotated_frame
    
    def _add_heatmap_overlay(self, frame: np.ndarray, source_id: str) -> np.ndarray:
        """Add heatmap overlay to a frame."""
        try:
            with self.lock:
                if source_id not in self.results:
                    return frame
                
                heatmap = self.results[source_id]['heatmap']
                
                # Resize heatmap to match frame size if needed
                if heatmap.shape[:2] != frame.shape[:2]:
                    heatmap = cv2.resize(heatmap, (frame.shape[1], frame.shape[0]))
                
                # Convert heatmap to RGB
                heatmap_rgb = cv2.applyColorMap((heatmap * 255).astype(np.uint8), cv2.COLORMAP_JET)
                
                # Create overlay
                overlay = frame.copy()
                alpha = 0.4
                cv2.addWeighted(heatmap_rgb, alpha, frame, 1 - alpha, 0, overlay)
                
                return overlay
                
        except Exception as e:
            logger.error(f"Error adding heatmap overlay: {e}")
            return frame
    
    def get_analytics_results(self, source_id: str) -> Dict:
        """Get analytics results for a specific source."""
        with self.lock:
            if source_id not in self.results:
                return {}
            
            result = self.results[source_id]
            
            # Prepare stats
            detections = result['detections']
            detection_count = len(detections)
            
            # Count by class
            class_counts = {}
            for detection in detections:
                class_name = detection.get('class_name', 'unknown')
                if class_name not in class_counts:
                    class_counts[class_name] = 0
                class_counts[class_name] += 1
            
            return {
                'detection_count': detection_count,
                'class_counts': class_counts,
                'frame_count': result['frame_count']
            }
    
    def get_all_analytics_results(self) -> Dict[str, Dict]:
        """Get analytics results for all sources."""
        with self.lock:
            results = {}
            for source_id in self.results:
                results[source_id] = self.get_analytics_results(source_id)
            return results 