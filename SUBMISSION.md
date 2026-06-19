# SUBMISSION.md

## What I changed and why

Before making any changes I read through the files in order of
operational risk: settings (secrets, debug mode, database config),
requirements (dependency hygiene), CI (quality gates), then views
(application behavior). I skipped boilerplate files like urls.py,
asgi.py, and wsgi.py — they're rarely where inherited risk lives.

### App

**`settings.py`**

Four issues, all in the first 12 lines:

- `SECRET_KEY` was hardcoded in the repo with a comment saying "replace
  me eventually." Moved to a required env var — the app now refuses to
  start without it
- `DEBUG = True` was hardcoded. Made it an env var defaulting to False
  so production is safe by default
- `ALLOWED_HOSTS = ["*"]` opens the door to host header injection.
  Locked to an env var
- File-based sessions don't survive in containers — two instances means
  users randomly lose their session depending on which container handles
  their request. Switched to database-backed sessions
- Removed `SECURE_SSL_REDIRECT` from app settings — this belongs at the
  load balancer level, not in Django. Having it in the app breaks local
  Docker testing where there's no TLS termination

**`requirements.txt`**

- Pinned all packages. Unpinned deps mean different versions on every
  install — what works today breaks tomorrow
- `requests==2.20.0` is a 2018 release with known CVEs. Updated to
  current
- Added `dj-database-url` to support the DATABASE_URL pattern in
  settings

**`views.py`**

- Replaced every `print()` with proper `logger` calls. print() has no
  log level, no timestamp, and can't be filtered or alerted on
- Failed logins use `logger.warning()` specifically — repeated failures
  are a security signal worth alerting on
- Removed `time.sleep(8)` from the summarize view — it was blocking a
  gunicorn thread for 8 seconds per request, which starves all other
  traffic with just 2 simultaneous requests
- Wrapped summarize in try/except with `logger.exception()` for full
  stack traces and a graceful fallback instead of a 500

**`ci.yml`**

- Removed `|| true` from pytest — CI was always green even when every
  test failed. This is the most dangerous line in the repo
- Scoped triggers to main and PRs only, not every branch
- Added a real Postgres service container so tests run against the same
  database engine as production
- Added pip caching — shaves ~2 minutes off every run
- Added TypeScript build step to catch frontend compilation errors in CI

**`.gitignore`**

- The original was missing `.env`. Added it — the repo had `.env`
  committed with real credentials including a SUMMARIZER_API_KEY. This
  also revealed the summarize view calls a real external service, making
  the error handling fix even more important

---

### Docker

**Dockerfile**

Multi-stage build with two stages:

- **Stage 1 (Node)**: compiles the TypeScript bundle. Node, npm, and
  all build tools are thrown away after — they never end up in the
  final image
- **Stage 2 (Python)**: runs the actual app. Lean, no build tools,
  smaller attack surface

The app runs as a non-root user (uid 1001). If the container process
is ever compromised, the attacker only gets that user's permissions —
not root access to the container.

**entrypoint.sh**

Runs three things in order every time the container starts:
1. `migrate` — brings the database schema up to date
2. `collectstatic` — prepares static files
3. `gunicorn` — starts the app server

`set -e` at the top means if migrations fail the script stops
immediately. Without it the container would start gunicorn anyway,
pointed at a broken schema.

**docker-compose.yml**

Wires up two containers on the same network so Django can reach
Postgres:

- `db`: Postgres 16 with a named volume so data persists across
  container restarts
- `web`: the Django app with all required environment variables injected

`depends_on` with `condition: service_healthy` makes Docker wait until
Postgres passes its healthcheck before starting the app. Without this
the app crashes on boot trying to connect too early.

**`.env.example`**

Documents every environment variable the app needs with placeholder
values. Safe to commit — no real secrets. Anyone cloning the repo runs
`cp .env.example .env`, fills in their values, and they're ready.

---

### CI/CD

- Test job runs against a real Postgres service container — same
  database engine as production
- `build-and-push` is gated on tests passing via `needs: test` — a
  broken image can never be pushed
- Images only push on merges to main, not on PRs — PRs validate, they
  don't ship
- Every image tagged with commit SHA (`sha-abc1234`) for deterministic
  rollbacks, plus `latest` for convenience
- Docker layer caching via GitHub Actions cache — fast on repeat builds

---

## Tradeoffs

- **No nginx in compose**: adds complexity for local dev. In production
  TLS termination and static file serving would be handled by a load
  balancer or nginx sidecar
- **Database sessions over Redis**: Redis is the right long-term answer
  at scale but adds a third service. Noted for when traffic demands it
- **SECURE_SSL_REDIRECT removed from app**: moved to infrastructure
  level where it belongs. The load balancer enforces HTTPS before
  traffic reaches the container
- **Worker count (2 workers, 4 threads)**: conservative default — needs
  tuning against real traffic with load testing

---

## What I'd do with another day

- `pip-compile` for a full transitive dependency lockfile
- Smoke test in CI: pull the built image and run
  `manage.py check --deploy` to catch misconfiguration before it ships
- Pre-commit hooks so lint failures don't reach CI
- Sentry for error tracking — the summarize endpoint calls a real
  external service and is the most likely source of silent failures
- Dependabot for automated dependency and CVE updates
- Staging environment that deploys on every main merge, production only
  on tagged releases

---

## How to run

```bash
git clone https://github.com/YOUR_USERNAME/notesy-app.git
cd notesy-app
cp .env.example .env
# Fill in DJANGO_SECRET_KEY and POSTGRES_PASSWORD in .env
docker compose up --build
```

Then create the demo user:
```bash
docker compose exec web python manage.py seed
```

Visit http://localhost:8000 and log in as `demo / demo`.

Note: tested on macOS 26.3 beta. Docker Desktop has a known port
forwarding issue on this OS version — the app builds and runs correctly
(confirmed via curl returning HTTP 200) but the browser cannot reach it
due to a Mac networking restriction specific to this beta. This does
not affect the Docker setup itself and will work on stable macOS.

---

## Deployment plan

**Where it runs**

ECS Fargate on AWS, us-east-1. Fargate removes server management —
no patching EC2 instances. RDS Postgres Multi-AZ for automatic failover.
A second region (us-west-2) for disaster recovery once there's a
business requirement for it — not day one.

**How secrets reach the container**

AWS Secrets Manager. Secrets are referenced by ARN in the ECS task
definition and injected as environment variables at task startup.
Nothing sensitive is in the image or in plaintext in the console.
90-day automatic rotation via Lambda from day one.

**Rollout and rollback**

Blue/green via ECS service updates. New tasks must pass health checks
before old ones drain. If health checks fail the rollout stops
automatically. Rollback means redeploying the previous task definition,
which references the previous SHA-tagged image — under two minutes.

**Migrations**

Run as a one-off ECS task before the service update so schema changes
land before new app code starts serving traffic. For irreversible
migrations (dropping a column): expand-contract — ship the new column,
migrate data, drop the old column in a follow-up release once rollback
is off the table.

**Observability**

- Logs → CloudWatch Logs. Structured JSON means filterable by field
- Alerts → CloudWatch Alarms → SNS → PagerDuty on: 5xx rate >1%,
  p99 latency >2s, task restart loops
- Tracing → AWS X-Ray for slow request investigation, especially the
  summarize endpoint once it hits a real LLM service

**Before a real user touches it**

- Load test to validate worker count holds under expected traffic
- Actually restore an RDS snapshot — a backup never restored is not
  a backup
- Runbooks written for "DB is down" and "app is returning 500s"
- On-call rotation defined before launch, not after the first incident