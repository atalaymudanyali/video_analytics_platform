.PHONY: setup deps models install run run-client clean docker-build docker-run docker-clean

# Default target
all: setup

# Setup the project
setup:
	python setup_project.py

# Install dependencies
deps:
	pip install -r requirements.txt

# Download ML models
models:
	mkdir -p models
	python -c "import torch; yolo = torch.hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True); yolo.save('models/yolov5s.pt')"

# Install the project
install: deps models

# Run the server
run:
	python main.py

# Run the client
run-client:
	python client/viewer.py

# Clean up
clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".DS_Store" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +
	find . -type d -name "*.egg" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name ".coverage" -exec rm -r {} +
	find . -type d -name "htmlcov" -exec rm -r {} +
	find . -type d -name ".benchmarks" -exec rm -r {} +
	find . -type d -name "logs/*.log" -exec rm -r {} +

# Docker commands
docker-build:
	docker-compose build

docker-run:
	docker-compose up

docker-clean:
	docker-compose down
	docker-compose rm -f

# Help
help:
	@echo "Available targets:"
	@echo "  setup       - Set up the project (directories, configs)"
	@echo "  deps        - Install Python dependencies"
	@echo "  models      - Download ML models"
	@echo "  install     - Install dependencies and models"
	@echo "  run         - Run the server"
	@echo "  run-client  - Run the client viewer"
	@echo "  clean       - Clean up temporary files"
	@echo "  docker-build - Build Docker images"
	@echo "  docker-run  - Run with Docker Compose"
	@echo "  docker-clean - Clean up Docker containers" 