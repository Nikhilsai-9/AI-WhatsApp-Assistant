# =============================================================================
# Railway Deployment Variables
# =============================================================================
# Configure these in Railway Dashboard > Variables
# Alternatively, use railway variables CLI: railway variables --set KEY=VALUE

# =============================================================================
# BACKEND SERVICE (Root Directory: backend)
# =============================================================================

# GENERAL
APP_ENV=production
APP_DEBUG=false
APP_TIMEZONE=Asia/Kolkata
APP_URL=https://your-backend-url.up.railway.app
APP_SECRET=<32-char-random-secret>

# DATABASE (Use Railway PostgreSQL)
DATABASE_URL=<your-railway-postgres-url>
POSTGRES_HOST=<auto-from-railway>
POSTGRES_PORT=5432
POSTGRES_USER=<auto-from-railway>
POSTGRES_PASSWORD=<auto-from-railway>
POSTGRES_DB=<auto-from-railway>

# REDIS (Use Railway Redis)
REDIS_URL=<your-railway-redis-url>

# JWT
JWT_SECRET=<32-char-random-secret>

# ENCRYPTION
ENCRYPTION_KEY=<fernet-key>

# AI PROVIDER
AI_PROVIDER=gemini
GEMINI_API_KEY=<your-api-key>

# BRIDGE
BRIDGE_URL=http://whatsapp-bridge:3001
BRIDGE_WEBHOOK_SECRET=<random-secret>

# =============================================================================
# WHATSAPP BRIDGE SERVICE (Root Directory: whatsapp-bridge)
# =============================================================================

PORT=3001
BACKEND_URL=<your-backend-url>
BRIDGE_WEBHOOK_SECRET=<same-as-backend>
WHATSAPP_WEBHOOK_VERIFY_TOKEN=<random-token>
WHATSAPP_PHONE_NUMBER_ID=<from-meta-console>
META_ACCESS_TOKEN=<from-meta-console>
META_APP_SECRET=<from-meta-console>
LOG_LEVEL=info

# =============================================================================
# RAILWAY POSTGRES ADDON (if using)
# =============================================================================
# These are automatically injected by Railway PostgreSQL addon
# POSTGRES_USER
# POSTGRES_PASSWORD
# POSTGRES_HOST
# POSTGRES_URL (full connection string)

# =============================================================================
# RAILWAY REDIS ADDON (if using)
# =============================================================================
# REDIS_HOST
# REDIS_PASSWORD
# REDIS_URL (full connection string)
