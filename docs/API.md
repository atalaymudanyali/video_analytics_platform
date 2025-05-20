# Video Analytics Platform API Documentation

This document describes the REST API endpoints available in the Video Analytics Platform.

## Base URL

By default, the API server runs at `http://localhost:8000`

## API Endpoints

### System Information

#### GET /
- **Description**: Root endpoint returning API information
- **Response**: Basic API information including version and documentation URL

#### GET /status
- **Description**: Get platform status
- **Response**: Current status of video sources, analytics engine, and streaming server

### Video Sources

#### GET /sources
- **Description**: Get all video sources
- **Response**: List of all configured video sources and their status

#### GET /sources/{source_id}
- **Description**: Get information about a specific video source
- **Parameters**:
  - `source_id`: String (path parameter)
- **Response**: Detailed information about the specified source
- **Error**: 404 if source not found

#### POST /sources/{source_id}
- **Description**: Add a new video source
- **Parameters**:
  - `source_id`: String (path parameter)
  - Request body:
    ```json
    {
        "url": "string",
        "width": "integer (optional, default: 640)",
        "height": "integer (optional, default: 480)"
    }
    ```
- **Response**: Success confirmation
- **Error**: 400 if failed to add source

#### DELETE /sources/{source_id}
- **Description**: Remove a video source
- **Parameters**:
  - `source_id`: String (path parameter)
- **Response**: Success confirmation
- **Error**: 404 if source not found

#### POST /sources/{source_id}/start
- **Description**: Start a video source
- **Parameters**:
  - `source_id`: String (path parameter)
- **Response**: Success confirmation
- **Error**: 400 if failed to start source

#### POST /sources/{source_id}/stop
- **Description**: Stop a video source
- **Parameters**:
  - `source_id`: String (path parameter)
- **Response**: Success confirmation
- **Error**: 400 if failed to stop source

#### GET /sources/{source_id}/frame
- **Description**: Get the latest frame from a video source
- **Parameters**:
  - `source_id`: String (path parameter)
  - `annotate`: Boolean (query parameter, optional) - Apply analytics overlay
- **Response**: JPEG image
- **Error**: 404 if no frame available

### Analytics

#### GET /analytics
- **Description**: Get analytics results for all sources
- **Response**: Analytics results for all active sources

#### GET /analytics/{source_id}
- **Description**: Get analytics results for a specific source
- **Parameters**:
  - `source_id`: String (path parameter)
- **Response**: Analytics results for the specified source
- **Error**: 404 if no results found

### Streaming

#### GET /streams
- **Description**: Get information about all streams
- **Response**: List of all active streams and their configurations

#### POST /streams/{stream_id}
- **Description**: Create a new stream
- **Parameters**:
  - `stream_id`: String (path parameter)
  - Request body:
    ```json
    {
        "source_id": "string",
        "stream_type": "string (optional, default: 'raw')",
        "width": "integer (optional, default: 640)",
        "height": "integer (optional, default: 480)",
        "framerate": "integer (optional, default: 30)",
        "bitrate": "integer (optional, default: 1000)"
    }
    ```
- **Response**: Success confirmation
- **Error**: 400 if failed to create stream

#### DELETE /streams/{stream_id}
- **Description**: Remove a stream
- **Parameters**:
  - `stream_id`: String (path parameter)
- **Response**: Success confirmation
- **Error**: 404 if stream not found

### System Control

#### POST /system/start
- **Description**: Start all components of the system
- **Response**: Success confirmation

#### POST /system/stop
- **Description**: Stop all components of the system
- **Response**: Success confirmation

## Error Responses

All error responses follow this format:
```json
{
    "detail": "Error message describing what went wrong"
}
```

Common HTTP status codes:
- 200: Success
- 400: Bad Request
- 404: Not Found
- 500: Internal Server Error

## Notes

- All endpoints return JSON responses unless otherwise specified
- The frame endpoint returns JPEG images
- Authentication is not implemented in the current version 