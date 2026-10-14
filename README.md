# Intelligent Disaster Response & Emergency Coordination Platform

> AI-assisted platform for real-time emergency reporting, classification, deduplication,
> priority scoring and resource-allocation recommendations.

**Final-year B.Tech major project.** Budget: INR 0 — every component is free/open-source.

---

## Quick start (one command)

```bash
# 1. Clone and create your local environment file
git clone <repo-url> && cd <repo>
cp .env.example .env          # edit passwords if you like; defaults work for local dev

# 2. Build and start everything (Postgres+PostGIS+pgvector, Redis, RabbitMQ, MinIO, API)
docker compose up -d --build --wait

# The --wait flag blocks until every container reports healthy.
# First run takes ~3 minutes to build; subsequent starts are <10 seconds.
```

Once healthy, visit:

| Service             | URL                                      |
| ------------------- | ---------------------------------------- |
| **API docs**        | http://localhost:8000/docs               |
| **Liveness**        | http://localhost:8000/health              |
| **Readiness**       | http://localhost:8000/health/ready        |
| RabbitMQ management | http://localhost:15672 (disaster/change-me-rabbitmq) |
| MinIO console       | http://localhost:9001 (disaster-minio/change-me-minio) |

### Run the test suite

```bash
# Inside Docker (Python 3.11, same as CI):
docker compose --profile test run --rm backend-tests

# Or locally (Python 3.11+ with the backend venv activated and Postgres running):
cd backend
pip install -e ".[dev]"
pytest -v
```

### Milestone M3 Intelligent Engine Demo (T-048)

```bash
cd backend
python scripts/demo_phase3.py
```

### Lint

```bash
cd backend && ruff check . && ruff format --check .
```

### Stop / tear down

```bash
docker compose down            # stop containers, keep data
docker compose down -v         # stop and delete all volumes (fresh start)
```

---

## Repository layout

```
backend/        FastAPI API service, Alembic migrations, backend tests
workers/        Celery workers (NLP, embedding, geo, CV) — Phase 2+
frontend/       React + Vite + TypeScript — Phase 1
ml/             Datasets, training scripts, exported models — Phase 2+
infra/          Custom Dockerfiles (Postgres with PostGIS + pgvector)
docs/           Implementation plan, ADRs, design documents
tests/          Cross-service: E2E (Playwright), load (Locust), security (ZAP) — Phase 3+
.github/        CI/CD workflows and PR template
```

## Tech stack

| Layer       | Choice                                    |
| ----------- | ----------------------------------------- |
| API         | FastAPI, SQLAlchemy 2, Alembic, psycopg 3 |
| Data        | PostgreSQL 16 + PostGIS + pgvector, Redis 7, RabbitMQ 3, MinIO |
| Frontend    | React, Vite, TypeScript, Tailwind, Leaflet + OpenStreetMap |
| AI/ML       | scikit-learn, Transformers, sentence-transformers, Ollama, PyTorch |
| Optimiser   | SciPy (Hungarian algorithm)               |
| DevOps      | Docker Compose, Nginx, GitHub Actions, Prometheus + Grafana |

See [docs/implementation_plan.xlsx](docs/implementation_plan.xlsx) for the full 75-task plan.

## License

This project is academic work. Contact the authors before redistributing.
