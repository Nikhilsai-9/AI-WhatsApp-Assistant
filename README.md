# AI WhatsApp Personal Assistant

A production-ready AI assistant that automatically replies to WhatsApp messages in your personal communication style. Built on the **official Meta WhatsApp Business Platform Cloud API** — fully compliant, secure, and authorized.

---

## ⚠️ Important: Official WhatsApp Integration Only

This application uses the **Meta WhatsApp Business Platform Cloud API** — the only officially supported way to automate WhatsApp messaging. It is:
- ✅ **Meta-approved** — uses official Graph API endpoints
- ✅ **Consent-based** — requires explicit permission from both account owner and contacts
- ✅ **Privacy-first** — encrypted storage, GDPR-compliant, audit logged
- ✅ **Platform-compliant** — only processes personal 1:1 chats, never groups/channels

---

## Features

### 🤖 AI-Powered Replies
- Generates context-aware responses matching your communication style
- Learns vocabulary, emoji usage, sentence length, greeting/ending patterns
- Supports: English, Telugu, Hindi, Tamil, Malayalam, Kannada, Hinglish, Tanglish, Teluglish
- **Teluglish mode**: English words with Telugu pronunciation (e.g., "Nenu 10 mins lo vasta")

### 🔒 Privacy & Consent (Two-Layer)
1. **Account Owner Consent**: Must explicitly link WhatsApp account and enable AI
2. **Contact Consent**: Every new contact receives a YES/NO permission request before auto-replies begin

### 🛡️ Supported Chats Only
- ✅ One-to-One Personal Chats
- ✘ Group Chats (automatically ignored)
- ✘ Communities (automatically ignored)
- ✘ Channels (automatically ignored)
- ✘ Broadcast Lists (automatically ignored)

### 🧠 Memory Engine
- Long-term memory with vector embeddings (pgvector)
- Short-term context within conversations
- Per-contact personality profiles
- Semantic search across all history
- Importance scoring for key facts

### 💬 Message Types
- Text, images (OCR), voice notes (transcription), documents (OCR), videos, links, locations, contacts

### 📊 Dashboard
- Real-time stats: messages today, AI replies, contacts, learning progress
- Activity charts (7-day history)
- Contact management with consent controls
- AI transparency panel (last reply, reply history)
- Privacy controls (export, delete, disable)

### 🔧 AI Providers
- Google Gemini, OpenAI GPT-4, Anthropic Claude, OpenRouter, MiniMax, Local Ollama

---

## Architecture

```
ai-whatsapp-assistant/
├── backend/              # FastAPI Python backend
│   ├── app/
│   │   ├── api/          # REST endpoints
│   │   ├── core/         # Config, security, logging
│   │   ├── db/           # SQLAlchemy session
│   │   ├── models/       # Database models
│   │   ├── schemas/      # Pydantic schemas
│   │   └── services/     # AI, memory, media, personality
│   ├── alembic/          # Database migrations
│   └── Dockerfile
├── whatsapp-bridge/      # Node.js Meta Cloud API bridge
│   ├── src/
│   │   └── index.js      # Meta Graph API integration
│   └── Dockerfile
├── frontend/             # React + TypeScript dashboard
│   └── src/
│       └── App.tsx       # Single-page dashboard
├── nginx/                # Reverse proxy config
├── docker-compose.yml    # Full stack orchestration
└── README.md
```

---

## Prerequisites

