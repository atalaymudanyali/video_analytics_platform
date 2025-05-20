#!/usr/bin/env python3
"""
Setup script for the Video Analytics Platform.
Creates necessary directories, configuration files, and initializes the environment.
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

def create_directory_structure():
    """Create the base directory structure for the project."""
    print("Creating directory structure...")
    
    # Base directories
    directories = [
        "ingest",
        "analytics",
        "streaming",
        "api",
        "mqtt",
        "client",
        "docs",
        "models",
        "logs",
        "mosquitto/config",
        "mosquitto/data",
        "mosquitto/log",
        "influxdb/data",
        "influxdb/config",
        "grafana/data"
    ]
    
    # Create each directory
    for directory in directories:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {path}")
    
    # Create __init__.py files for Python modules
    python_packages = ["ingest", "analytics", "streaming", "api", "mqtt", "client"]
    for package in python_packages:
        init_file = Path(package) / "__init__.py"
        if not init_file.exists():
            init_file.touch()
            print(f"Created file: {init_file}")

def create_mosquitto_config():
    """Create Mosquitto MQTT broker configuration file."""
    print("Creating Mosquitto configuration...")
    
    config_path = Path("mosquitto/config/mosquitto.conf")
    if not config_path.exists():
        with open(config_path, "w") as f:
            f.write("""# Mosquitto configuration for Video Analytics Platform
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data
log_dest file /mosquitto/log/mosquitto.log
""")
        print(f"Created Mosquitto config: {config_path}")

def create_docker_files():
    """Check if Docker files exist and create them if they don't."""
    print("Checking Docker files...")
    
    # Docker Compose file
    compose_file = Path("docker-compose.yml")
    if not compose_file.exists():
        print(f"Docker Compose file not found: {compose_file}")
        print("Please create docker-compose.yml manually or re-run the project setup.")
    
    # Dockerfile
    dockerfile = Path("Dockerfile")
    if not dockerfile.exists():
        print(f"Dockerfile not found: {dockerfile}")
        print("Please create Dockerfile manually or re-run the project setup.")

def create_env_file():
    """Create a default .env file with configuration."""
    print("Creating environment file...")
    
    env_file = Path(".env")
    env_example = Path(".env.example")
    
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)
        print(f"Created .env file from example: {env_file}")
    elif not env_file.exists():
        with open(env_file, "w") as f:
            f.write("""# Server Configuration
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
""")
        print(f"Created new .env file: {env_file}")

def install_dependencies():
    """Check and install Python dependencies."""
    print("Checking Python dependencies...")
    
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print(f"Requirements file not found: {requirements_file}")
        print("Please create requirements.txt manually or re-run the project setup.")
        return
    
    try:
        print("Installing Python dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        print("Dependencies installed successfully.")
    except subprocess.CalledProcessError:
        print("Error installing dependencies. Please install them manually:")
        print(f"pip install -r {requirements_file}")

def download_models():
    """Download ML models for object detection."""
    print("Checking for ML models...")
    
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    
    # Check if models exist
    yolov5_model = models_dir / "yolov5s.pt"
    
    if not yolov5_model.exists():
        print("YOLOv5 model not found. To download, run:")
        print("python -c \"import torch; torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)\"")

def verify_setup():
    """Verify that the setup is complete and ready to run."""
    print("\nVerifying setup...")
    
    # Check essential files
    essential_files = [
        "main.py",
        "requirements.txt",
        ".env"
    ]
    
    missing_files = [file for file in essential_files if not Path(file).exists()]
    
    if missing_files:
        print("Warning: The following essential files are missing:")
        for file in missing_files:
            print(f"  - {file}")
        print("Please create these files before running the application.")
    else:
        print("All essential files are present.")
    
    # Check essential directories
    essential_dirs = [
        "ingest",
        "analytics",
        "streaming",
        "api",
        "client",
        "logs"
    ]
    
    missing_dirs = [dir_name for dir_name in essential_dirs if not Path(dir_name).is_dir()]
    
    if missing_dirs:
        print("Warning: The following essential directories are missing:")
        for dir_name in missing_dirs:
            print(f"  - {dir_name}")
        print("Please create these directories before running the application.")
    else:
        print("All essential directories are present.")
    
    # Final message
    if not missing_files and not missing_dirs:
        print("\nSetup verification completed successfully.")
        print("You can run the application with: python main.py")
    else:
        print("\nSetup verification completed with warnings.")
        print("Please address the issues before running the application.")

def main():
    """Main function to execute setup tasks."""
    parser = argparse.ArgumentParser(description="Setup the Video Analytics Platform")
    parser.add_argument("--skip-deps", action="store_true", help="Skip dependency installation")
    parser.add_argument("--skip-models", action="store_true", help="Skip model download information")
    args = parser.parse_args()
    
    print("Setting up Video Analytics Platform...")
    
    create_directory_structure()
    create_mosquitto_config()
    create_docker_files()
    create_env_file()
    
    if not args.skip_deps:
        install_dependencies()
    
    if not args.skip_models:
        download_models()
    
    verify_setup()
    
    print("\nSetup completed!")

if __name__ == "__main__":
    main() 