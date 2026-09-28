# HR Multi-Agentic System

A web-based HR management platform with a layered AI foundation — a 5th-year Software Engineering final-year project (PFE).

The product is a **real HR system first**: identity, recruitment, organization, onboarding, leave, documents, and dashboards. The AI layer sits beside Core HR — it never invents authorization, never touches the database directly, and answers only from authorized tools or retrieved, ACL-filtered documents.

---

## Architecture

```mermaid
flowchart TB
  subgraph clients [Clients]
    Web[Next.js role portals]
  end

  subgraph backend [FastAPI modular monolith]
    API[API routers]
    Modules[Core HR modules]
    AI[AI layer]
    Shared[Shared storage / auth / meetings]
    API --> Modules
    API --> AI
    Modules --> Shared
    AI --> Modules
  end

  subgraph data [Data plane]
    PG[(PostgreSQL + pgvector)]
    S3[(AWS S3)]
    Meet[Google Calendar Meet]
  end

  Web -->|JWT REST| API
  Modules --> PG
  Shared --> S3
  Shared --> Meet
  AI -->|embeddings / FTS / vectors| PG
  AI -->|tools via services only| Modules
  AI -->|read company PDFs| Shared
```

### Design principles

| Principle | Practice |
|-----------|----------|
| Modular monolith | Domain modules under `backend/app/modules/` — one deployable API |
| User ≠ Employee | Identity accounts are separate from employment records ([ADR 002](docs/decisions/002-user-vs-employee.md)) |
| Agents never hit the DB | `Agent → Tool → Service → DB` ([ADR 003](docs/decisions/003-agent-database-isolation.md)) |
| Auth before generation | `AIExecutionContext` + permission filters run before tools / retrieval; the LLM only sees authorized context |
| Writes need confirmation | Recruitment, Leave, and Onboarding write tools return an HMAC-signed pending action; the user must Confirm in the UI before mutation |
| Embed ≠ generate | `gemini-embedding-2` for vectors; conversational `GEMINI_MODEL` for grounded answers |
| Registry ≠ authorization | Agent registry / router decide **availability + intent only**; tools + domain services remain authoritative |

### Backend layout

```
backend/app/
├── api/                 # Versioned HTTP (incl. /ai/assistant, /ai/onboarding, leave, recruitment, knowledge)
├── core/                # Config, security, database
├── modules/             # Core HR domains
│   ├── identity/        # Auth, RBAC, seed admin
│   ├── employees/       # Workforce records
│   ├── recruitment/     # Jobs, applications, fit fields, rejection_reason
│   ├── interviews/      # Invites, slots, feedback, outcomes, Meet
│   ├── onboarding/      # Tasks & verification
│   ├── documents/       # Employee docs + company library
│   ├── training/        # Assignments
│   ├── leave/           # Policies, dual approval
│   ├── notifications/   # In-app alerts
│   ├── dashboard/       # Aggregated HR metrics
│   └── profile/         # Self-service profile
├── ai/                  # AI foundation (in-tree)
│   ├── core/            # LLM providers, AIExecutionContext
│   ├── registry/        # Static agent catalog + permission / employee_id availability
│   ├── routing/         # Deterministic keyword router (no LLM supervisor)
│   ├── agents/          # Knowledge, Recruitment, Leave, Onboarding
│   ├── tools/           # Registry, auth, domain tools (incl. onboarding reads/writes)
│   ├── confirmation/    # HMAC confirmation tokens for AI writes
│   ├── audit/           # ai_tool_action_audits (minimal write audit)
│   ├── orchestration/   # Tool roundtrips
│   └── rag/             # Ingest → embed → retrieve → answer
└── shared/              # StorageService (S3), MeetingProvider, helpers
```

### Floating assistant (frontend)

On authenticated portals, the floating assistant is **one UI** backed by the **unified gateway**:

`POST /api/v1/ai/assistant/ask` → `get_available_agents` → deterministic `route_message` → Knowledge / Leave / Recruitment / Onboarding.

