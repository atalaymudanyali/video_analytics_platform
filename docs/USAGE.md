# Video Analytics Platform Usage Guide

This guide will help you get started using the Video Analytics Platform.

## System Requirements

- Python 3.8+
- GStreamer 1.18+ with plugins
- OpenCV 
- NVIDIA GPU recommended for faster ML processing (optional)

## Installation

### Method 1: Manual Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/video-analytics-platform.git
   cd video-analytics-platform
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Download ML models:
   ```bash
   mkdir -p models
   python -c "import torch; yolo = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True); yolo.save('models/yolov5s.pt')"
   ```

### Method 2: Using the Setup Script

Run the setup script:
```bash
python setup_project.py
```

### Method 3: Using Make

If you have Make installed, you can use:
```bash
make setup   # Set up the project structure
make deps    # Install dependencies
make models  # Download ML models
make install # Install everything
```

### Method 4: Using Docker

Build and run with Docker Compose:
```bash
docker-compose up
```

## Starting the Platform

### Running the Server

Start the main server:
```bash
python main.py
```

This will start all components:
- Video ingestion
- Analytics engine
- Streaming server
- REST API server
- MQTT client (if enabled)

### Configuration

The platform is configured using environment variables, which can be set in the `.env` file:

```
# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True

# Streaming Configuration
STREAM_HOST=0.0.0.0
STREAM_PORT=8554
HLS_PORT=8080
STREAM_PATH=/streams

# Video Sources (comma-separated)
# Format: name=url
VIDEO_SOURCES=webcam=0

# Analytics Configuration
ANALYTICS_ENABLED=True
DETECTION_MODEL=yolov5s
DETECTION_CONFIDENCE=0.4
TRACKING_ENABLED=True
HEATMAP_ENABLED=True
DETECTION_INTERVAL=1

# MQTT Configuration
MQTT_ENABLED=False
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=video_analytics

# Database Configuration
DB_ENABLED=False
INFLUXDB_URL=http://localhost:8086
INFLUXDB_TOKEN=your_influxdb_token
INFLUXDB_ORG=your_org
INFLUXDB_BUCKET=video_analytics
```

## Running the Client

### Desktop Client

Run the Python client:
```bash
python client/viewer.py
```

### Web Client

Navigate to the API server in your browser:
```
http://localhost:8000
```

Or open the static web client directly:
```
client/web_client.html
```

## Adding Video Sources

Video sources can be added in several ways:

### 1. Through the .env file

Edit the `VIDEO_SOURCES` variable in the `.env` file:
```
VIDEO_SOURCES=webcam=0,ip_cam=rtsp://admin:password@192.168.1.100:554/stream
```

### 2. Through the REST API

Send a POST request to add a source:
```bash
curl -X POST http://localhost:8000/sources/camera1 \
  -H "Content-Type: application/json" \
  -d '{"url": "rtsp://admin:password@192.168.1.100:554/stream", "width": 640, "height": 480}'
```

### 3. Using the Test Generator

For testing without real cameras, use the sample generator:
```bash
python utils/sample_generator.py --objects 5
```

## Working with Streams

### Accessing Raw Streams

Raw video streams can be accessed at:
```
RTSP: rtsp://localhost:8554/streams
HLS: http://localhost:8080/stream
```

### Accessing Annotated Streams

Annotated streams with object detection are available at:
```
RTSP: rtsp://localhost:8554/streams/annotated
HLS: http://localhost:8080/stream/annotated
```

### Individual Source Frames

You can get individual frames from a source via the API:
```
http://localhost:8000/sources/{source_id}/frame?annotate=true
```

## REST API Endpoints

The platform provides a comprehensive REST API for control and monitoring:

### Sources

- `GET /sources` - List all sources
- `GET /sources/{source_id}` - Get source info
- `POST /sources/{source_id}` - Add a source
- `DELETE /sources/{source_id}` - Remove a source
- `POST /sources/{source_id}/start` - Start a source
- `POST /sources/{source_id}/stop` - Stop a source
- `GET /sources/{source_id}/frame` - Get latest frame

### Analytics

- `GET /analytics` - Get analytics for all sources
- `GET /analytics/{source_id}` - Get analytics for a specific source

### Streams

- `GET /streams` - Get stream info
- `POST /streams/{stream_id}` - Create a stream
- `DELETE /streams/{stream_id}` - Remove a stream

### System

- `GET /status` - Get system status
- `POST /system/start` - Start all components
- `POST /system/stop` - Stop all components

## MQTT Integration

If MQTT is enabled, the platform publishes detection events to the following topics:

- `video_analytics/events/detection/{source_id}` - Detection events
- `video_analytics/status` - System status updates

You can also send commands to control the platform:

- `video_analytics/commands/source` - Source commands
- `video_analytics/commands/stream` - Stream commands
- `video_analytics/commands/analytics` - Analytics commands

## Time Series Database

If InfluxDB integration is enabled, analytics data is stored in the database for historical analysis and visualization with tools like Grafana.

## Troubleshooting

### Common Issues

1. **GStreamer Not Found**
   - Ensure GStreamer is installed with all required plugins
   - Check environment variables are set correctly

2. **Camera Access Issues**
   - Verify camera permissions
   - Test the camera directly with tools like `v4l2-ctl` or VLC

3. **Performance Issues**
   - Reduce resolution or framerate
   - Increase `DETECTION_INTERVAL` to process fewer frames
   - Use a smaller model (e.g., `yolov5n` instead of `yolov5s`)

### Logs

Logs are stored in the `logs` directory. Check these for detailed error information.

## Advanced Usage

### Custom ML Models

You can use custom ML models by:
1. Placing the model file in the `models` directory
2. Setting the `DETECTION_MODEL` configuration to the model filename

### Stream Customization

You can customize encoding parameters via the API:
```bash
curl -X POST http://localhost:8000/streams/custom_stream \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "webcam", 
    "stream_type": "raw", 
    "width": 1280, 
    "height": 720, 
    "framerate": 30, 
    "bitrate": 2000
  }'
```

### Containerized Deployment

For production deployments, use Docker Compose to orchestrate all components:
```bash
docker-compose up -d
```

This will start the platform along with:
- MQTT broker (Mosquitto)
- Time series database (InfluxDB)
- Visualization dashboard (Grafana) 