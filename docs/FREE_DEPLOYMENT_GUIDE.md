# Complete Free Deployment Guide
## AI WhatsApp Personal Assistant — Zero Cost Setup

---

## Overview

This guide deploys the entire application using **100% free services**:

| Component | Free Service | Limit |
|-----------|-------------|-------|
| Backend API | Railway | 500 hrs/month |
| Database | Supabase | 500MB storage |
| Redis Cache | Upstash | 10K commands/day |
| Frontend | Vercel | Unlimited |
| WhatsApp API | Meta (Free) | Unlimited |
| AI - Gemini | Google (Free) | 60 req/min |
| AI - Ollama | Local (Free) | Unlimited |
| Webhook Testing | ngrok (Free) | 1 tunnel |

**Total Cost: ₹0 (Free Forever)**

---

## Phase 1: Prepare Your Computer

### Step 1.1: Install Required Software

```bash
# Install Git (version control)
# Download from: https://git-scm.com/download/win

# Install Node.js 18+ (for WhatsApp bridge)
# Download from: https://nodejs.org/

# Install Python 3.11+ (for backend)
# Download from: https://www.python.org/downloads/

# Install Docker Desktop (for local testing)
# Download from: https://docker.com/products/docker-desktop
```

### Step 1.2: Verify Installations

Open Command Prompt and run:

```bash
git --version
node --version
python --version
docker --version
```

---

## Phase 2: Set Up GitHub Repository

### Step 2.1: Create GitHub Account
1. Go to https://github.com
2. Click "Sign Up"
3. Enter email, password, username
4. **Verify email**

### Step 2.2: Create New Repository
1. Click "New repository"
2. Name: `ai-whatsapp-assistant`
3. Select "Public" (free hosting requires public)
4. Click "Create repository"

### Step 2.3: Push Code to GitHub

```bash
# Open Command Prompt in project folder
cd C:\Users\saini\Desktop\ai-whatsapp-assistant

# Initialize git
git init

# Add all files
git add .

# First commit
git commit -m "Initial commit - AI WhatsApp Assistant"

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/ai-whatsapp-assistant.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## Phase 3: Set Up Supabase (Free PostgreSQL)

### Step 3.1: Create Supabase Account
1. Go to https://supabase.com
2. Click "Start your project"
3. Sign up with GitHub (easiest)
4. **Verify email**

### Step 3.2: Create New Project
1. Click "New Project"
2. **Name**: `ai-whatsapp-assistant`
3. **Database Password**: Generate strong password, **SAVE IT**
4. **Region**: Select nearest (Asia: Singapore)
5. Click "Create new project"
6. **Wait 2 minutes** for setup

### Step 3.3: Get Connection String
1. Go to **Settings** → **Database**
2. Scroll to **Connection string**
3. Select **URI** tab
4. Copy the connection string:

```
postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

5. **SAVE THIS** — You'll need it later

### Step 3.4: Enable pgvector Extension
1. Go to **SQL Editor** in Supabase dashboard
2. Run this query:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## Phase 4: Set Up Upstash (Free Redis)

### Step 4.1: Create Upstash Account
1. Go to https://upstash.com
2. Click "Get Started"
3. Sign up with GitHub

### Step 4.2: Create Redis Database
1. Click "Create Database"
2. **Name**: `ai-whatsapp-redis`
3. **Region**: Select nearest
4. **Tier**: Free (10K commands/day)
5. Click "Create"

### Step 4.3: Get Redis URL
1. Copy **REDIS_URL** from the dashboard:

```
redis://default:[PASSWORD]@[ENDPOINT]:6379
```

2. **SAVE THIS**

---

## Phase 5: Set Up Google Gemini (Free AI)

### Step 5.1: Create Google Account
1. Go to https://accounts.google.com
2. Sign in or create account

### Step 5.2: Get Gemini API Key
1. Go to https://aistudio.google.com/app/apikey
2. Click "Create API Key"
3. Click "Create API key in new project"
4. **Copy the API key**
5. **SAVE THIS**

---

## Phase 6: Set Up Meta WhatsApp API (Free)

### Step 6.1: Create Meta Developer Account
1. Go to https://developers.facebook.com
2. Click "My Apps"
3. Click "Create App"
4. Select **"Other"** → **"Business"**
5. **App Name**: `AI WhatsApp Assistant`
6. **App Contact Email**: Your email
7. Click "Create app"

