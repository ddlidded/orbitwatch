# Deployment Guide

## Local development with Docker Compose

The root `docker-compose.yml` runs PostgreSQL, Redis, MinIO, the backend API, a Dramatiq worker, and the Vite dev frontend.

```bash
cp .env.example .env
# (optional) edit .env
docker compose up --build -d
```

Services:

| Service | Port | Description |
|--------|------|-------------|
| Frontend | http://localhost:5173 | Vite dev server with API/WebSocket proxy |
| Backend API | http://localhost:8000 | FastAPI + auto-reload |
| Worker | internal | Dramatiq Redis worker |
| PostgreSQL | 5432 | Application database |
| Redis | 6379 | Broker/caches |
| MinIO | 9000 (API), 9001 (console) | S3-compatible object storage |

Default admin account: `admin@isotopiq.dev` / `OrbitWatch-Admin-2024!`.

## Production deployment

Use `docker-compose.prod.yml`:

```bash
cp .env.example .env
# Set strong secrets:
#   SECRET_KEY, POSTGRES_PASSWORD, S3_SECRET_KEY, CORS_ORIGINS, ORBITWATCH_SECRET_KEY
docker compose -f docker-compose.prod.yml up --build -d
```

Production adds:

- Caddy reverse proxy on ports `80`/`443`
- Nginx-built static frontend container
- Backend/worker run without `--reload`
- `alembic upgrade head` runs before backend start

Edit `infrastructure/Caddyfile` to enable HTTPS/TLS and set the real domain.

## Agent deployment

The Windows instrument agent is not containerized. Build and run the .NET worker service on the instrument PC:

```powershell
cd agent\OrbitWatchAgent
dotnet publish -c Release -r win-x64 --self-contained true
```

See `docs/instrument-connection.md` for registering an agent and obtaining a token.

## Environment variables

Key variables (full list in `.env.example`):

- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `SECRET_KEY` — FastAPI secret key
- `CORS_ORIGINS` — Comma-separated allowed origins
- `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` — Object storage
- `VITE_API_PROXY_TARGET`, `VITE_WS_PROXY_TARGET` — Frontend dev proxy targets

## Troubleshooting

- If `docker compose up` fails with port conflicts, stop local `uvicorn`, `vite`, `redis-server`, or `postgres` processes first.
- If the MinIO image is unavailable, `docker compose` uses `minio/minio:latest`.
- Worker logs: `docker compose logs -f worker`
- Backend logs: `docker compose logs -f backend`