1. **Meta Business App** — [developers.facebook.com](https://developers.facebook.com/apps/)
2. **WhatsApp Business Account (WABA)** — linked to your Meta Business
3. **Registered Phone Number** — added to your WABA (cannot be used on regular WhatsApp)
4. **Permanent Access Token** — generated from Meta developer console
5. **Docker & Docker Compose**
6. **AI API Key** — Gemini, OpenAI, Claude, etc.

---

## Quick Start

### 1. Create Meta App

```
1. Go to https://developers.facebook.com/apps/
2. Create a new "Business" app
3. Add "WhatsApp" product to the app
4. Link your WhatsApp Business Account
5. Add a phone number to your WABA
6. Generate a permanent access token
```

### 2. Configure Environment

```bash
cd ai-whatsapp-assistant
cp .env.example .env
```

Edit `.env`:
```env
SECRET_KEY=your-32-char-minimum-secret-key
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your-random-verify-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
META_ACCESS_TOKEN=your-permanent-access-token
META_APP_SECRET=your-app-secret
GEMINI_API_KEY=your-gemini-key
```

### 3. Start Services

```bash
docker compose up -d
```

This starts:
- **PostgreSQL + pgvector** on port 5432
- **Redis** on port 6379
- **Backend API** on port 8000
- **WhatsApp Bridge** on port 3001
- **Nginx** on ports 80/443

### 4. Configure Webhook

In your Meta developer console, configure the webhook URL:
```
https://your-domain.com/bridge/webhook
```
Set the verify token to match `WHATSAPP_WEBHOOK_VERIFY_TOKEN` in your `.env`.

Subscribe to these webhook fields:
- `messages`
- `message_deliveries`
- `message_reads`

### 5. Create Admin User

```bash
docker compose exec backend python -c "
from app.db.session import SessionLocal
from app.models.user import User
from passlib.context import CryptContext
db = SessionLocal()
pwd = CryptContext(schemes=['bcrypt']).hash('your-password')
db.add(User(email='admin@example.com', hashed_password=pwd, is_admin=True))
db.commit()
db.close()
"
```

### 6. Open Dashboard

```
http://localhost:5173  (development)
http://localhost       (production)
```

Login → Link WhatsApp account → Enable AI → Done!

---

## How Consent Works

### Account Owner (You)
1. Login to dashboard
2. Link WhatsApp account (enter credentials/API token)
3. Accept Terms of Service and Privacy Policy
4. Enable AI Assistant toggle
5. Configure settings (reply delay, filters, provider)

### Your Contacts
When a new contact messages you:
1. They receive: *"Hi 👋 I'm using an AI assistant... Reply YES or NO"*
2. If **YES** → AI auto-replies enabled for that contact
3. If **NO** → AI never replies to that contact (until manually changed)
4. Consent is stored permanently

---

## Privacy Controls

Every user can:
- ✅ View all stored conversation history
- ✅ Export conversation history (JSON)
- ✅ Delete individual conversations
- ✅ Delete all AI memory
- ✅ Disable AI for specific contacts
- ✅ Disable AI completely
- ✅ Remove linked WhatsApp account
- ✅ Configure data retention (30/90/180/365 days)
- ✅ View AI transparency log (all auto-replies)

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login (form data) |
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/refresh` | Refresh JWT token |
| GET | `/api/contacts/` | List contacts (filterable) |
| POST | `/api/contacts/consent` | Update consent status |
| GET | `/api/messages/` | Get message history |
| DELETE | `/api/messages/{id}` | Delete a message |
| DELETE | `/api/messages/contact/{id}` | Delete all messages with contact |
| GET | `/api/dashboard/stats` | Dashboard statistics |
| GET | `/api/dashboard/activity` | Activity chart data |
| GET | `/api/dashboard/transparency` | AI reply history |
| GET | `/api/settings/` | Get user settings |
| PATCH | `/api/settings/` | Update settings |
| POST | `/api/settings/export` | Export all data |
| DELETE | `/api/settings/memory` | Delete all memory |
| POST | `/api/webhooks/whatsapp` | Bridge → Backend webhook |

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | JWT signing key (32+ chars) | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Auto |
| `REDIS_URL` | Redis connection string | Auto |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta phone number ID | Yes |
| `META_ACCESS_TOKEN` | Meta permanent access token | Yes |
| `META_APP_SECRET` | Meta app secret | Yes |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Webhook verification token | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Recommended |
| `OPENAI_API_KEY` | OpenAI API key | Optional |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `ENVIRONMENT` | `development` or `production` | Auto |

---

## Development

### Backend (local)

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### WhatsApp Bridge (local)

```bash
cd whatsapp-bridge
npm install
node src/index.js
```

### Frontend (local)

```bash
cd frontend
npm install
npm run dev
```

---

## License

MIT License