### Step 6.2: Add WhatsApp Product
1. In your app dashboard, click **"Add Products"**
2. Find **WhatsApp** and click "Set up"

### Step 6.3: Get Phone Number ID
1. Go to **WhatsApp** → **Getting Started**
2. Under **API Setup**, find **Phone Number ID**
3. **Copy and SAVE**

### Step 6.4: Get WhatsApp Business Account ID
1. In the same section, find **WhatsApp Business Account ID**
2. **Copy and SAVE**

### Step 6.5: Generate Permanent Access Token
1. Go to **Meta Business Suite**: https://business.facebook.com
2. Click your business (or create one)
3. Go to **Settings** → **System Users**
4. Click **Add System User**
5. **Name**: `WhatsApp Bot`
6. **Role**: Admin
7. Click "Save Changes"
8. Click **Assign Assets**
9. Select your **WhatsApp Business Account**
10. Give **Full Control**
11. Click "Save Changes"
12. Click **Generate Token**
13. Select your app
14. Check ALL permissions
15. Click "Generate Token"
16. **COPY AND SAVE** — This is your `META_ACCESS_TOKEN`

### Step 6.6: Verify Phone Number
1. Go to **WhatsApp** → **Getting Started**
2. Under **Phone Numbers**, add your personal WhatsApp number
3. **Verify** the number with SMS or call
4. Set status to **"Connected"**

---

## Phase 7: Deploy Backend to Railway (Free)

### Step 7.1: Create Railway Account
1. Go to https://railway.app
2. Click "Login" → "Login with GitHub"
3. Authorize the app

### Step 7.2: Deploy Backend
1. Click **"New Project"**
2. Select **"Deploy from GitHub repo"**
3. Find and select `ai-whatsapp-assistant`
4. Railway will detect it's a Python app

### Step 7.3: Configure Environment Variables

In Railway dashboard, go to **Variables** and add:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres

# Redis
REDIS_URL=redis://default:[PASSWORD]@[ENDPOINT]:6379

# Security
APP_SECRET=generate-a-very-long-random-string-here
JWT_ALGORITHM=HS256

# Bridge
BRIDGE_URL=https://your-bridge.railway.app
BRIDGE_WEBHOOK_SECRET=another-random-secret-string

# AI Provider
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key

# Vector Search
EMBEDDING_MODEL=all-MiniLM-L6-v2

# Environment
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Step 7.4: Configure Start Command
1. Go to **Settings** → **Start Command**
2. Enter:

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Step 7.5: Deploy
1. Click **Deploy**
2. Wait 3-5 minutes
3. Your backend URL will be: `https://your-app.up.railway.app`

### Step 7.6: Run Migrations
1. In Railway, go to **Shell**
2. Run:

```bash
cd backend && alembic upgrade head
```

---

## Phase 8: Deploy WhatsApp Bridge to Railway (Free)

### Step 8.1: Create Second Railway Project
1. Create another Railway project
2. Deploy from same GitHub repo

### Step 8.2: Configure for Bridge
1. Set root directory to: `whatsapp-bridge`
2. Set start command: `node src/index.js`

### Step 8.3: Add Environment Variables

```env
# Meta WhatsApp
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
META_ACCESS_TOKEN=your-permanent-access-token
META_APP_SECRET=your-meta-app-secret

# Bridge
BRIDGE_WEBHOOK_SECRET=your-random-secret
BACKEND_URL=https://your-backend.up.railway.app
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your-verify-token

# Port
PORT=3001
```

### Step 8.4: Deploy
1. Click **Deploy**
2. Bridge URL: `https://your-bridge.up.railway.app`

---

## Phase 9: Deploy Frontend to Vercel (Free)

### Step 9.1: Create Vercel Account
1. Go to https://vercel.com
2. Click "Sign Up"
3. Sign up with GitHub

### Step 9.2: Import Project
1. Click **"Add New..."** → **"Project"**
2. Find `ai-whatsapp-assistant`
3. Click **Import**

### Step 9.3: Configure
1. **Root Directory**: `frontend`
2. **Build Command**: `npm run build`
3. **Output Directory**: `dist`

### Step 9.4: Add Environment Variables

```env
VITE_API_URL=https://your-backend.up.railway.app/api
```

### Step 9.5: Deploy
1. Click **Deploy**
2. Your URL: `https://your-project.vercel.app`

---

## Phase 10: Configure WhatsApp Webhook

