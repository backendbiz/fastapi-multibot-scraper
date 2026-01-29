# FastAPI Scraper Server 🚀

A production-grade FastAPI server with Selenium web scraping and **multi-bot Telegram support (30+ bots)**.

## ✨ Features

- **🤖 Multi-Bot Support** - Manage 30+ Telegram bots simultaneously
- **📱 Telegram Commands** - Users send commands to bots → scrape → results to channel
- **🌐 API Scraping** - Direct API calls → scrape → return response + notify Telegram
- **🔐 Encrypted API Keys** - AES-256-GCM encryption
- **📸 Screenshot Capture** - Visual proof of scraped pages
- **🐳 Docker Ready** - Includes Chrome/Chromium for Selenium
- **☁️ Coolify Compatible** - Easy deployment

## 🎯 How It Works

### Via Telegram Bot Commands
```
User sends /scrape https://example.com to Bot
    ↓
Bot triggers Selenium scraping
    ↓
Results sent to Bot's configured channel
```

### Via API
```
POST /api/v1/bots/scrape with URL
    ↓
Selenium scrapes the page
    ↓
Returns JSON response + notifies all active bot channels
```

## 🚀 Quick Start

### 1. Start the Server
```bash
# Clone and enter directory
git clone <your-repo>
cd fastapi-coolify-project

# Copy environment file
cp .env.example .env

# Start with Docker
docker-compose up --build
```

### 2. Register a Bot
```bash
curl -X POST "http://localhost:8000/api/v1/bots/register" \
  -H "X-API-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "bot_id": "my_scraper_bot",
    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "bot_name": "My Scraper Bot",
    "channel_id": "@my_results_channel"
  }'
```

### 3. Setup Webhook
```bash
curl -X POST "http://localhost:8000/api/v1/bots/webhooks/setup" \
  -H "X-API-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://your-domain.com"}'
```

### 4. Use the Bot
Send to your Telegram bot:
```
/scrape https://example.com
```

Results will appear in your channel! 📢

## 📡 API Endpoints

### Bot Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/bots/register` | Register a new bot |
| POST | `/api/v1/bots/register/bulk` | Register multiple bots |
| GET | `/api/v1/bots` | List all bots |
| GET | `/api/v1/bots/{bot_id}` | Get bot details |
| PATCH | `/api/v1/bots/{bot_id}` | Update bot config |
| DELETE | `/api/v1/bots/{bot_id}` | Remove a bot |

### Webhooks
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/bots/webhooks/setup` | Setup webhooks for all bots |
| POST | `/api/v1/bots/webhooks/remove` | Remove all webhooks |
| POST | `/api/v1/bots/webhook/{bot_id}` | Webhook receiver (for Telegram) |

### API Scraping
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/bots/scrape` | Scrape URL via API + notify channels |
| POST | `/api/v1/bots/broadcast` | Send message to all channels |

### Direct Scraping (no Telegram)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/scraper/scrape` | Scrape with full options |
| POST | `/api/v1/scraper/scrape/batch` | Scrape multiple URLs |

## 🤖 Telegram Bot Commands

When users message your bots:

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show available commands |
| `/scrape <url>` | Scrape a single URL |
| `/batch <url1> <url2>` | Scrape multiple URLs (max 10) |
| `/status` | Check bot status |
| `/cancel` | Cancel ongoing task |

**Quick Usage:** Just send any URL and it will be scraped automatically!

**Options:**
```
/scrape https://example.com --wait=5 --no-screenshot
/scrape https://news.site --selector=".article"
```

## 📋 Register Multiple Bots

### Via API (Bulk)
```bash
curl -X POST "http://localhost:8000/api/v1/bots/register/bulk" \
  -H "X-API-Key: dev-key-123" \
  -H "Content-Type: application/json" \
  -d '{
    "bots": [
      {"bot_id": "bot1", "bot_token": "TOKEN1", "bot_name": "Bot 1", "channel_id": "@channel1"},
      {"bot_id": "bot2", "bot_token": "TOKEN2", "bot_name": "Bot 2", "channel_id": "@channel2"},
      {"bot_id": "bot3", "bot_token": "TOKEN3", "bot_name": "Bot 3", "channel_id": "@channel3"}
    ]
  }'
```

### Via Environment Variable
```env
BOTS_CONFIG=[{"bot_id":"bot1","bot_token":"TOKEN1","bot_name":"Bot 1","channel_id":"@ch1"},{"bot_id":"bot2","bot_token":"TOKEN2","bot_name":"Bot 2","channel_id":"@ch2"}]
```

### Via Config File
Create `config/bots.json`:
```json
[
  {"bot_id": "bot1", "bot_token": "TOKEN1", "bot_name": "Bot 1", "channel_id": "@channel1"},
  {"bot_id": "bot2", "bot_token": "TOKEN2", "bot_name": "Bot 2", "channel_id": "@channel2"}
]
```

Set: `BOTS_CONFIG_FILE=/app/config/bots.json`

## ☁️ Deploy to Coolify

### Environment Variables
```env
ENVIRONMENT=production
DEBUG=false
API_KEY_SECRET=<64-char-hex-secret>
VALID_API_KEYS=<your-keys>
ALLOWED_ORIGINS=https://your-domain.com
```

### After Deployment
1. Register your bots via API
2. Setup webhooks: `POST /api/v1/bots/webhooks/setup`
3. Add bots as admins to their channels
4. Test with `/status` command

### Resource Requirements
- **Memory**: 2GB minimum (Chrome + 30 bots)
- **CPU**: 2 cores recommended

## 📁 Project Structure

```
├── app/
│   ├── api/v1/
│   │   ├── bots.py          # 🆕 Multi-bot management
│   │   ├── scraper.py       # Direct scraping
│   │   └── auth.py          # API key auth
│   ├── services/
│   │   ├── bot_manager.py   # 🆕 Manages 30+ bots
│   │   ├── command_handler.py # 🆕 Telegram commands
│   │   ├── scraper.py       # Selenium scraper
│   │   └── telegram.py      # Telegram API client
│   └── main.py
├── config/
│   └── bots.example.json    # Sample bot config
├── Dockerfile
└── docker-compose.yml
```

## 🔧 Bot Configuration Options

| Field | Type | Description |
|-------|------|-------------|
| `bot_id` | string | Unique identifier |
| `bot_token` | string | Telegram bot token |
| `bot_name` | string | Display name |
| `channel_id` | string | Results channel |
| `allowed_users` | int[] | User IDs (empty = all) |
| `allowed_commands` | string[] | Enabled commands |
| `is_active` | bool | Enable/disable bot |
| `take_screenshot` | bool | Screenshot by default |
| `default_timeout` | int | Scraping timeout |

## 📖 More Documentation

See [PROMPT.md](PROMPT.md) for:
- Detailed Telegram setup
- Advanced scraping options
- Troubleshooting guide
- Security best practices

## 📄 License

MIT License

---

Built with ❤️ for managing 30+ Telegram scraper bots
