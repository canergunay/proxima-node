.PHONY: build install dev clean deploy

# Build frontend and copy to backend/static
build:
	cd frontend && npm ci && npx vite build

# Pull, rebuild the UI, restart the service, verify. Run as root.
# Updating the backend without rebuilding the frontend serves a stale UI —
# see the note at the top of deploy.sh.
deploy:
	@./deploy.sh $(ARGS)

# Set up Python venv and install dependencies
install:
	cd backend && python3 -m venv venv && venv/bin/pip install -r requirements.txt

# Development: run backend (frontend uses vite dev server with proxy)
dev:
	cd backend && python app.py

# Clean build artifacts
clean:
	rm -rf backend/static frontend/node_modules frontend/dist
