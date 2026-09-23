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

On Windows, optional helpers under `scripts/` can stop stale ports and start a clean stack (`dev-stop.ps1`, `dev-start.ps1`; frontend also supports `npm run dev:fresh`).

## Project Structure

```
hr-multi-agent-system/
├── backend/          # FastAPI modular monolith
├── frontend/         # Next.js application (role portals)
├── ai/               # AI layer (future)
├── infrastructure/   # Docker & deployment configs
├── scripts/          # Local dev helpers
└── docs/             # Architecture & decisions
```

## Features

### Identity & access

- JWT authentication with role-based access (admin, HR, manager, employee, candidate)
- Admin can create HR accounts; candidates self-register for careers
- HR-staff gates on sensitive recruitment and onboarding writes
- Organization integrity: managers must exist, cannot be self, cannot introduce cycles, and **new** manager assignments must be **ACTIVE** (historical inactive managers may remain)

### Recruitment

- Job posting and applications
- Interview invitations with flexible slot counts (2–5)
- Interview completion, outcomes, shortlist notifications, and hire → employee creation

### Organization

- Departments and org positions
- Reporting hierarchy / directory for HR and employee portals
- Employee create/edit with manager and position assignment

### Onboarding

- Hire-triggered onboarding with task templates/catalogue
- Task verification sync and completion lifecycle
- Progress tracking for HR and employee self-service
- Lifecycle and task notifications

### Documents & training

- Employee document upload/storage with secure access
- Training assignments tied to the employee lifecycle

### Leave

- Leave types, policies, and balances
- Dual manager / HR approval workflow
- Leave calendar views
- Derived on-leave work status (banner / dashboard signals)

### HR dashboard & UX

- Aggregated HR dashboard API (importance-first metrics, leave overview, upcoming deadlines)
- Animated dashboard UI (shadcn/Lucide/Recharts) with corporate brand palette
- Role shells: admin, HR, manager, employee, and careers/candidate portals
- In-app notifications (bell + notification pages)

### Employee self-service

- Profile and profile picture
- Own leave requests and balances
- Onboarding progress and organization view

## Current Status

- [x] Backend foundation (FastAPI, PostgreSQL, Alembic)
- [x] Identity & authentication (JWT, RBAC)
- [x] Recruitment (jobs, applications, interviews, hiring)
- [x] Organization structure (departments, positions, reporting tree)
- [x] Onboarding workflow (tasks, verification, notifications)
- [x] Employee documents & training assignments
- [x] Leave management (policies, dual approval, calendar, on-leave status)
- [x] Premium HR dashboard & role portals
- [x] Core HR security hardening (RBAC/IDOR gates, inactive-manager validation)
- [ ] AI multi-agent layer
