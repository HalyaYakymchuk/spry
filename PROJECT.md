# Spry Monorepo Specification

## 1. Repository Structure & Purpose
- `backend/`: FastAPI application, SQLAlchemy ORM, Alembic migrations. Handles data persistence and exposes the REST API.
- `frontend/`: Next.js App Router with TypeScript and Tailwind CSS. Single-page view for meeting analytics and creation.
- `docker-compose.yml`: Defines the local environment orchestrating Postgres, Backend, and Frontend.

## 2. API Contract
### Data Models
Meeting Object (JSON):
- `id`: integer (primary key)
- `title`: string (min 1, max 255 chars)
- `starts_at`: string (ISO 8601 UTC timestamp, e.g. "2026-10-01T09:00:00Z")
- `ends_at`: string (ISO 8601 UTC timestamp, e.g. "2026-10-01T10:00:00Z")
- `attendee_count`: integer (>= 1)

### Endpoints
- `GET /api/meetings`: Returns HTTP 200 with JSON list `[ { ...Meeting Object... } ]`.
- `POST /api/meetings`: Accepts JSON body:
  `{ "title": string, "starts_at": string, "ends_at": string, "attendee_count": integer }`
  Returns HTTP 201 with the created Meeting Object.
- `GET /api/health`: Returns HTTP 200 `{"status": "ok"}` for container readiness probes.

## 3. Technology & Version Pinning
- Base OS/Runtime: `python:3.12-slim`, `node:20-alpine`
- Database: `postgres:16-alpine`
- Backend: fastapi==0.110.0, uvicorn==0.28.0, sqlalchemy==2.0.28, alembic==1.13.1, pydantic==2.6.4, psycopg2-binary==2.9.9
- Frontend: next==14.2.0, react==18.3.1, tailwindcss==3.4.1

## 4. Startup Order
1. `postgres` starts on 5432. Healthcheck uses `pg_isready`.
2. `backend` waits for `postgres` via `condition: service_healthy`, runs `alembic upgrade head`, starts on port 8000.
3. `frontend` starts on port 3000 and communicates with the backend via internal Docker network (`http://backend:8000`).