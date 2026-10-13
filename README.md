# Vegz Admin

Central operations console for the Vegz ecosystem. The portal includes a responsive web UI and FastAPI management API for platform records, partner onboarding, order oversight, dispatch assignment, settings and audit history.

## Features in this initial implementation

- Admin email/password sign-in with PBKDF2-HMAC-SHA256 password hashing, expiring JWT access tokens and account active-state checks.
- Super-admin bootstrap from deployment environment; there is no public administrator registration.
- Dashboard with daily order/gross-sales metrics, active orders, pending shop/agent counts and recent audit activity.
- Shop onboarding and approval/rejection/suspension; non-approved shops are automatically marked closed and paused.
- Agent onboarding, approval/suspension, vehicle records and operational availability.
- Product moderation records with pending/approved/blocked status.
- Order oversight with valid status transitions, approved-agent assignment, customer/shop/agent associations and duplicate-code rejection.
- Customer records and account status.
- Configurable platform settings such as delivery fee, free delivery threshold, commission, maintenance mode, support email and maximum order value.
- Audit trail for important admin changes.
- Admin account creation and activation controls restricted to the super-admin role.
- SQLite development database, SQLAlchemy ORM, Dockerfile, Compose and GitHub Actions checks.

## Run locally

Requires Python 3.11+.

```bash
git clone https://github.com/Manojhole/vegz-admin.git
cd vegz-admin
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
cp backend/.env.example .env
uvicorn backend.app.main:app --reload --port 8000
```

Open the admin console at http://localhost:8000 and the API documentation at http://localhost:8000/docs.

Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD in .env before starting the app. The bootstrap password must be at least 14 characters. On first start, the service creates a super-admin account if that email does not already exist. Login uses those credentials. Do not commit .env or use example credentials on a hosted environment.

## Docker

```bash
docker compose up --build
```

Compose requires explicit JWT_SECRET, BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD values in your shell or .env file. Copy backend/.env.example to .env and replace the example values before starting it; the bootstrap password must be at least 14 characters. The container persists its SQLite file in a Docker volume.

## Environment

Important variables:

- APP_ENV: development or production.
- DATABASE_URL: SQLite for local setup; use a managed PostgreSQL/MySQL service with TLS, backups and connection limits for production.
- JWT_SECRET: unique cryptographically random secret, at least 32 characters, configured separately for each environment.
- ADMIN_TOKEN_TTL_MINUTES: token lifetime.
- BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD, BOOTSTRAP_ADMIN_NAME: initial super-admin creation.
- CORS_ORIGINS: exact allowed web origins.

The service raises an error in production mode if JWT_SECRET is missing, too short, or left at its local placeholder.

## API summary

All routes except health and login require an Authorization: Bearer access token.

| Area | Endpoints |
|---|---|
| Auth | POST /api/auth/login; GET /api/auth/me |
| Dashboard | GET /api/dashboard |
| Shops | GET/POST /api/shops; PATCH /api/shops/{id} |
| Agents | GET/POST /api/agents; PATCH /api/agents/{id} |
| Products | GET/POST /api/products; PATCH /api/products/{id} |
| Orders | GET/POST /api/orders; PATCH /api/orders/{id}; PATCH /api/orders/{id}/status; POST /api/orders/{id}/assign |
| Customers | GET/POST /api/customers; PATCH /api/customers/{id} |
| Settings | GET /api/settings; PATCH /api/settings/{key} |
| Audit | GET /api/audit |
| Admin access | GET/POST /api/admin-users; PATCH /api/admin-users/{id}/active (super-admin only) |
| Demo | POST /api/dev/seed (super-admin only) |

## Critical production integration boundary

**This repository is not yet the live control plane for the other Vegz apps.** The current vegz-user, vegz-shop and vegz-agent projects have independently developed data models and local databases. The data maintained here is kept in admin-service tables (prefixed managed_) so this console can be built and tested without mutating production systems accidentally.

Before launch, define an authoritative shared platform API/data model and integrate each app with it. Partner/product/order actions here currently affect records stored in this service only; they do not automatically approve real users in the shop app, change the customer app catalog, dispatch actual agent jobs, or perform payment refunds. Avoid directly pointing these different applications at the same DB without reviewed migrations and ownership constraints.

## Security and operations work still required before real production

This is an initial operations-console foundation, not a security-reviewed production release. Before managing real customer data:

1. Add login throttling, account lockout, password reset, MFA/passkeys, short-lived token rotation/revocation and security-event logging.
2. Enforce fine-grained permissions per endpoint; only admin-user endpoints are currently super-admin restricted.
3. Use migration-managed schemas (e.g. Alembic), a managed production database, backups, restore drills, retention policy and concurrency tests. Tables currently initialize with create_all for a new environment.
4. Add strict field validation and permission checks for all state transitions, pagination, redaction of customer PII and IP/user-agent audit context.
5. Integrate live shop, agent, customer and order services with authenticated service-to-service APIs or an event bus, using idempotency, retries and an authoritative order state.
6. Wire maintenance settings, delivery fee, commission and price/catalog controls into the customer/shop APIs before exposing those settings to operations staff.
7. Implement actual payment-gateway refund workflows, COD reconciliation, notification delivery and operational alerting.
8. Configure HTTPS, secrets manager, restricted production CORS, monitoring, error reporting and production deployment pipeline.
9. Add CSRF protection if cookie-based sessions are adopted, plus dependency/security scanning and end-to-end tests.
10. Conduct a privacy and security review before exposing customer addresses, phone numbers and financial information.

## Repository structure

```
backend/app/main.py      FastAPI endpoints, models and access controls
backend/tests/test_api.py API authorization and workflow tests
frontend/index.html      Responsive operations console
frontend/styles.css      UI styling
frontend/app.js          API-backed views and admin actions
Dockerfile
docker-compose.yml
.github/workflows/ci.yml
```