| Agent | When it is available | Confirm endpoint (writes) |
|-------|----------------------|---------------------------|
| Knowledge | `company_documents:read` | — (read-only) |
| Leave | `leaves:read` | `POST /api/v1/ai/leave/confirm` |
| Recruitment | `recruitment:read` (HR/Admin) | `POST /api/v1/ai/recruitment/confirm` |
| Onboarding | `employee_id` set **or** `onboarding:read` | `POST /api/v1/ai/onboarding/confirm` |

The UI stores each reply’s `agent_id` and routes Confirm by that id (not by pathname). Write proposals show a **Confirm / Cancel** card; the HMAC token stays in client state (not rendered as text). Cancel drops the token locally. Typing “I confirm” in chat does nothing — only the UI button completes a write.

Standalone per-agent ask/confirm routes remain for debugging and regression (`/ai/knowledge`, `/ai/leave`, `/ai/recruitment`, `/ai/onboarding`).

---

### AI / RAG pipeline (Phases 5.1–5.8)

```mermaid
flowchart LR
  PDF[Company PDF in S3]
  Ingest[Ingest + chunk]
  Embed[Gemini Embedding 2]
  Store[(pgvector + FTS)]
  Query[RAGQueryService]
  Hybrid[Hybrid retrieval RRF]
  Gen[GroundedGenerationService]
  Answer[RAGAnswer + citations]

  PDF --> Ingest --> Embed --> Store
  Query --> Embed
  Query --> Hybrid
  Store --> Hybrid
  Hybrid --> Gen --> Answer
```

1. **Ingest** — download company-library PDF via `StorageService`, parse pages, deterministic chunking with provenance (`chunk_id`, pages, `content_hash`).
2. **Embed** — persist 768-d vectors (`RETRIEVAL_DOCUMENT`); query embeds use `RETRIEVAL_QUERY`.
3. **Retrieve** — ACL (`company_documents:read`, ACTIVE docs for non-HR) → cosine HNSW + PostgreSQL FTS → RRF fusion → context budget.
4. **Generate** — conversational Gemini answers **only** from that context; citations mapped from retrieval metadata (not invented by the model). Empty context → deterministic abstention (no LLM call).

Authorization is decided **before** generation. Document text is treated as untrusted data (prompt-injection defense).

---

### Recruitment AI (Phases 6.1–6.4G) — functionally complete

```mermaid
flowchart TD
  HR[HR natural language]
  Ask[POST /ai/recruitment/ask]
  Agent[RecruitmentAgent + tools]
  Gate[Confirmation gate]
  Pending[pending_confirmation + HMAC token]
  UI[Confirm or Cancel]
  Conf[POST /ai/recruitment/confirm]
  Svc[ApplicationService / InterviewService / MeetingService]
  DB[(PostgreSQL)]
  Audit[ai_tool_action_audits]

  HR --> Ask --> Agent
  Agent -->|read tools| Svc
  Agent -->|write tool| Gate
  Gate -->|no execute yet| Pending --> UI
  UI -->|Confirm| Conf --> Agent
  Agent -->|verify HMAC + re-auth + execute_writes| Svc --> DB
  Agent --> Audit
```

**What it covers**

| Phase | Capability |
|-------|------------|
| 6.1 | CV extraction (careers apply pre-fill) |
| 6.2 | Candidate ↔ job fit analysis (HR-only scores) |
| 6.3 | Recruitment Agent reads + overview + shortlist/reject |
| 6.4A–C | Multi-interviewer invites, notifications, slots, structured feedback |
| 6.4D | Real Google Meet via Calendar `conferenceData` (`MeetingProvider`) |
| 6.4E | Interview **read** tools on the agent |
| 6.4F | Interview **write** tools behind confirmation |
| 6.4G | Hardening: rejection reason, audits, confirm UX, regression |

