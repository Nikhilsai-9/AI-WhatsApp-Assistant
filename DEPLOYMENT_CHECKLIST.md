# =============================================================================
# Production Deployment Checklist
# =============================================================================

## Pre-Deployment Requirements

### 1. Account Setup
- [ ] Railway account created
- [ ] Vercel account created (for frontend)
- [ ] Meta WhatsApp Business account setup
- [ ] PostgreSQL database provisioned (Railway PostgreSQL)
- [ ] Redis cache provisioned (Railway Redis)

### 2. API Keys
- [ ] Gemini API key obtained from Google AI Studio
- [ ] Meta WhatsApp API credentials ready:
  - Phone Number ID
  - Access Token
  - App Secret
- [ ] Sentry DSN (optional, for error tracking)

### 3. Domain & SSL
- [ ] Domain configured (optional but recommended)
- [ ] SSL certificates (handled by Railway/Vercel)

---

## Railway Backend Deployment

### 1. Create Railway Project
```bash
npm i -g @railway/cli
railway login
cd AI-WhatsApp-Assistant
railway init
```

### 2. Configure Backend Service
- Set **Root Directory**: `backend`
- Build Command: Leave empty (Dockerfile will be used)
- Start Command: Leave empty

### 3. Add PostgreSQL
```bash
railway add --database
```
Or use Railway Dashboard > Add Database > PostgreSQL

### 4. Add Redis (optional but recommended)
```bash
railway add --redis
```

### 5. Set Environment Variables (Backend)
Copy from `RAILWAY_VARIABLES.md` and set values:

```
APP_ENV=production
APP_DEBUG=false
APP_URL=https://your-backend-url.up.railway.app
APP_SECRET=<generate-32-char-key>
DATABASE_URL=<from-railway-postgres>
REDIS_URL=<from-railway-redis>
JWT_SECRET=<generate-32-char-key>
ENCRYPTION_KEY=<generate-fernet-key>
AI_PROVIDER=gemini
GEMINI_API_KEY=<your-key>
BRIDGE_URL=http://whatsapp-bridge:3001
BRIDGE_WEBHOOK_SECRET=<generate-random>
```

### 6. Deploy Backend
```bash
railway up
```

### 7. Verify Backend
- Health check: `https://your-backend-url.up.railway.app/health`
- Check logs for any startup errors

---

## Railway WhatsApp Bridge Deployment

### 1. Create Second Railway Service
```bash
railway service create whatsapp-bridge
```

### 2. Configure Bridge Service
- Set **Root Directory**: `whatsapp-bridge`
- Build Command: Leave empty
- Start Command: `node src/index.js`

### 3. Set Environment Variables (Bridge)
```
PORT=3001
BACKEND_URL=https://your-backend-url.up.railway.app
BRIDGE_WEBHOOK_SECRET=<same-as-backend>
WHATSAPP_WEBHOOK_VERIFY_TOKEN=<generate-random>
WHATSAPP_PHONE_NUMBER_ID=<from-meta>
META_ACCESS_TOKEN=<from-meta>
META_APP_SECRET=<from-meta>
LOG_LEVEL=info
```

### 4. Deploy Bridge
```bash
railway up
```

---

## Vercel Frontend Deployment

### 1. Connect Repository
- Go to Vercel Dashboard
- Import project from GitHub
- Select `frontend` directory

### 2. Configure Build Settings
- Framework: Vite
- Build Command: `npm run build`
- Output Directory: `dist`

### 3. Set Environment Variables
```
VITE_API_URL=https://your-backend-url.up.railway.app
VITE_APP_NAME=AI WhatsApp Assistant
VITE_APP_ENV=production
```

### 4. Deploy
Click Deploy

---

## WhatsApp Webhook Setup

### 1. Get Railway URLs
```bash
railway status
```
Note down the URLs for backend and bridge services.

### 2. Configure Meta Webhook
1. Go to Meta Developer Console
2. Select your WhatsApp Business app
3. Navigate to Webhooks
4. Add callback URL:
   ```
   https://your-bridge-url.up.railway.app/webhook
   ```
5. Add verify token (same as WHATSAPP_WEBHOOK_VERIFY_TOKEN)

### 3. Subscribe to Webhooks
- Select `messages` field for incoming messages
- Select `message_deliveries` for delivery status
- Select `message_reads` for read receipts

---

## Database Migration

### 1. Run Migrations
```bash
cd backend
railway run alembic upgrade head
```

Or run via Railway CLI:
```bash
railway run --service backend alembic upgrade head
```

---

## Post-Deployment Verification

### Backend
- [ ] Health endpoint responds: `/health`
- [ ] Database connection works
- [ ] Redis connection works
- [ ] API documentation accessible (dev only): `/docs`

### WhatsApp Bridge
- [ ] Status endpoint: `/status` shows "connected"
- [ ] Webhook verified with Meta
- [ ] Test sending a message

### Frontend
- [ ] Login page loads
- [ ] Can authenticate
- [ ] Dashboard displays correctly
- [ ] Contacts sync works

### Integration
- [ ] Send test WhatsApp message
- [ ] Verify AI response received
- [ ] Check message appears in dashboard

---

## Security Checklist

- [ ] All API keys stored as Railway/Vercel secrets
- [ ] No hardcoded secrets in code
- [ ] CORS configured for production domains
- [ ] Rate limiting enabled
- [ ] HTTPS enforced everywhere
- [ ] Webhook signature verification enabled

---

## Monitoring Setup

### Health Checks
- Backend: `https://your-url/health`
- Bridge: `https://your-url/status`

### Logs
```bash
# View backend logs
railway logs --service backend

# View bridge logs
railway logs --service whatsapp-bridge
```

### Error Tracking (Optional)
Set Sentry DSN:
```
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
```

---

## Rollback Plan

### Railway
```bash
# View deployments
railway deployments

# Rollback to previous
railway rollback <deployment-id>
```

### Vercel
```bash
# View deployments
vercel ls

# Rollback
vercel rollback <url>
```

---

## Support & Troubleshooting

### Common Issues

1. **Bridge not connecting**
   - Check META_ACCESS_TOKEN is valid
   - Verify Phone Number ID is correct
   - Check bridge logs for errors

2. **Database connection failed**
   - Verify DATABASE_URL is correct
   - Check PostgreSQL is accessible
   - Check pgvector extension is enabled

3. **AI not responding**
   - Verify GEMINI_API_KEY is set
   - Check API quota not exceeded
   - Check backend logs for errors

4. **Whisper/OCR not working**
   - Verify ffmpeg installed
   - Check tesseract-ocr is available
   - Verify language packs installed

### Debug Commands
```bash
# Backend shell
railway shell backend

# Check environment
railway variables

# View logs
railway logs --service backend --tail 100
```
