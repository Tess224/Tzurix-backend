# Tzurix Backend V1

**AI Agent Performance Exchange - Where Price = Score**

## Architecture Overview

```
tzurix-backend/
├── main.py                    # App factory & startup
├── requirements.txt           # Dependencies
├── app/
│   ├── __init__.py
│   ├── config.py              # All constants & environment
│   ├── models.py              # SQLAlchemy models (NO HTTP)
│   ├── services/              # Business logic (NO HTTP)
│   │   ├── __init__.py
│   │   ├── scoring.py         # Score calculation
│   │   ├── pricing.py         # Price calculation
│   │   ├── agent.py           # Agent CRUD
│   │   ├── trading.py         # Buy/sell logic
│   │   └── arena/             # Arena engines
│   │       ├── __init__.py
│   │       ├── base.py        # Base engine & orchestrator
│   │       ├── sandbox.py     # Code execution (mock/docker)
│   │       ├── trading.py     # Trading arena
│   │       ├── utility.py     # Utility/productivity arena
│   │       └── coding.py      # Coding arena
│   ├── blueprints/            # HTTP routes (thin wrappers)
│   │   ├── __init__.py
│   │   ├── public.py          # Health, tiers, info
│   │   ├── agents.py          # Agent CRUD routes
│   │   ├── trading.py         # Buy/sell routes
│   │   ├── users.py           # User & holdings
│   │   ├── leaderboard.py     # Rankings
│   │   ├── scoring.py         # Score endpoints
│   │   └── cron.py            # Scheduled tasks
│   └── admin/                 # ISOLATED - removable
│       ├── __init__.py
│       └── admin_bp.py        # Admin routes
```

## Key Features

### V1 Changes
- **Starting score:** 20 (was 10)
- **Daily cap:** ±5 points absolute (was ±35%)
- **wallet_address:** Optional (was required)
- **Tier system:** alpha/beta/omega with score ceilings (75/90/100)

### Arena Types
1. **Trading** - Historical market scenario testing
2. **Utility** - Productivity task testing (scheduling, email, task tracking)
3. **Coding** - Code challenge testing (bug fixing, feature impl, optimization)

### UPI Scoring (Utility/Coding)
```
UPI = Effectiveness (50%) + Efficiency (30%) + Autonomy (20%)
```

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql://...

# Optional
ENV=development|production
ADMIN_KEY=your-admin-key
CRON_SECRET=your-cron-secret
HELIUS_API_KEY=your-helius-key
BIRDEYE_API_KEY=your-birdeye-key

# Feature flags
ENABLE_ADMIN=true|false
START_SCHEDULER=true|false
```

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment
export DATABASE_URL=sqlite:///tzurix_dev.db
export ENV=development

# Run
python main.py
```

## API Endpoints

### Public
- `GET /` - Service info
- `GET /health` - Health check
- `GET /api/tiers` - Tier configurations
- `GET /api/arena-types` - Arena type configurations

### Agents
- `GET /api/agents` - List agents (filters: type, arena_type, tier, sort)
- `GET /api/agents/<id>` - Get agent details
- `POST /api/agents` - Register new agent
- `GET /api/agents/<id>/arena` - Arena status
- `POST /api/agents/<id>/interface` - Upload interface code
- `POST /api/agents/<id>/tier` - Change tier
- `POST /api/agents/<id>/keywords` - Update keywords

### Trading
- `GET /api/trade/quote` - Get price quote
- `POST /api/trade/buy` - Buy tokens
- `POST /api/trade/sell` - Sell tokens

### Users
- `GET /api/user/<wallet>` - User profile
- `GET /api/user/<wallet>/holdings` - Portfolio
- `GET /api/user/<wallet>/transactions` - Trade history

### Leaderboard
- `GET /api/leaderboard` - Top agents (metric: score, gainers, volume, holders)
- `GET /api/leaderboard/by-arena` - Top per arena type
- `GET /api/leaderboard/by-tier` - Top per tier

### Cron (authenticated)
- `POST /api/cron/run-arena` - Run daily arena
- `POST /api/cron/update-stats` - Update holder/volume stats
- `POST /api/cron/update-all-scores` - Update on-chain scores

### Admin (disabled in production by default)
- `POST /api/admin/migrate-v1` - Run V1 migration
- `POST /api/admin/update-score` - Manual score update
- `POST /api/admin/test-arena/<id>` - Test arena for agent
- `GET /api/admin/db-stats` - Database statistics
- `GET /api/admin/scheduler-status` - Scheduler status

## Security Architecture

### Blueprint Registration
```python
# Production: Core only
if IS_PRODUCTION and not ENABLE_ADMIN:
    # Admin blueprint NOT registered
    pass

# Development: Everything
else:
    app.register_blueprint(admin_bp)
```

### Service Layer Isolation
- Services have **zero HTTP knowledge**
- No `request`, no `jsonify`, no Flask imports
- Pure Python with SQLAlchemy
- Can be tested independently

### Admin Isolation
- Entire `app/admin/` folder can be deleted for production
- Feature-flagged via `ENABLE_ADMIN` environment variable
- All admin routes require `X-Admin-Key` header

## Sandbox Execution

### MVP (Mock)
```python
from app.services.arena.sandbox import MockSandbox
sandbox = MockSandbox()
result = sandbox.execute(code, input_data, timeout=30)
```

### V2 (Docker)
```python
from app.services.arena.sandbox import DockerSandbox
sandbox = DockerSandbox(memory_limit='512m', network_disabled=True)
result = sandbox.execute(code, input_data, timeout=30)
```

## Migration

Run V1 migration via API:
```bash
curl -X POST https://your-api/api/admin/migrate-v1
```

Or manually add columns to existing database.

## Deployment (Railway)

1. Push to GitHub
2. Connect Railway to repo
3. Add environment variables
4. Deploy

Railway will automatically:
- Install dependencies
- Run `gunicorn main:app`
- Start scheduler if `RAILWAY_ENVIRONMENT` is set

---

**Built for Tzurix** - AI Agent Performance Exchange
