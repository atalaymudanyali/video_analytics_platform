#!/usr/bin/env python3
"""
Sample data generator for testing the video analytics platform.
Generates synthetic video streams with moving objects.
"""

import os
import sys
import cv2
import numpy as np
import time
import argparse
import random
from typing import List, Tuple, Dict

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class MovingObject:
    """Class representing a moving object in a synthetic video."""
    
    def __init__(self, frame_width: int, frame_height: int, size_range: Tuple[int, int] = (30, 100)):
        """
        Initialize a moving object.
        
        Args:
            frame_width: Width of the video frame
            frame_height: Height of the video frame
            size_range: Range of possible object sizes (min, max)
        """
        # Position and velocity
        self.x = random.randint(0, frame_width)
        self.y = random.randint(0, frame_height)
        self.vx = random.randint(-4, 4)
        self.vy = random.randint(-4, 4)
        
        # Ensure non-zero velocity
        if self.vx == 0 and self.vy == 0:
            self.vx = random.choice([-2, 2])
            self.vy = random.choice([-2, 2])
        
        # Size and appearance
        self.width = random.randint(size_range[0], size_range[1])
        self.height = random.randint(size_range[0], size_range[1])
        self.color = (
            random.randint(50, 255),
            random.randint(50, 255),
            random.randint(50, 255)
        )
        
        # Frame dimensions
        self.frame_width = frame_width
        self.frame_height = frame_height
        
        # Object class (for detection simulation)
        self.class_name = random.choice(['person', 'car', 'cat', 'dog', 'bicycle'])
        self.confidence = random.uniform(0.6, 0.95)
    
    def update(self):
        """Update object position."""
        # Update position
        self.x += self.vx
        self.y += self.vy
        
        # Bounce off edges
        if self.x < 0 or self.x + self.width > self.frame_width:
            self.vx = -self.vx
            self.x = max(0, min(self.x, self.frame_width - self.width))
        
        if self.y < 0 or self.y + self.height > self.frame_height:
            self.vy = -self.vy
            self.y = max(0, min(self.y, self.frame_height - self.height))
    
    def draw(self, frame: np.ndarray):
        """Draw the object on a frame."""
        x1, y1 = int(self.x), int(self.y)
        x2, y2 = int(self.x + self.width), int(self.y + self.height)
        
        # Draw object
        cv2.rectangle(frame, (x1, y1), (x2, y2), self.color, -1)
        
        # Draw outline
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 0), 2)
    
    def get_detection_info(self) -> Dict:
        """Get object detection info (simulating ML model output)."""
        return {
            'box': [int(self.x), int(self.y), int(self.x + self.width), int(self.y + self.height)],
            'confidence': self.confidence,
            'class_name': self.class_name,
            'class_id': ['person', 'car', 'cat', 'dog', 'bicycle'].index(self.class_name)
        }


class SampleGenerator:
    """Generator for sample video data."""
    
    def __init__(self, width: int = 640, height: int = 480, bg_color: Tuple[int, int, int] = (200, 200, 200)):
        """
        Initialize the sample generator.
        
        Args:
            width: Frame width
            height: Frame height
            bg_color: Background color
        """
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.objects: List[MovingObject] = []
        self.frame_count = 0
    
    def add_object(self):
        """Add a moving object to the scene."""
        obj = MovingObject(self.width, self.height)
        self.objects.append(obj)
        return obj
    
    def generate_frame(self) -> Tuple[np.ndarray, List[Dict]]:
        """
        Generate a video frame with objects.
        
        Returns:
            Tuple of (frame, detections)
        """
        # Create background
        frame = np.ones((self.height, self.width, 3), dtype=np.uint8) * np.array(self.bg_color, dtype=np.uint8)
        
        # Update and draw objects
        detections = []
        for obj in self.objects:
            obj.update()
            obj.draw(frame)
            detections.append(obj.get_detection_info())
        
        # Add frame number and timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, f"Frame: {self.frame_count}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        cv2.putText(frame, timestamp, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        self.frame_count += 1
        return frame, detections
    
    def annotate_frame(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """
        Add detection annotations to a frame.
        
        Args:
            frame: Video frame
            detections: List of detection info
            
        Returns:
            Annotated frame
        """
        annotated = frame.copy()
        
        for detection in detections:
            # Get detection info
            box = detection['box']
            confidence = detection['confidence']
            class_name = detection['class_name']
            
            # Draw bounding box
            x1, y1, x2, y2 = box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label
            label = f"{class_name}: {confidence:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            y1 = max(y1, label_size[1])
            cv2.rectangle(annotated, (x1, y1 - label_size[1] - 5), (x1 + label_size[0], y1), (0, 255, 0), -1)
            cv2.putText(annotated, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        return annotated


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Generate synthetic video data for testing")
    parser.add_argument("--width", type=int, default=640, help="Frame width")
    parser.add_argument("--height", type=int, default=480, help="Frame height")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second")
    parser.add_argument("--objects", type=int, default=5, help="Number of moving objects")
    parser.add_argument("--duration", type=int, default=0, help="Duration in seconds (0 for infinite)")
    parser.add_argument("--output", type=str, default="", help="Output video file (empty for display only)")
    parser.add_argument("--show-annotations", action="store_true", help="Show detection annotations")
    args = parser.parse_args()
    
    # Create sample generator
    generator = SampleGenerator(args.width, args.height)
    
    # Add objects
    for _ in range(args.objects):
        generator.add_object()
    
    # Create video writer if output specified
    writer = None
    if args.output:
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        writer = cv2.VideoWriter(args.output, fourcc, args.fps, (args.width, args.height))
    
    # Calculate total frames
    total_frames = args.fps * args.duration if args.duration > 0 else float('inf')
    
    # Main loop
    try:
        while generator.frame_count < total_frames:
            # Generate frame
            frame, detections = generator.generate_frame()
            
            # Annotate if requested
            if args.show_annotations:
                frame = generator.annotate_frame(frame, detections)
            
            # Display frame
            cv2.imshow("Synthetic Video", frame)
            
            # Write frame if output specified
            if writer:
                writer.write(frame)
            
            # Process keyboard input
            key = cv2.waitKey(1000 // args.fps) & 0xFF
            if key == ord('q') or key == 27:  # 'q' or ESC
                break
            elif key == ord('a'):
                generator.add_object()
                print(f"Added object (total: {len(generator.objects)})")
            elif key == ord('r'):
                if generator.objects:
                    generator.objects.pop()
                    print(f"Removed object (total: {len(generator.objects)})")
            
    except KeyboardInterrupt:
        print("Stopped by user")
    
    # Cleanup
    cv2.destroyAllWindows()
    if writer:
        writer.release()


if __name__ == "__main__":
    main() 