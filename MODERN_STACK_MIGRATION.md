# Vegz modern-stack migration

## Target stack
- Web portals: Next.js + TypeScript (`web/` in each app repository)
- Customer Android app foundation: React Native + Expo (`vegz-user/mobile/`)
- APIs: existing Python + FastAPI services
- Target database: PostgreSQL with psycopg 3

## Local modern-stack profile
Run from this repository's directory, with the four app repositories checked out as sibling folders:

```bash
docker-compose -f docker-compose.postgres.yml config
docker-compose -f docker-compose.postgres.yml up -d --build
```

Web foundation URLs:
- Customer: http://localhost:3000
- Shop: http://localhost:3001
- Agent: http://localhost:3002
- Admin: http://localhost:3003

FastAPI APIs:
- Admin: http://localhost:8000
- Agent: http://localhost:8001
- Shop: http://localhost:8002
- Customer: http://localhost:8003
- PostgreSQL: localhost:5433

## Important migration boundary
This profile creates a new, separate PostgreSQL volume and empty service databases. It does not delete the legacy MySQL or SQLite volumes, and it does not automatically migrate existing records. Keep using the existing docker-compose.all.yml until the PostgreSQL profile has been tested and the data migration has been planned.

The new Next.js pages and Expo app are initial TypeScript foundations, not feature-complete replacements yet. Authentication, catalog loading, partner approvals, availability, image uploads, checkout, and delivery flows must be ported to these clients and tested against the APIs before switching production traffic. Do not expose this development profile publicly or use its demo secrets in production.