**Read tools (examples)** — `get_job`, `get_application`, `get_application_fit`, `list_recruitment_applications`, `find_employees`, `get_interview`, `list_interviews`, `get_interview_feedback`, `get_candidate_interviews`, `get_upcoming_interviews`.

**Write tools (all confirmation-gated, `recruitment:write`)**

1. `shortlist_application`
2. `reject_application` (optional reason **persisted** as `rejection_reason`; blocked while an active interview exists)
3. `create_interview_invitation` (primary + optional panel — only at invite time)
4. `retry_interview_meeting` (idempotent Meet provisioning; never calls Google from the agent)
5. `record_interview_outcome` (`rejected` \| `another_interview` \| `hired` — explicit HR only)

**Confirmation security**

- Opaque HMAC token binds `user_id`, `tool_name`, exact `arguments`, and expiry (~10 minutes).
- Confirm re-checks permission and current business state; a valid HMAC alone is not enough.
- Replay after a successful mutate is blocked by domain transitions (Meet retry stays intentionally idempotent).
- Minimal append-only audit: `ai_tool_action_audits` (`proposed` → `confirmed` → `executed` / `failed`).

**Interview workflow (domain)**

- HR creates invitation (shortlisted application) → primary proposes slots → candidate selects → Meet ensured → primary completes with recommendation → HR records outcome (hire may create employee + onboarding).
- Agent does **not** propose/select slots, submit feedback, cancel/reschedule, or change panel after invite (known domain limits).
- Interviewer recommendation ≠ automatic hire/reject.

Hardening report: [`backend/docs/phase_6_4g_recruitment_hardening_report.md`](backend/docs/phase_6_4g_recruitment_hardening_report.md).

---

### Leave AI (Phases 7.1–7.4B) — scoped reads + confirmation-gated writes

```mermaid
flowchart TD
  User[User on leave paths]
  Ask[POST /ai/leave/ask]
  Agent[LeaveAgent + tools]
  Gate[Confirmation gate]
  Pending[pending_confirmation + HMAC token]
  UI[Confirm or Cancel]
  Conf[POST /ai/leave/confirm]
  Svc[LeaveService / EmployeeService]
  DB[(PostgreSQL)]
  Audit[ai_tool_action_audits]

  User --> Ask --> Agent
  Agent -->|scoped read tools| Svc
  Agent -->|write tool| Gate
  Gate -->|no execute yet| Pending --> UI
  UI -->|Confirm| Conf --> Agent
  Agent -->|verify HMAC + re-auth + execute_writes| Svc --> DB
  Agent --> Audit
```

**What it covers**

| Phase | Capability |
|-------|------------|
| 7.1–7.2 | Leave Agent + HR read tools + `POST /ai/leave/ask` |
| 7.3A/B | Auth audit + scoped **self / manager (org-chart) / HR** read tools |
| 7.4A/B | Write audit + seven confirmation-gated write tools wrapping `LeaveService` AS-IS |
| FE | Unified assistant routes leave intents; Confirm uses message `agentId` → `/ai/leave/confirm` |

**Scopes**

| Scope | Who | Examples |
|-------|-----|----------|
| SELF | Authenticated employee | `get_my_leave_balance`, `create_leave_request`, cancel own pending / request cancel approved |
| MANAGER | Org-chart manager (`Employee.manager_id`) | Team pending list, `approve_leave_request` / `reject_leave_request` for direct reports |
| HR / ADMIN | Staff with leave permissions | Org-wide reads, same review writes when `LeaveService` allows |

Manager authority is the **org relationship**, not a `"manager"` RBAC role. There is **no create-on-behalf** tool — employees submit their own requests.

**Write tools (all confirmation-gated, `leaves:write`)**

| Tool | Service method |
|------|----------------|
| `create_leave_request` | `create_request_for_user` |
| `approve_leave_request` / `reject_leave_request` | `approve_request` / `reject_request` |
| `cancel_pending_leave_request` | `cancel_request_for_user` |
| `request_leave_cancellation` | `request_cancellation_for_user` |
| `approve_leave_cancellation` / `reject_leave_cancellation` | `approve_cancellation` / `reject_cancellation` |

