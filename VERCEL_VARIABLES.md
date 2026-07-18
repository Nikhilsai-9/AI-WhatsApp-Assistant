# =============================================================================
# Vercel Frontend Deployment Variables
# =============================================================================
# Configure these in Vercel Dashboard > Settings > Environment Variables

# =============================================================================
# FRONTEND (frontend/)
# =============================================================================

# API Configuration
VITE_API_URL=https://your-backend-url.up.railway.app
VITE_APP_NAME=AI WhatsApp Assistant
VITE_APP_ENV=production

# Optional: Analytics
# VITE_GA_ID=G-XXXXXXXXXX

# =============================================================================
# RAILWAY BACKEND (backend/)
# =============================================================================
# Configure these in your Railway backend service

# GENERAL
APP_ENV=production
APP_DEBUG=false
APP_URL=https://your-backend-url.up.railway.app
APP_SECRET=<32-char-random-secret>

# DATABASE
DATABASE_URL=<railway-postgres-url>

# REDIS
REDIS_URL=<railway-redis-url>

# JWT
JWT_SECRET=<32-char-random-secret>

# ENCRYPTION
ENCRYPTION_KEY=<fernet-key>

# AI
AI_PROVIDER=gemini
GEMINI_API_KEY=<your-api-key>

# BRIDGE
BRIDGE_URL=https://your-bridge-url.up.railway.app
BRIDGE_WEBHOOK_SECRET=<random-secret>

# =============================================================================
# WHATSAPP BRIDGE (whatsapp-bridge/)
# =============================================================================

PORT=3001
BACKEND_URL=https://your-backend-url.up.railway.app
BRIDGE_WEBHOOK_SECRET=<same-as-backend>
WHATSAPP_WEBHOOK_VERIFY_TOKEN=<random-token>
WHATSAPP_PHONE_NUMBER_ID=<from-meta>
META_ACCESS_TOKEN=<from-meta>
META_APP_SECRET=<from-meta>
LOG_LEVEL=info
