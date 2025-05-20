# Video Analytics Platform Setup Guide

This guide provides detailed instructions for setting up and configuring the Video Analytics Platform.

## Prerequisites

- Docker and Docker Compose
- Python 3.8 or higher
- NVIDIA GPU (optional, for accelerated inference)
- NVIDIA Container Toolkit (if using GPU)
- GStreamer 1.0 or higher

## Installation Steps

### 1. Clone the Repository

```bash
git clone <repository-url>
cd video_analytics_platform
```

### 2. Environment Setup

#### Windows Setup
```bash
# Run the Windows setup script
python setup_windows.py

# Or use the batch file
run_platform.bat
```

#### Linux/Mac Setup
```bash
# Install dependencies
make install

# Setup environment
make setup
```

### 3. Configuration

1. Create a `.env` file in the root directory:
```ini
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# MQTT Configuration
MQTT_ENABLED=true
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883

# Analytics Configuration
ANALYTICS_MODEL=yolov5n
ANALYTICS_DEVICE=cuda  # or cpu
ANALYTICS_CONFIDENCE=0.5

# Streaming Configuration
STREAM_PORT=8554
```

2. Configure video sources in `config/sources.yaml`:
```yaml
sources:
  local_car:
    url: file:///path/to/car-detection.mp4
    width: 640
    height: 480
  rtsp_camera:
    url: rtsp://camera-ip:554/stream
    width: 1280
    height: 720
```

### 4. Docker Setup

1. Build the containers:
```bash
docker-compose build
```

2. Start the services:
```bash
docker-compose up -d
```

The following containers will be started:
- Video Analytics Platform
- InfluxDB (Time series database)
- Mosquitto MQTT Broker
- Grafana (Visualization)

### 5. Model Setup

1. Download the YOLOv5n model:
```bash
# The setup script will handle this automatically
python setup_project.py --download-models
```

2. (Optional) Add custom models to the `models/` directory

### 6. Verification

1. Check if services are running:
```bash
docker-compose ps
```

2. Test the API:
```bash
curl http://localhost:8000/status
```

3. Access the interfaces:
- API Documentation: http://localhost:8000/docs
- Grafana Dashboard: http://localhost:3000
- Frame View: http://localhost:8000/sources/local_car/frame

## Troubleshooting

### Common Issues

1. **Docker Container Fails to Start**
   - Check Docker logs: `docker-compose logs`
   - Verify port availability
   - Ensure NVIDIA drivers are installed for GPU support

2. **Video Source Not Found**
   - Verify file paths in sources.yaml
   - Check file permissions
   - Ensure network connectivity for RTSP sources

3. **MQTT Connection Issues**
   - Verify Mosquitto broker is running
   - Check MQTT port availability
   - Review broker logs: `docker-compose logs mosquitto`

4. **Performance Issues**
   - Check GPU utilization
   - Monitor system resources
   - Adjust video resolution and framerate

### Logs

Log files are stored in the `logs/` directory:
- `platform.log`: Main application logs
- `analytics.log`: Model inference logs
- `streaming.log`: GStreamer pipeline logs

## Security Notes

1. Default configurations are for development only
2. Change default passwords in production
3. Enable authentication for production deployments
4. Secure MQTT broker access
5. Use HTTPS for API access in production

## Next Steps

After successful setup:
1. Review the [USAGE.md](USAGE.md) guide
2. Explore the [API.md](API.md) documentation
3. Check the [ARCHITECTURE.md](ARCHITECTURE.md) for system details 