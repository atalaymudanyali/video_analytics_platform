# Video Analytics OpenCV Client

This is a Python-based client application that connects to the Video Analytics Platform and displays video streams with real-time analytics overlays.

## Features

- Real-time video display using OpenCV
- MQTT integration for analytics data
- Detection visualization with bounding boxes and labels
- FPS counter
- Automatic reconnection to MQTT broker
- Thread-safe frame and detection updates
- ESC key to exit

## Prerequisites

- Python 3.8 or higher
- OpenCV
- MQTT broker (e.g., Mosquitto)
- Video Analytics Platform running

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the client with a specific video source:

```bash
python opencv_client.py --source local_car
```

Optional arguments:
- `--broker`: MQTT broker hostname (default: localhost)
- `--port`: MQTT broker port (default: 1883)

Example with all options:
```bash
python opencv_client.py --source rtsp_camera --broker 192.168.1.100 --port 1883
```

## Controls

- ESC: Exit the application
- Window can be resized by dragging corners

## Display Information

The client window shows:
- Video frame with detection overlays
- FPS counter in top-left corner
- Object detection boxes with class names and confidence scores
- "Waiting for video..." message when no frames are available

## Troubleshooting

1. No video display:
   - Check if the video source exists in the platform
   - Verify MQTT broker connection
   - Check logs in `logs/client_[source_id].log`

2. No detections:
   - Ensure analytics are enabled in the platform
   - Check MQTT topic subscription
   - Verify detection events are being published

3. Connection issues:
   - Check MQTT broker status
   - Verify network connectivity
   - Check broker hostname and port

## Architecture

The client uses a multi-threaded architecture:
- Main thread: Handles MQTT communication and frame updates
- Display thread: Manages OpenCV window and rendering
- MQTT client thread: Handles message publishing and subscription

Thread synchronization is handled using:
- Frame lock for video frame updates
- Detection lock for analytics data updates

## Contributing

Feel free to submit issues and enhancement requests. 