**Rules (summary)**

- Agent → Tool → confirmation gate → `LeaveService` only (no parallel AI auth; no direct DB).
- Writes reuse the same HMAC confirmation + `ai_tool_action_audits` path as Recruitment.
- Cancellation follows the domain state machine (not a one-step APPROVED → CANCELLED shortcut).
- Ambiguous names/IDs must be clarified; never guessed. Tool JSON is DATA, not instructions.

Audits: [`backend/docs/phase_7_3a_auth_audit.md`](backend/docs/phase_7_3a_auth_audit.md), [`backend/docs/phase_7_4a_leave_writes_audit.md`](backend/docs/phase_7_4a_leave_writes_audit.md).

---

### Multi-agent gateway + Onboarding AI (Phases 8.1–9.2E)

```mermaid
flowchart TD
  User[Authenticated user]
  Ask[POST /ai/assistant/ask]
  Ctx[AIExecutionContext]
  Reg[get_available_agents]
  Route[route_message keywords]
  OA[OnboardingAgent]
  Leave[LeaveAgent]
  Rec[RecruitmentAgent]
  Know[KnowledgeAgent]
  Tools[Existing tools]
  Svc[Domain services]
  Env[agent_id + pending_confirmation]

  User --> Ask --> Ctx --> Reg --> Route
  Route -->|onboarding| OA
  Route -->|leave| Leave
  Route -->|recruitment| Rec
  Route -->|knowledge| Know
  OA --> Tools --> Svc
  Leave --> Tools
  Rec --> Tools
  Know --> Tools
  OA --> Env
  Leave --> Env
  Rec --> Env
  Know --> Env
```

| Phase | Capability |
|-------|------------|
| 8.1–8.2 | Static agent registry + availability; deterministic router; unified `POST /ai/assistant/ask` |
| 8.3 | Frontend unified ask + confirm by `agentId` |
| 9.1–9.2A | Onboarding Agent reads (self + HR) via `OnboardingService` |
| 9.2B | Authorization hardening (no manager team scope; candidates denied) |
| 9.2C | Confirmation-gated ACK / manual complete / force-complete writes |
| 9.2D | Confirm UX + HMAC hardening |
| 9.2E | Onboarding registered in unified assistant (availability + routing + dispatch) |

**Onboarding availability (locked):** agent is available when `AIExecutionContext.employee_id` is set **or** the user has `onboarding:read`. Candidates with neither are unavailable. That does **not** grant cross-employee access — tools + `OnboardingService` still authorize.

**Write tools (confirmation-gated)** — employee ACK of own tasks; HR/Admin manual task complete and force-complete onboarding (see [`backend/docs/phase_9_2e_onboarding_unified_assistant.md`](backend/docs/phase_9_2e_onboarding_unified_assistant.md)).

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16 + **pgvector** |
| Object storage | AWS S3 (`StorageService`) |
| Meetings | Google Calendar API + Meet (`MeetingProvider`: noop / fake / google) |
| Embeddings | Gemini Embedding 2 (`gemini-embedding-2`) |
| Generation / tools | Gemini Flash (`GEMINI_MODEL`), provider-agnostic `LLMProvider` (Mistral adapter also present) |
| Auth | JWT + RBAC permissions |

---

## Features

### Identity & access

- JWT authentication with roles: admin, HR, manager, employee, candidate
- Admin creates HR accounts; candidates self-register for careers
- HR-staff gates on sensitive recruitment and onboarding writes
- Organization integrity: managers must exist, cannot be self, cannot introduce cycles; **new** manager assignments must be **ACTIVE**

### Recruitment & interviews

