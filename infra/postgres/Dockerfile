# PostgreSQL 16 + PostGIS 3.5 + pgvector, in a single image.
# The official postgis image already includes the PGDG apt repository,
# so pgvector is installed from the matching postgresql-16-pgvector package.
# Extensions are enabled per database by the Alembic migration, not here.
FROM postgis/postgis:16-3.5

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
