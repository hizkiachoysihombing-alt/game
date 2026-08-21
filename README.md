# ElectroQuest

**Learn. Calculate. Simulate. Master Electricity.**

An Intelligent Gamified Electrical Engineering Learning & Simulation Platform

## Project Overview

ElectroQuest is a production-quality, full-stack web application for electrical engineering education. It combines adaptive learning, interactive simulations, gamification, and comprehensive assessment to transform how students learn electricity.

## Architecture

```
electroquest/ (monorepo)
├── frontend/          (Next.js + React + TypeScript)
├── backend/           (FastAPI + Python)
├── docs/              (Architecture, API, deployment)
├── docker-compose.yml
└── .env.example
```

## Technology Stack

- **Frontend**: Next.js, React, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, Python, Pydantic, SQLAlchemy
- **Database**: PostgreSQL
- **Migrations**: Alembic
- **Deployment**: Docker, Docker Compose
- **Testing**: pytest (backend), Vitest + React Testing Library (frontend)

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or use Docker)

### Quick Start

1. Clone the repository
2. Copy `.env.example` to `.env` and configure
3. Start the stack:
   ```bash
   docker-compose up -d
   ```
4. Access the application:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Development Setup

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Project Structure

See [ARCHITECTURE.md](./docs/architecture/ARCHITECTURE.md) for detailed structure documentation.

## Features

### Phase 1 (Foundation)

- ✅ User authentication and RBAC
- ✅ Student, Instructor, Admin roles
- ✅ Course and learning path management
- ✅ Lesson and content delivery
- ✅ Rich question bank with parameterized questions
- ✅ Gamification (XP, levels, coins, streaks, quests, achievements)
- ✅ Mastery tracking
- ✅ Learning Energy quota (Free users)
- ✅ Subscription and entitlements (Pro)
- ✅ Dashboard and analytics
- ✅ Reasoning diagnosis foundation

### Phase 2+ (Advanced Features)

- Circuit Lab and simulation
- Single-Line Diagram editor
- Power Flow analysis
- Fault analysis
- Sequence networks
- Protection lab
- Adaptive problem generation
- AI Engineering Tutor

## API Documentation

Interactive API documentation available at:

```
http://localhost:8000/docs
```

## Database

All database changes are version-controlled via Alembic migrations:

```bash
cd backend
alembic upgrade head           # Apply migrations
alembic revision --autogenerate -m "Description"  # Create migration
```

## Testing

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## Deployment

Docker images are built and can be deployed to any container orchestration platform:

```bash
docker-compose -f docker-compose.prod.yml up
```

## Documentation

- [Architecture](./docs/architecture/ARCHITECTURE.md)
- [API Reference](./docs/api/API.md)
- [Database Schema](./docs/database/SCHEMA.md)
- [Gamification System](./docs/gamification/GAMIFICATION.md)
- [Billing & Subscriptions](./docs/billing/BILLING.md)

## Contributing

See CONTRIBUTING.md for development guidelines.

## License

Proprietary - All Rights Reserved

## Contact

For questions or support, contact the ElectroQuest team.