- Job posting, application questions, CV / cover letter upload to S3
- CV extraction pre-fill on careers apply
- Status workflow: submitted → screening → shortlisted / rejected / hired (hire only via interview outcome)
- Optional **rejection reason** (HR-visible); candidates get status notifications on shortlist and reject
- Fit analysis for HR review (score, skills, explanation)
- Multi-interviewer invitations (one primary + panel), primary-led slots, candidate slot confirm
- Structured interviewer feedback + recommendation; HR final outcome
- Google Meet link provisioning (idempotent; credentials never exposed to the frontend or AI tool output)
- Hire → employee creation and onboarding kickoff

### Organization & employees

- Departments, org positions, reporting hierarchy / directory
- Employee create/edit with manager and position assignment

### Onboarding, documents & training

- Hire-triggered onboarding with task templates and verification sync
- **Employee documents** (onboarding / personal files) and **Company Document Library** + private docs (separate stores)
- Training assignments tied to the employee lifecycle
- Lifecycle and task notifications
- **Onboarding Agent** — self + HR reads; confirmation-gated ACK / complete writes via the unified assistant (or `POST /api/v1/ai/onboarding/ask` + `/confirm`)

### Leave

- Leave types, policies, and balances
- Dual manager / HR approval workflow and calendar views
- Derived on-leave work status for dashboards
- Cancellation request / approve / reject flows
- **Leave Agent** — scoped self / team / HR tools via the unified assistant (or `POST /api/v1/ai/leave/ask` + `/confirm`)

### HR dashboard & portals

- Aggregated HR dashboard API and animated UI
- Role shells: admin, HR, manager, employee, and careers / candidate portals
- In-app notifications (bell + pages)
- Floating **unified AI assistant** (intent routing across Knowledge, Leave, Recruitment, Onboarding)

### AI foundation (shipped)

- Provider-agnostic LLM layer + `AIExecutionContext`
- Tool registry with authorization
- **Agent registry + deterministic router** + unified `POST /api/v1/ai/assistant/ask`
- **Knowledge Agent** — RAG Q&A with citations over company documents
- **Recruitment Agent** — authorized read/write tools over recruitment & interviews (writes confirmation-gated)
- **Leave Agent** — scoped leave reads + confirmation-gated writes via `LeaveService`
- **Onboarding Agent** — self/HR onboarding reads + confirmation-gated writes via `OnboardingService`
- Shared HMAC confirmation + `ai_tool_action_audits` for AI writes
- Full RAG path through **grounded generation + citations** (see pipeline above)
- Smoke scripts under `backend/scripts/` (RAG + recruitment agent helpers)

### Not yet

- Training / Document / Offboarding specialized agents
- LLM supervisor / chat history / rich Markdown renderer for the assistant
- LLM rerank / query reformulation for RAG
- Autonomous domain decisions (writes always require UI confirmation)
- Manager onboarding “reports” scope (employees see self only; HR sees org-wide)

---

## Quick start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (local frontend)
- Python 3.12+ (local backend)
- Gemini API key for AI / RAG / Recruitment Agent
- AWS credentials for S3 document flows
- Optional: Google OAuth client + refresh token for live Meet (`MEETING_PROVIDER=google`)

### Run with Docker

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| PostgreSQL | `localhost:5433` → container `5432` |

> Host port **5433** avoids clashing with a local Postgres on 5432. Use `127.0.0.1:5433` in `backend/.env` when running uvicorn on the host.

### Default admin

```
Email:    admin@hr-platform.local
Password: admin123
```

Copy `backend/.env.example` → `backend/.env` and set at least:

- `GEMINI_API_KEY` / `GEMINI_MODEL`
- `AWS_*` for S3
- `DATABASE_URL` (Compose vs host — see comments in `.env.example`)
- `SECRET_KEY` (also used for AI write confirmation HMAC unless `AI_CONFIRMATION_SECRET` is set)
- Optional Meet: `MEETING_PROVIDER`, `GOOGLE_MEET_*`

After pulling, apply migrations:

```bash
cd backend
alembic upgrade head
# Current head includes 045_application_rejection_reason
```

---

## Development

### Backend (local)

