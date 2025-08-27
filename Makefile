.PHONY: run stop build clean logs health help

# Default target
help:
	@echo "Available commands:"
	@echo "  make run     - Build and run the container with .env file"
	@echo "  make stop    - Stop and remove the container"
	@echo "  make build   - Build the Docker image"
	@echo "  make clean   - Stop container and remove image"
	@echo "  make logs    - View container logs"
	@echo "  make health  - Check service health"

# Build and run the container with .env file
run: stop build
	@echo "🚀 Starting Langfuse Observability Service..."
	@if [ ! -f .env ]; then \
		echo "⚠️  .env file not found. Copy .env.example to .env and configure it."; \
		exit 1; \
	fi
	docker-compose --env-file .env up -d
	@echo "✅ Service started! Check logs with 'make logs'"
	@echo "🔗 Service URL: http://localhost:8000"
	@echo "🏥 Health check: http://localhost:8000/health"
	@echo "📚 API docs: http://localhost:8000/docs"

# Stop and remove containers
stop:
	@echo "🛑 Stopping containers..."
	@docker-compose down --remove-orphans 2>/dev/null || true

# Build the Docker image
build:
	@echo "🏗️  Building Docker image..."
	docker-compose build

# Clean up containers and images
clean: stop
	@echo "🧹 Cleaning up..."
	@docker-compose down --volumes --remove-orphans 2>/dev/null || true
	@docker image rm langfuse-observability-langfuse-trace-service 2>/dev/null || true
	@echo "✅ Cleanup complete"

# View logs
logs:
	docker-compose logs -f langfuse-trace-service

# Health check
health:
	@echo "🏥 Checking service health..."
	@curl -s http://localhost:8000/health | jq '.' || echo "❌ Service not responding. Is it running? Try 'make run'"