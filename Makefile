# ─────────────────────────────────────────────────────────────────
#  AI WhatsApp Personal Assistant — developer Makefile
# ─────────────────────────────────────────────────────────────────

.PHONY: help install up down logs ps restart build rebuild \
        backend-shell bridge-shell db-shell redis-shell \
        migrate migration revision seed test lint format clean \
        keys qr open

COMPOSE ?= docker compose

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ─── Lifecycle ───────────────────────────────────────────────────
up:    ## Start all services
	$(COMPOSE) up -d
	@echo "✅ Stack is up. Dashboard: http://localhost:3000"

down:  ## Stop all services
	$(COMPOSE) down

restart: ## Restart services
	$(COMPOSE) restart

ps:    ## Show running services
	$(COMPOSE) ps

logs:  ## Tail logs
	$(COMPOSE) logs -f --tail=200

build: ## Build all images
	$(COMPOSE) build

rebuild: ## Rebuild without cache
	$(COMPOSE) build --no-cache

# ─── Shells ─────────────────────────────────────────────────────
backend-shell: ## Bash into backend container
	$(COMPOSE) exec backend bash

bridge-shell: ## Bash into bridge container
	$(COMPOSE) exec whatsapp-bridge sh

db-shell: ## Open psql
	$(COMPOSE) exec postgres psql -U $$POSTGRES_USER -d $$POSTGRES_DB

redis-shell: ## Open redis-cli
	$(COMPOSE) exec redis redis-cli -a $$REDIS_PASSWORD

# ─── DB Migrations & Seeds ──────────────────────────────────────
migrate: ## Apply all pending migrations
	$(COMPOSE) exec backend alembic upgrade head

revision: ## Create new migration (msg="...")
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(msg)"

seed: ## Seed sample data (dev only)
	$(COMPOSE) exec backend python -m app.scripts.seed

# ─── Dev / Test ─────────────────────────────────────────────────
test:  ## Run backend pytest suite
	$(COMPOSE) exec backend pytest -q

lint:  ## Run ruff + eslint
	$(COMPOSE) exec backend ruff check app
	cd frontend && pnpm lint

format:
	$(COMPOSE) exec backend ruff format app
	cd frontend && pnpm format

# ─── Maintenance ────────────────────────────────────────────────
keys:  ## Generate secure secrets
	@echo "APP_SECRET=$$(openssl rand -hex 32)"
	@echo "JWT_SECRET=$$(openssl rand -hex 32)"
	@echo "POSTGRES_PASSWORD=$$(openssl rand -hex 16)"
	@echo "REDIS_PASSWORD=$$(openssl rand -hex 16)"
	@echo "BRIDGE_WEBHOOK_SECRET=$$(openssl rand -hex 32)"
	@echo "ENCRYPTION_KEY=$$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")"

qr:    ## Show WhatsApp QR (login)
	@curl -s http://localhost:3001/qr

open:  ## Open dashboard in browser
ifeq ($(OS),Windows)
	start http://localhost:3000
else
	open http://localhost:3000
endif

clean: ## ⚠ Remove volumes and caches
	$(COMPOSE) down -v
	rm -rf backend/.pytest_cache backend/app/**/__pycache__