```bash
cd backend
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
# source .venv/bin/activate

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

On Windows, helpers under `scripts/` can stop stale ports and start a clean stack (`dev-stop.ps1`, `dev-start.ps1`; frontend also supports `npm run dev:fresh`).

### RAG smoke (after a company PDF is indexed)

From `backend/` with the venv active:

```powershell
$env:PYTHONPATH = "."
python scripts/smoke_rag_answer.py
```

Expect exactly **one** embedding call and **one** generation call, plus `smoke_rag_answer_ok: True`.

Earlier pipeline checks: `smoke_ingest_pdf.py` → `smoke_embed_chunks.py` → `smoke_hybrid_retrieve.py` → `smoke_rag_query.py`.

### Unified assistant (Knowledge / Leave / Recruitment / Onboarding)

1. Log in (employee with a linked Employee record, or HR) → open the floating assistant on any authenticated portal.
2. Ask in natural language; the backend routes by intent:
   - Leave: “What’s my leave balance?”
   - Onboarding: “What’s my onboarding progress?” / “Acknowledge my pending onboarding task.”
   - Knowledge: “What does the company policy say about remote work?”
   - Recruitment (HR): “How many candidates are currently shortlisted?”
3. **Writes** (leave, recruitment, or onboarding ACK/complete): expect a **Confirm / Cancel** card → Confirm hits the matching `/ai/*/confirm` from the message `agentId`; Cancel does nothing.
4. Do not type “I confirm” in chat — only the UI button completes the write.
5. Candidates without `employee_id` / `onboarding:read` should get unavailable for onboarding (and typically have no agents).

---

## Project structure

```
HR-Multi-Agentic-System/
├── backend/                 # FastAPI app, Alembic, smoke scripts
│   ├── app/
│   │   ├── api/
│   │   ├── ai/              # LLM, agents, tools, confirmation, audit, RAG
│   │   ├── modules/         # Core HR domains
│   │   └── shared/          # S3, MeetingProvider, etc.
│   ├── alembic/
│   ├── docs/                # Phase reports (e.g. 6.4G hardening)
│   ├── scripts/             # RAG / recruitment smoke helpers
│   └── tests/
├── frontend/                # Next.js role portals + AI assistant
├── docs/
│   ├── architecture/        # Architecture index
│   └── decisions/           # ADRs
├── scripts/                 # Local Windows dev helpers
├── docker-compose.yml       # db (pgvector) + backend + frontend
└── README.md
```

Architecture decisions: [docs/architecture/README.md](docs/architecture/README.md).

---

## Current status

- [x] Backend foundation (FastAPI, PostgreSQL, Alembic, pgvector)
- [x] Identity & authentication (JWT, RBAC)
- [x] Recruitment (jobs, applications, interviews, hiring)
- [x] Organization structure (departments, positions, reporting tree)
- [x] Onboarding workflow (tasks, verification, notifications)
- [x] Employee documents, company library, private documents & training
- [x] Leave management (policies, dual approval, calendar, on-leave status)
- [x] Premium HR dashboard & role portals
- [x] Core HR security hardening (RBAC / IDOR, inactive-manager validation)
- [x] AI foundation (LLM providers, execution context, authorized tools)
- [x] RAG through grounded generation + citations (Phases 5.1–5.8)
- [x] Knowledge Agent + in-app floating assistant
- [x] Recruitment AI (CV extraction, fit, agent reads/writes, Meet, confirmation, audit) — Phases 6.1–6.4G
- [x] Leave Agent (scoped reads + confirmation-gated writes) — Phases 7.1–7.4B
- [x] Multi-agent registry + deterministic router + unified `/ai/assistant/ask` — Phases 8.1–8.3
- [x] Onboarding Agent (reads, auth harden, confirmation writes, unified registration) — Phases 9.1–9.2E
- [ ] Training / Document / Offboarding agents
- [ ] Assistant chat history & richer answer rendering

---

## License

See [LICENSE](LICENSE).
