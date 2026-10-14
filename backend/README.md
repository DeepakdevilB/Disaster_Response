# Backend — Disaster Response API

The FastAPI backend for the Intelligent Disaster Response Platform.
See the root [README](../README.md) for setup instructions.

## Running locally (without Docker)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows (or `source .venv/bin/activate` on Linux/Mac)
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Tests

```bash
pytest                              # unit tests only (no Postgres needed)
pytest -m integration               # integration tests (needs a running Postgres + PostGIS)
pytest --cov=app --cov-report=html  # coverage report
```

## Lint

```bash
ruff check .
ruff format --check .
```