### Step 10.1: Set Up ngrok (for testing)
1. Download ngrok: https://ngrok.com/download
2. Extract the zip
3. Sign up at https://ngrok.com
4. Get your authtoken from dashboard
5. Configure ngrok:

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

6. Start tunnel to your bridge:

```bash
ngrok http 3001
```

7. Copy the **https** URL (e.g., `https://abc123.ngrok.io`)

### Step 10.2: Configure Webhook in Meta
1. Go to https://developers.facebook.com
2. Open your app
3. Go to **WhatsApp** → **Configuration**
4. Click **Edit** on Webhook
5. Enter:
   - **Callback URL**: `https://abc123.ngrok.io/webhook`
   - **Verify Token**: `your-verify-token` (same as in .env)
6. Click **Verify and Save**

### Step 10.3: Subscribe to Webhooks
1. In the same section, click **Manage**
2. Check these fields:
   - `messages`
   - `message_deliveries`
   - `message_reads`

### Step 10.4: Update Bridge URL for Production
Once you have a permanent URL (Railway provides one), update the webhook URL in Meta dashboard.

---

## Phase 11: Final Configuration

### Step 11.1: Update All URLs
In Railway backend variables, update:

```env
BRIDGE_URL=https://your-bridge.up.railway.app
```

In your frontend `.env` or Vercel:

```env
VITE_API_URL=https://your-backend.up.railway.app/api
```

### Step 11.2: Test the System
1. Open your frontend URL
2. Register a new account
3. Go to WhatsApp Setup
4. Scan QR code with your WhatsApp
5. Send a message from another WhatsApp number
6. You should get the consent message
7. Reply "YES"
8. Send another message
9. AI should reply!

---

## Phase 12: Set Up Custom Domain (Optional, Free)

### Step 12.1: Get Free Domain
1. Go to https://www.freenom.com (or .tk, .ml, .ga domains)
2. Search for a free domain
3. Register for 12 months (free)

### Step 12.2: Connect to Vercel
1. In Vercel project settings
2. Go to **Domains**
3. Enter your domain
4. Add the DNS records to Freenom
5. Wait for verification

---

## Troubleshooting

### "Connection refused" errors
- Check if all services are running
- Verify environment variables are correct
- Check Railway logs for errors

### "WhatsApp not connected"
- Verify phone number is added in Meta dashboard
- Check if access token is valid
- Ensure webhook URL is correct

### "AI not responding"
- Check Gemini API key is valid
- Verify backend can reach Gemini
- Check Railway logs for AI errors

### "Database connection failed"
- Verify Supabase credentials
- Check if IP is whitelisted (Supabase allows all by default)
- Verify DATABASE_URL format

---

## Cost Summary

| Service | Free Tier | Cost |
|---------|-----------|------|
| Railway | 500 hrs/month | ₹0 |
| Supabase | 500MB | ₹0 |
| Upstash | 10K commands/day | ₹0 |
| Vercel | Unlimited | ₹0 |
| Meta WhatsApp | Unlimited | ₹0 |
| Gemini | 60 req/min | ₹0 |
| GitHub | Unlimited | ₹0 |
| **TOTAL** | | **₹0** |

---

## Important Notes

1. **Free Tier Limits**: Railway's free tier sleeps after 30 minutes of inactivity. It wakes up when you visit your site. For always-on, consider upgrading to $5/month.

2. **Supabase Limits**: 500MB is enough for ~10,000 messages and ~1,000 contacts.

3. **Upstash Limits**: 10K commands/day is enough for normal usage.

4. **Gemini Limits**: 60 requests/minute is plenty for personal use.

5. **Railway Sleep**: To prevent sleep, use UptimeRobot (free) to ping your site every 5 minutes.

---

## Quick Reference: All URLs

```
Frontend:     https://your-project.vercel.app
Backend API:  https://your-backend.up.railway.app
Bridge:       https://your-bridge.up.railway.app
Database:     postgresql://...@db.xxx.supabase.co:5432/postgres
Redis:        redis://...@xxx.upstash.io:6379
```

---

## Emergency Commands

```bash
# Check Railway logs
railway logs

# Open Railway shell
railway shell

# Restart Railway deployment
railway up

# Check Supabase database
psql $DATABASE_URL

# Test Redis connection
redis-cli -u $REDIS_URL PING
```

---

## Support

If stuck, check:
1. Railway logs for backend errors
2. Supabase SQL Editor for database errors
3. Meta Developer Console for WhatsApp errors
4. Vercel logs for frontend errors

---

**Happy Deploying! 🚀**