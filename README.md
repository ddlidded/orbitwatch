# OrbitWatch

Production-ready real-time monitoring for Thermo Scientific Orbitrap Exploris 480 instruments, branded for isotopiq.

## Components

- `agent/` — C# .NET 8 worker service that runs on the Windows instrument PC
- `backend/` — Python FastAPI central data service, auth, processing, and APIs
- `frontend/` — React + TypeScript + Vite dashboard
- `infrastructure/` — Reverse-proxy and deployment configs
- `docs/` — Architecture and operations documentation
- `scripts/` — Development and setup helpers
- `tests/` — Test suites

## Docker deployment

The fastest way to run the full stack is with Docker Compose.

```bash
# Copy and edit environment variables
cp .env.example .env

# Build and start PostgreSQL, Redis, MinIO, backend, worker, and frontend
docker compose up --build -d
```

Then open http://localhost:5173. The default admin account is `admin@isotopiq.dev` / `OrbitWatch-Admin-2024!`.

For production:

```bash
cp .env.example .env
# Set strong SECRET_KEY, POSTGRES_PASSWORD, S3_SECRET_KEY, and CORS_ORIGINS
# AGENT_BOOTSTRAP_TOKEN is optional (used for auto agent registration)
docker compose -f docker-compose.prod.yml up --build -d
```

Production serves on http://localhost (Caddy reverse proxy) or configure TLS by editing `infrastructure/Caddyfile`.

### Easypanel

For Easypanel deployments, use `docker-compose.easypanel.yml` and follow `docs/easypanel.md`.

## Development quick start

Without Docker:

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

The backend defaults to SQLite if `DATABASE_URL` is not set to PostgreSQL.

## Instrument agent

The agent can run in two modes:

- `replay` (default) — deterministic simulator for development
- `helios` — Thermo IAPI adapter for the Exploris 480 (Windows + Tune/IAPI required)

Set `Agent:Mode=helios` in `agent/OrbitWatchAgent/appsettings.json` on the instrument PC. The agent uses the Thermo IAPI .NET Standard reference assemblies shipped in `agent/OrbitWatchAgent/lib/` and loads the instrument-specific implementation from the local Tune installation via registry.

For pre-registered deployments, use the `Connect Instrument` page in the app to generate an agent token and IDs, then paste them into `agent/OrbitWatchAgent/appsettings.json`.

## License / proprietary components

Thermo Fisher Scientific IAPI and Helios are proprietary and are not redistributed. The vendored `Thermo.API.*` DLLs in `agent/OrbitWatchAgent/lib/` are reference assemblies from the user-supplied `iapi-master` archive and are used for compilation only. The full IAPI runtime must be installed on the instrument PC by Thermo-authorized personnel.
