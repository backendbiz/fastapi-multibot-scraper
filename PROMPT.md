# FastAPI Scraper Server with Multi-Bot Telegram Support

Production-grade FastAPI server with Selenium web scraping and multi-bot Telegram notifications.
Supports 30+ bots with individual configurations.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          TELEGRAM BOTS (30+)                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  Bot 1  │  │  Bot 2  │  │  Bot 3  │  │   ...   │  │ Bot 30+ │       │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │
│       │            │            │            │            │             │
│       └────────────┴────────────┴────────────┴────────────┘             │
│                              │                                          │
│                      ┌───────▼───────┐                                  │
│                      │   Webhooks    │                                  │
│                      │ /webhook/{id} │                                  │
│                      └───────┬───────┘                                  │
│                              │                                          │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   FastAPI Server    │
                    │                     │
                    │  ┌───────────────┐  │
                    │  │ Bot Manager   │  │◄────── Manages all bots
                    │  └───────┬───────┘  │
                    │          │          │
                    │  ┌───────▼───────┐  │
                    │  │Cmd Handler    │  │◄────── Processes /scrape, /batch, etc.
                    │  └───────┬───────┘  │
                    │          │          │
                    │  ┌───────▼───────┐  │
                    │  │   Selenium    │  │◄────── Headless Chrome
                    │  │   Scraper     │  │
                    │  └───────┬───────┘  │
                    │          │          │
                    └──────────┼──────────┘
                               │
               ┌───────────────┴───────────────┐
               │                               │
        ┌──────▼──────┐                 ┌──────▼──────┐
        │  Telegram   │                 │    API      │
        │  Channels   │                 │  Response   │
        └─────────────┘                 └─────────────┘
```

## Two Input Modes

### 1. Telegram Bot Commands
User sends command directly to a Telegram bot → Bot processes via webhook → Scrapes → Sends results to Telegram channel

```
User → @YourBot: /scrape https://example.com
       ↓
       Webhook received
       ↓
       Selenium scrapes URL
       ↓
       Results sent to configured channel
```

### 2. API Requests
External API call → Scrapes → Returns response AND notifies Telegram channel(s)

```
API Call: POST /api/v1/bots/scrape
          {"url": "https://example.com", "bot_ids": ["bot1", "bot2"]}
          ↓
          Selenium scrapes URL
          ↓
          JSON response returned
          ↓
          Results ALSO sent to bot1 & bot2 channels
