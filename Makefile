.PHONY: dev-backend dev-frontend build test docker-build docker-dev lock-deps setup-backend setup-frontend clean

# Backend development
setup-backend:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install pip-tools pytest

dev-backend:
	.venv/bin/uvicorn backend.app:app --host 0.0.0.0 --port 8487 --reload

# Frontend development
setup-frontend:
	cd frontend && npm install

dev-frontend:
	cd frontend && npm run dev

# Build frontend for production
build:
	cd frontend && npm run build

# Run tests
test:
	.venv/bin/python -m pytest tests/ -v

# Lock Python dependencies
lock-deps:
	.venv/bin/pip-compile requirements.in

# Docker
docker-build:
	docker compose -f docker-compose.dev.yml build

docker-dev:
	mkdir -p test-library test-dest
	docker compose -f docker-compose.dev.yml up

docker-dev-detached:
	mkdir -p test-library test-dest
	docker compose -f docker-compose.dev.yml up -d

docker-down:
	docker compose -f docker-compose.dev.yml down

# Clean
clean:
	rm -rf .venv frontend/node_modules frontend/dist __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
