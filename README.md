# HR Multi-Agentic System

A web-based HR management platform enhanced with a multi-agent AI layer — a 5th-year Software Engineering final-year project (PFE).

## Architecture

- **Frontend**: Next.js, TypeScript, Tailwind CSS
- **Core HR Backend**: FastAPI modular monolith, SQLAlchemy, PostgreSQL
- **AI Layer**: LangGraph / LangChain (future phase)

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local backend development)

### Run with Docker

```bash
docker compose up --build
```

Services:

| Service    | URL                        |
|------------|----------------------------|
| Frontend   | http://localhost:3000      |
| Backend    | http://localhost:8000      |
| API Docs   | http://localhost:8000/docs |
| PostgreSQL | localhost:5432             |

### Default Admin Credentials

```
Email:    admin@hr-platform.local
Password: admin123
```

## Development

### Backend (local)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend (local)

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Project Structure

```
hr-multi-agent-system/
├── backend/          # FastAPI modular monolith
├── frontend/         # Next.js application
├── ai/               # AI layer (future)
├── infrastructure/   # Docker & deployment configs
└── docs/             # Architecture & decisions
```

## Current Status

- [x] Backend foundation (FastAPI, PostgreSQL, Alembic)
- [x] Identity & Authentication (JWT, RBAC)
- [x] Frontend login & dashboard
- [ ] Recruitment module
- [ ] AI layer
