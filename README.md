# OrbitWatch

Production-ready real-time monitoring for Thermo Scientific Orbitrap Exploris 480 instruments, branded for isotopiq.

## Components

- `agent/` — C# .NET 8 worker service that runs on the Windows instrument PC
- `backend/` — Python FastAPI central data service, auth, processing, and APIs
- `frontend/` — React + TypeScript + Vite dashboard
- `infrastructure/` — Docker Compose and deployment configs
- `docs/` — Architecture and operations documentation
- `scripts/` — Development and setup helpers
- `tests/` — Test suites (to be expanded)

## Development quick start

```bash
cp .env.example .env
# Start PostgreSQL, Redis, MinIO and backend/frontend
docker compose -f infrastructure/docker-compose.dev.yml up --build
```

The default admin account is `admin@isotopiq.dev` / `OrbitWatch-Admin-2024!`.

## Instrument agent

The agent can run in two modes:

- `replay` (default) — deterministic simulator for development
- `helios` — Thermo IAPI adapter for the Exploris 480 (Windows + Tune/IAPI required)

Set `Agent:Mode=helios` in `agent/OrbitWatchAgent/appsettings.json` on the instrument PC. The agent uses the Thermo IAPI .NET Standard reference assemblies shipped in `agent/OrbitWatchAgent/lib/` and loads the instrument-specific implementation from the local Tune installation via registry.

## License / proprietary components

Thermo Fisher Scientific IAPI and Helios are proprietary and are not redistributed. The vendored `Thermo.API.*` DLLs in `agent/OrbitWatchAgent/lib/` are reference assemblies from the user-supplied `iapi-master` archive and are used for compilation only. The full IAPI runtime must be installed on the instrument PC by Thermo-authorized personnel.
