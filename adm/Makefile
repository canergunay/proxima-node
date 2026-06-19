.PHONY: build install dev clean

# Build frontend and copy to backend/static
build:
	cd frontend && npm ci && npx vite build

# Set up Python venv and install dependencies
install:
	cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt

# Development: run backend (frontend uses vite dev server with proxy)
dev:
	cd backend && python app.py

# Clean build artifacts
clean:
	rm -rf backend/static frontend/node_modules frontend/dist