```

## Quick Start

### 1. Deploy to Coolify/Docker

```bash
# Build and run
docker-compose up -d
```

### 2. Create Telegram Bots

For each bot (repeat 30+ times):
1. Message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`
3. Get the API token
4. Create a Telegram channel
5. Add bot as admin to the channel
6. Get channel ID (forward message to [@getidsbot](https://t.me/getidsbot))

### 3. Register Bots via API

```bash
# Register a single bot
curl -X POST "https://your-server.com/api/v1/bots/register" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "bot_id": "scraper_bot_1",
    "bot_token": "123456789:ABCdefGHI...",
    "bot_name": "Scraper Bot 1",
    "channel_id": "-1001234567890",
    "allowed_users": [123456789],
    "take_screenshot": true
  }'

# Register multiple bots at once
curl -X POST "https://your-server.com/api/v1/bots/register/bulk" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "bots": [
      {"bot_id": "bot1", "bot_token": "...", "bot_name": "Bot 1", "channel_id": "..."},
      {"bot_id": "bot2", "bot_token": "...", "bot_name": "Bot 2", "channel_id": "..."},
      ...
    ]
  }'
```

### 4. Setup Webhooks

```bash
# Setup webhooks for all bots
curl -X POST "https://your-server.com/api/v1/webhooks/setup" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"base_url": "https://your-server.com"}'
```

### 5. Use the Bots

**Via Telegram:**
```
/scrape https://example.com
/batch https://a.com https://b.com
/status
/help
```

**Via API:**
```bash
# Scrape and notify all bots
curl -X POST "https://your-server.com/api/v1/bots/scrape" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Scrape and notify specific bots
curl -X POST "https://your-server.com/api/v1/bots/scrape" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "bot_ids": ["bot1", "bot3", "bot5"]
  }'
```

## Environment Variables

### Required
```env
# API Security
API_KEY_SECRET=your-32-byte-hex-secret
VALID_API_KEYS=key1,key2,key3

# Environment
ENVIRONMENT=production
```

### Optional - Pre-configured Bots
```env
# Single bot (legacy)
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHANNEL_ID=-1001234567890

# Multiple bots (JSON array)
BOTS_CONFIG='[
  {"bot_id": "bot1", "bot_token": "...", "bot_name": "Bot 1", "channel_id": "..."},
  {"bot_id": "bot2", "bot_token": "...", "bot_name": "Bot 2", "channel_id": "..."}
]'
```

### Selenium Configuration
```env
SELENIUM_HEADLESS=true
SELENIUM_TIMEOUT=30
SELENIUM_PAGE_LOAD_TIMEOUT=60
```

## API Endpoints

### Bot Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/bots/register` | Register single bot |
| POST | `/api/v1/bots/register/bulk` | Register multiple bots |
| GET | `/api/v1/bots` | List all bots |
| GET | `/api/v1/bots/{bot_id}` | Get bot details |
| PATCH | `/api/v1/bots/{bot_id}` | Update bot config |
| DELETE | `/api/v1/bots/{bot_id}` | Delete bot |
| POST | `/api/v1/bots/{bot_id}/test` | Test bot |

### Webhooks
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/webhooks/setup` | Setup all webhooks |
| POST | `/api/v1/webhooks/setup/{bot_id}` | Setup single webhook |
| DELETE | `/api/v1/webhooks` | Remove all webhooks |
| DELETE | `/api/v1/webhooks/{bot_id}` | Remove single webhook |
| GET | `/api/v1/webhooks/{bot_id}/info` | Get webhook info |

### Scraping
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/bots/scrape` | Scrape URL + notify Telegram |
| POST | `/api/v1/scraper/scrape` | Full scrape with options |
| POST | `/api/v1/scraper/scrape/batch` | Batch scrape URLs |
| POST | `/api/v1/scraper/scrape/simple` | Quick scrape |

### Broadcast
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/bots/broadcast` | Send to all channels |
| POST | `/api/v1/broadcast` | Broadcast message |

## Bot Commands (Telegram)

| Command | Description | Example |
|---------|-------------|---------|
| `/scrape <url>` | Scrape single URL | `/scrape https://example.com` |
| `/scrape <url> wait=10` | Scrape with wait | `/scrape https://spa.com wait=10` |
| `/scrape <url> noscreen` | Without screenshot | `/scrape https://example.com noscreen` |
| `/batch <urls>` | Scrape multiple URLs | `/batch https://a.com https://b.com` |
| `/status` | Bot status | `/status` |
| `/cancel` | Cancel current task | `/cancel` |
| `/help` | Show help | `/help` |

Auto-scrape: Just send a URL without command!

## Bot Configuration Options

```json
{
  "bot_id": "unique_identifier",
  "bot_token": "telegram_bot_token",
  "bot_name": "Display Name",
  "channel_id": "-1001234567890",
  "allowed_users": [123456789, 987654321],  // Empty = all users
  "allowed_commands": ["scrape", "batch", "status", "help"],
  "is_active": true,
  "default_wait_time": 5,
  "default_timeout": 30,
  "take_screenshot": true,
  "send_to_channel": true
}
```

## Deployment

### Docker Compose
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - API_KEY_SECRET=your-secret
      - VALID_API_KEYS=key1,key2
    volumes:
      - app-data:/app/data
      - app-screenshots:/app/screenshots
    shm_size: '2gb'  # Required for Chrome

volumes:
  app-data:
  app-screenshots:
```

### Resource Requirements
- **Memory:** 2GB minimum (Chrome needs ~1GB per instance)
- **CPU:** 2 cores recommended
- **Storage:** 10GB for screenshots and data

## Scaling for 30+ Bots

The system is designed to handle 30+ bots efficiently:

1. **Shared Selenium Instance:** All bots share one Chrome instance
2. **Async Processing:** Commands processed asynchronously
3. **Rate Limiting:** Per-bot rate limits prevent abuse
4. **Persistent Storage:** Bot configs saved to `/app/data/bots.json`
5. **Webhook-based:** No polling overhead

### Best Practices for Many Bots
- Use webhook mode (not polling)
- Stagger webhook registration
- Monitor memory usage
- Set appropriate rate limits
- Use SSD storage for screenshots

## File Structure

```
app/
├── main.py                 # Application entry
├── api/v1/
│   ├── bots.py            # Bot CRUD & scraping
│   ├── webhooks.py        # Webhook handling
│   └── scraper.py         # Scraper endpoints
├── services/
│   ├── bot_manager.py     # Multi-bot management
│   ├── command_handler.py # Telegram commands
│   ├── scraper.py         # Selenium scraper
│   └── telegram.py        # Telegram API client
└── core/
    └── config.py          # Settings
```

## Troubleshooting

### Bot not responding
1. Check webhook: `GET /api/v1/webhooks/{bot_id}/info`
2. Test bot: `POST /api/v1/bots/{bot_id}/test`
3. Check logs for errors

### Scraping fails
1. Check Chrome is running: `ps aux | grep chrome`
2. Increase timeout: `wait_time` parameter
3. Check URL accessibility

### Memory issues
1. Reduce concurrent scrapes
2. Disable screenshots
3. Increase container memory

## Support

- **API Docs:** `/docs` (Swagger UI)
- **Health Check:** `/health`
- **Status:** `/api/v1/bots/status/summary`
