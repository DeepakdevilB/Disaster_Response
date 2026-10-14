# Project: Intelligent Disaster Response & Emergency Coordination Platform

## What we are building
A final-year B.Tech major project: a real-time, AI-assisted platform where citizens
report emergencies, the system auto-classifies and prioritizes them, detects duplicate
reports, geocodes locations, and recommends resource allocation (ambulances, boats,
rescue teams) on a live command-center dashboard.

## Hard constraints
- Total budget is INR 0. Use only free/open-source tools. No paid APIs (no OpenAI,
  no Google Maps). LLM and embeddings must run locally.
- Must be production-quality: tests, security, logging, Docker, documentation.
- Small student team; prefer simple, explainable solutions over clever ones.

## Tech stack (do not change without asking)
- Backend: FastAPI (Python 3.11), SQLAlchemy 2, Alembic, Celery
- Data: PostgreSQL 16 + PostGIS + pgvector, Redis 7, RabbitMQ, MinIO
- Frontend: React + Vite + TypeScript, Tailwind, Leaflet + OpenStreetMap
- AI/ML: scikit-learn, Hugging Face Transformers, sentence-transformers
  (multilingual MiniLM), Ollama for the local LLM, PyTorch for image model
- Optimization: SciPy linear_sum_assignment (Hungarian algorithm)
- DevOps: Docker Compose, Nginx, GitHub Actions, Prometheus + Grafana
- Testing: pytest, Playwright, Locust, OWASP ZAP

## Architecture rules
- Modular monolith API + separate Celery workers (NLP, embedding/dedup, geo, CV).
- Report submission: validate -> save -> publish to RabbitMQ -> return HTTP 202.
  Never run AI inside the request.
- Consumers must be idempotent; use retries and a dead-letter queue.
- Roles: citizen, authority, rescue, admin. RBAC is deny-by-default.
- LLM output is advisory only: schema-validated, never auto-dispatches resources.
- Every AI prediction stores model name/version and confidence; authorities can override.
- Priority score = transparent weighted formula (0-100) with per-factor breakdown.

## Working rules
- Work on ONE phase/task at a time. Before coding, state a short plan.
- Write tests with the code. Do not move on while tests fail.
- Commit small, with clear messages. Never commit secrets; use .env.example.
- Follow the plan in docs/implementation_plan.xlsx (task IDs T-001...T-075).
- If a requirement is ambiguous or a choice changes the architecture, ask me first.
- Be honest: if something is mocked, simulated or not working, say so. Never fake
  metrics or test results.
- After each task: summarize what changed, how to run it, and what to do next.

## Definition of done (per task)
Code + tests passing + lint clean + docs/README updated + runs via docker compose.