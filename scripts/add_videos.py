#!/usr/bin/env python3
"""
Video source management module.
"""

import requests
from typing import List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class VideoSource:
    name: str
    path: str
    width: int = 640
    height: int = 480

class VideoManager:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.sources: List[VideoSource] = []

    def add_source(self, source: VideoSource) -> bool:
        """Add a video source to the platform."""
        try:
            response = requests.post(
                f"{self.base_url}/sources/{source.name}",
                json={
                    "url": f"/app/data/raw_videos/{source.path}",
                    "width": source.width,
                    "height": source.height
                }
            )
            response.raise_for_status()
            self.sources.append(source)
            return True
        except requests.exceptions.RequestException:
            return False

    def start_source(self, name: str) -> bool:
        """Start a video source."""
        try:
            response = requests.post(f"{self.base_url}/sources/{name}/start")
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False

    def get_stream_urls(self, name: str) -> Tuple[str, str]:
        """Get HLS and RTSP URLs for a video source."""
        hls_url = f"http://localhost:8080/stream/{name}"
        rtsp_url = f"rtsp://localhost:8554/streams/{name}"
        return hls_url, rtsp_url

def setup_default_sources() -> VideoManager:
    """Setup default video sources."""
    manager = VideoManager()
    
    sources = [
        VideoSource("car_video", "car-detection.mp4"),
        VideoSource("person_video", "person_detection.mp4"),
        VideoSource("combined_video", "person-bicycle-car-detection.mp4")
    ]

    for source in sources:
        if manager.add_source(source):
            manager.start_source(source.name)

    return manager

if __name__ == "__main__":
    manager = setup_default_sources()
    for source in manager.sources:
        hls_url, rtsp_url = manager.get_stream_urls(source.name)
        print(f"\n{source.name}:")
        print(f"  HLS: {hls_url}")
        print(f"  RTSP: {rtsp_url}") 