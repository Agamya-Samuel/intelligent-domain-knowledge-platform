# IDKP Backend

FastAPI backend for the **Intelligent Domain Knowledge Platform** — a fine-tuned LLM + Advanced RAG system.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI with async support |
| Database | PostgreSQL 16 via asyncpg |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic (async runner) |
| Cache | Redis 7 |
| Auth | Auth.js v5 JWT bridge (JWE/JWS) |
| Config | Pydantic Settings (.env) |
| Tooling | uv, Ruff, mypy, pytest |

## Project Structure

```
backend/
├── app/
│   ├── api/v1/endpoints/   # Route handlers (health, auth, ...)
│   ├── core/security.py    # Auth.js v5 JWT decode bridge
│   ├── db/                 # SQLAlchemy session & declarative base
│   ├── models/             # ORM models (future)
│   ├── dependencies.py     # FastAPI Depends (get_current_user, get_db)
│   ├── config.py           # Pydantic Settings from .env
│   └── main.py             # FastAPI app entry point
├── alembic/                # Database migrations
├── tests/                  # pytest (asyncio_mode = auto)
├── pyproject.toml          # Dependencies & tool config
└── uv.lock                 # Pinned dependency versions
```

## Prerequisites

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) — fast Python package manager
- PostgreSQL 16 running locally (or via Docker)
- Redis 7 running locally (or via Docker)

## Quick Start

```bash
# Clone and enter the backend directory
cd backend

# Create virtual environment and install all dependencies
uv sync --all-extras

# Copy environment template and fill in values
cp ../.env.example .env

# Start the development server
uv run uvicorn app.main:app --reload --port 8000
```

The API docs will be available at `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc` (ReDoc).

## Docker Services

The project includes a Docker Compose stack at the repo root that runs PostgreSQL, Redis, Langfuse, and Nginx:

```bash
# From the repo root
docker compose up -d
```

## Environment Variables

All settings are loaded from a `.env` file in the backend directory. See `../.env.example` for the full list. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://idkp:idkp_secret@localhost:5432/idkp` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `AUTH_SECRET` | Shared secret with Auth.js v5 frontend | `change-me-in-production` |
| `FRONTEND_URL` | Allowed CORS origin | `http://localhost:3000` |
| `DEBUG` | Enable debug mode | `true` |

## Authentication

The backend validates JWT tokens issued by the Next.js frontend (Auth.js v5).

**Token flow:**
1. Frontend signs in via Auth.js (Google, GitHub, or Credentials provider)
2. Auth.js issues a JWE-encrypted JWT (alg=dir, enc=A256GCM) using `AUTH_SECRET`
3. Frontend sends the token via `Authorization: Bearer <token>` header or `next-auth.session-token` cookie
4. Backend decrypts/verifies the token and extracts `sub`, `email`, `name`

**Protecting an endpoint:**
```python
from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.core.security import CurrentUser

router = APIRouter()

@router.get("/me")
async def get_me(user: CurrentUser = Depends(get_current_user)):
    return {"user_id": user.user_id, "email": user.email, "name": user.name}
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (public) |
| `GET` | `/api/v1/auth/me` | Get current user (requires auth) |

## Database Migrations

```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply all pending migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1
```

## Available Commands

```bash
# Run the dev server with hot reload
uv run uvicorn app.main:app --reload --port 8000

# Run tests
uv run pytest tests/ -v

# Lint with Ruff
uv run ruff check app/

# Format code with Ruff
uv run ruff format app/

# Type check with mypy
uv run mypy app/

# Run Alembic migrations
uv run alembic upgrade head
```

## Adding a New Dependency

```bash
# Add a runtime dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>

# Update uv.lock
uv lock
```
