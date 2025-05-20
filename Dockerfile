FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TF_CPP_MIN_LOG_LEVEL=2
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg
ENV MATPLOTLIBRC=/etc/matplotlibrc

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-opencv \
    python3-gi \
    python3-gst-1.0 \
    python3-gi-cairo \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-rtsp \
    gstreamer1.0-libav \
    libgstrtspserver-1.0-dev \
    libgirepository1.0-dev \
    libcairo2-dev \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
    gir1.2-gst-rtsp-server-1.0 \
    mosquitto-clients \
    ninja-build \
    pkg-config \
    fonts-liberation \
    fontconfig \
    fonts-dejavu \
    fonts-freefont-ttf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install meson from pip to get a newer version
RUN pip3 install --no-cache-dir meson>=0.63.3

# Create app directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Create directories for models and logs
RUN mkdir -p models logs

# Initialize the font cache
RUN fc-cache -fv

# Configure matplotlib to use Agg backend
RUN echo "backend: Agg" > /etc/matplotlibrc

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x main.py client/viewer.py

# Default port for the API server
EXPOSE 8000
# Default port for RTSP streaming
EXPOSE 8554
# Default port for HLS streaming
EXPOSE 8080
# Default port for MQTT
EXPOSE 1883

# Command to run the application
CMD ["python3", "main.py"] 