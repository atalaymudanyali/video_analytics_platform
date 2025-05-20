# Video Analytics Platform Architecture

This document describes the high-level architecture of the Video Analytics Platform.

## System Components

```
┌─────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│                 │     │                   │     │                   │
│  Video Sources  │────▶│  Ingest Module    │────▶│  Analytics Engine │
│  (Webcams/RTSP) │     │  (GStreamer)      │     │  (OpenCV/ML)      │
│                 │     │                   │     │                   │
└─────────────────┘     └───────────────────┘     └─────────┬─────────┘
                                                           │
                                                           │
                                                           ▼
┌─────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│                 │     │                   │     │                   │
│  Client Viewer  │◀────│  Streaming Server │◀────│  Frame Processing │
│  (OpenCV/Web)   │     │  (RTSP/HLS)       │     │  (Annotations)    │
│                 │     │                   │     │                   │
└─────────┬───────┘     └───────┬───────────┘     └───────────────────┘
          │                     │
          │                     │
          ▼                     ▼
┌─────────────────────────────────────────────┐     ┌───────────────────┐
│                                             │     │                   │
│               REST API Server               │────▶│    MQTT Broker    │
│               (FastAPI)                     │     │    (Optional)     │
│                                             │     │                   │
└───────────────────────┬─────────────────────┘     └───────────────────┘
                        │
                        │
                        ▼
                ┌───────────────────┐
                │                   │
                │    Time Series    │
                │    Database       │
                │    (Optional)     │
                │                   │
                └───────────────────┘
```

## Data Flow

1. **Video Ingestion**:
   - The system captures video from multiple sources (webcams, IP cameras, RTSP streams).
   - The ingest module uses GStreamer pipelines to handle different video formats and protocols.

2. **Analytics Processing**:
   - Frames from video sources are processed by the analytics engine.
   - Object detection models (YOLOv5, SSD) identify objects in the frames.
   - Additional analytics like motion tracking and heatmaps are generated.

3. **Frame Annotation**:
   - Detected objects are annotated on video frames with bounding boxes and labels.
   - Analytics overlays (heatmaps, statistics) are added to the frames.

4. **Video Streaming**:
   - Both raw and annotated video streams are published via RTSP and HLS.
   - The streaming server handles encoding and streaming protocols.

5. **API Control**:
   - A REST API provides endpoints for controlling and monitoring the system.
   - Clients can start/stop streams, adjust parameters, and query analytics.

6. **Event Messaging (Optional)**:
   - MQTT messaging provides real-time event notifications and control commands.
   - Detection events, system status, and alerts are published to MQTT topics.

7. **Data Storage (Optional)**:
   - Analytics data can be stored in a time series database (InfluxDB).
   - Historical data can be visualized with tools like Grafana.

## Component Interactions

### Video Source Manager
- Manages connections to multiple video sources
- Handles reconnection and error recovery
- Provides frames to the analytics engine

### Analytics Engine
- Processes video frames using AI models
- Generates detection results and metadata
- Creates analytics visualizations (heatmaps, etc.)

### Streaming Server
- Publishes multiple video streams
- Supports different streaming protocols
- Handles encoding and frame rate control

### API Server
- Provides RESTful endpoints for system control
- Serves as the main interface for clients
- Handles authentication and access control

### MQTT Client
- Publishes detection events and system status
- Subscribes to control commands
- Provides real-time communication

### Client Viewer
- Displays video streams with annotations
- Shows analytics information and statistics
- Provides user controls for viewing options

## Deployment Architecture

The system can be deployed as:

1. **Single-node deployment**:
   - All components run on a single machine
   - Suitable for small-scale deployments

2. **Containerized deployment**:
   - Components run in Docker containers
   - Orchestrated with Docker Compose
   - Easier deployment and scaling

3. **Distributed deployment**:
   - Components distributed across multiple machines
   - Video processing scaled horizontally
   - Suitable for large-scale installations 