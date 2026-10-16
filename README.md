# Vegz Admin

Central operations console for shop/agent onboarding, product moderation, order oversight, customers, settings and audit history.

## Stack

- Web: Next.js + TypeScript under `web/`
- API: FastAPI + SQLAlchemy under `backend/`
- Local multi-app data store: PostgreSQL via `docker-compose.postgres.yml`; standalone API also supports SQLite configuration.
- User, shop and agent clients keep separately owned schemas and interact through API contracts rather than sharing tables blindly.

## Existing operations workflows

- Administrator email/password sign-in; initial super-admin provisioned from environment.
- Dashboard metrics, orders, shop/agent records and approval/suspension workflows.
- Product moderation, customer records/status, settings, audit history and super-admin user management.
- Authenticated partner registration callbacks from shop/agent and approval callbacks to their services when the corresponding URLs and shared token are configured.

**Integration boundary:** existing admin managed-records remain separate from some actual shop/order records. A new approval or order change may not propagate to every service in all deployments; use the PostgreSQL multi-service Compose profile for development, test the callback behavior and complete the authoritative cross-service workflows before production. Do not point all separate SQLAlchemy schemas to a single DB without reviewed migrations and table ownership.

## Run the Next.js portal

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:3000`. The Next.js operations workspace calls the FastAPI admin API for administrator sign-in, dashboard metrics, shop/agent approval and suspension, product moderation, order status transitions, customer access, editable settings, audit history and (for super-admins) admin-account controls.

## Run the complete local PostgreSQL stack

From this repository root (with sibling `vegz-user`, `vegz-shop`, and `vegz-agent` folders alongside this repository):

```bash
docker-compose -f docker-compose.postgres.yml up --build -d
```

- Admin API: `http://localhost:8000`
- Agent API: `http://localhost:8001`
- Shop API: `http://localhost:8002`
- Customer API: `http://localhost:8003`
- Customer web: `http://localhost:3000`
- Shop web: `http://localhost:3001`
- Agent web: `http://localhost:3002`
- Admin web: `http://localhost:3003`

The Compose profile uses the named `vegz_postgres_data` volume and initializes separate databases. It does not migrate legacy MySQL/SQLite records automatically. Keep existing data; never use `docker-compose down -v` when persistence matters.

## CI

The `dev` workflow tests Python syntax and API unit tests, checks frontend JavaScript, and builds/type-checks the Next.js web app.

## Production blockers

- Full cross-service shared order and customer record reconciliation.
- Fine-grained role authorization, MFA/password recovery, rate limits and security review.
- Migration-managed schemas, backup/restore drills, HTTPS, production secrets and monitoring.
- Payment gateway/refund/COD reconciliation, push notifications and deployment/DNS.
