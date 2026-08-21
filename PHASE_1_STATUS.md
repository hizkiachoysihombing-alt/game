# ElectroQuest implementation status

Last verified: 2026-08-20

Legend: **Implemented**, **Partial**, **Not implemented**, **Blocked**.

## Current student milestone

### Implemented and tested

- Docker Compose starts the frontend, backend, and Redis. The backend connects to the configured PostgreSQL database.
- Alembic applies the initial schema before FastAPI starts; FastAPI no longer calls `create_all`.
- Alembic model comparison reports no pending schema operations.
- Registration, login, current-user lookup, JWT access/refresh tokens, persistent browser session, and logout.
- Password validation and bcrypt hashing with a compatible pinned bcrypt version.
- Student/instructor/admin role model and backend RBAC dependencies.
- Course browsing, course detail, idempotent enrollment, lesson viewing, and persisted lesson completion.
- Numerical assessment with absolute tolerance and equivalent common engineering units (for example `2 A` and `2000 mA`).
- Idempotent problem sessions: replaying a submission does not consume more Energy or award XP again.
- Backend-authoritative XP ledger, levels, coins, daily activity streak, solved count, and running accuracy.
- Free-plan Learning Energy consumption for new graded problem sessions.
- Basic per-topic mastery, confidence, review/struggling flags, and persisted reasoning diagnosis.
- Daily quest assignment/progress and achievement evaluation from verified backend events.
- Aggregated `GET /api/dashboard/student` endpoint backed by PostgreSQL.
- Course-independent adaptive Journey with 32 Electrical Engineering domains, 118 topic nodes, mastery-aware difficulty selection, recent-exposure avoidance, and randomized top candidates.
- Fair Engineering League leaderboard using correctness, difficulty, and response speed, capped to the first 20 ranked attempts.
- Dashboard UI for rank, XP, coins, streak, Energy, enrolled-course progress, quests, mastery, recent errors, and next action.
- Refresh-token retry in the frontend API client.
- PostgreSQL integration tests with transaction rollback: health, complete student flow, unit conversion, and idempotency.
- Frontend TypeScript check and production Next.js build.

### Verification results

```text
pytest:             4 passed
alembic check:      No new upgrade operations detected
TypeScript:         passed
Next.js build:      passed (11 routes)
```

### Partial

- Curriculum content: the complete requested domain map is seeded; 19 original starter problems currently cover key journey domains. Large parameterized banks are still being expanded.
- Reasoning diagnosis: persists useful basic arithmetic/unit/concept diagnoses; advanced multi-step electrical-engineering diagnosis is not yet implemented.
- Mastery: basic evidence-weighted topic mastery works; mastery history and retention are not yet implemented.
- Gamification: core progression, one daily quest, and three achievements work. Weekly quests, ranked challenges, certificates, and scheduled leaderboard calculation remain.
- Subscription: Free subscription and Energy enforcement work. Pro entitlements and real billing require completion.
- RBAC: backend primitives and admin protection exist; instructor/admin product experiences remain incomplete.
- Error/loading states exist in core student pages but need consolidation into reusable shell components.

### Not implemented

- Full My Learning, Skill Tree, Knowledge Map detail, Challenges, Quests, Achievements, Leaderboard, Formula Book, Calculator, Notifications, Profile, Settings, Pricing, and Billing pages.
- Instructor course/question/quiz builders and analytics.
- Complete administrator product UI and audit log persistence.
- Parameterized/generated question architecture and question quality/validation history.
- Structured multi-step solutions and partial-credit rubric engine.
- Mastery history, adaptive learning, retention, and recommendation services.
- Centralized entitlement service and verified Stripe webhook workflow.
- Circuit lab, single-line diagram, per-unit, Ybus, power flow, fault analysis, protection lab, and AI tutor.
- Browser end-to-end test suite and critical-console-error automation.

### Blocked

- Real hosted checkout and webhook verification require Stripe credentials and product/price configuration.

## Next dependency-ordered work

1. Expand reusable application shell and remaining core student pages backed by current APIs.
2. Add mastery history and richer misconception rules with an Alembic migration.
3. Add question templates/instances/exposure/validation models and assessment services.
4. Centralize entitlements and finish Free/Pro backend enforcement.
5. Build instructor content-authoring workflows before advanced engineering labs.
