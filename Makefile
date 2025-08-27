.PHONY: run stop build clean logs logs-api logs-worker health help monitoring

# Default target
help:
	@echo "Available commands:"
	@echo "  make run        - Build and run all services with .env file"
	@echo "  make monitoring - Run with Flower monitoring (port 5555)"
	@echo "  make stop       - Stop and remove all containers"
	@echo "  make build      - Build all Docker images"
	@echo "  make clean      - Stop containers and remove images"
	@echo "  make logs       - View all container logs"
	@echo "  make logs-api   - View API container logs"
	@echo "  make logs-worker - View worker container logs"
	@echo "  make health     - Check service health"

# Build and run all services with .env file
run: stop build
	@echo "🚀 Starting Langfuse Observability Services..."
	@if [ ! -f .env ]; then \
		echo "⚠️  .env file not found. Copy .env.example to .env and configure it."; \
		exit 1; \
	fi
	docker-compose --env-file .env up -d
	@echo "✅ Services started! Check logs with 'make logs'"
	@echo "🔗 API URL: http://localhost:8000"
	@echo "🏥 Health check: http://localhost:8000/health"
	@echo "📚 API docs: http://localhost:8000/docs"
	@echo "👥 Redis: localhost:6379"

# Run with monitoring (Flower)
monitoring: stop build
	@echo "🚀 Starting services with Flower monitoring..."
	@if [ ! -f .env ]; then \
		echo "⚠️  .env file not found. Copy .env.example to .env and configure it."; \
		exit 1; \
	fi
	docker-compose --env-file .env --profile monitoring up -d
	@echo "✅ Services started with monitoring!"
	@echo "🔗 API URL: http://localhost:8000"
	@echo "🌸 Flower monitoring: http://localhost:5555"
	@echo "🏥 Health check: http://localhost:8000/health"

# Stop and remove containers
stop:
	@echo "🛑 Stopping containers..."
	@docker-compose down --remove-orphans 2>/dev/null || true

# Build all Docker images
build:
	@echo "🏗️  Building Docker images..."
	docker-compose build

# Clean up containers and images
clean: stop
	@echo "🧹 Cleaning up..."
	@docker-compose down --volumes --remove-orphans 2>/dev/null || true
	@docker image rm langfuse-observability-langfuse-api 2>/dev/null || true
	@docker image rm langfuse-observability-langfuse-worker 2>/dev/null || true
	@echo "✅ Cleanup complete"

# View all logs
logs:
	docker-compose logs -f

# View API logs
logs-api:
	docker-compose logs -f langfuse-api

# View worker logs
logs-worker:
	docker-compose logs -f langfuse-worker

# Health check
health:
	@echo "🏥 Checking service health..."
	@curl -s http://localhost:8000/health | jq '.' || echo "❌ Service not responding. Is it running? Try 'make run'"