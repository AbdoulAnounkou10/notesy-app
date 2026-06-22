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

#### CI/CD

The existing CI had one critical flaw — `pytest || true` meant the
pipeline always showed green even when every test failed. That single
change made the entire CI meaningless. Beyond that it had no database,
no image build, and triggered on every branch indiscriminately.

Here's how it works now:

**On every pull request targeting main**, the test job runs:
- Installs dependencies with pip caching so repeat runs are fast
- Spins up a real Postgres 16 service container — same database engine
  as production, not SQLite
- Runs pytest with the correct environment variables
- Builds the TypeScript bundle to catch frontend errors early

If any of those fail the PR is blocked. Nothing merges in a broken state.

**On merge to main**, a second job runs automatically:
- Tests run again to confirm the merged code is clean
- Docker image is built and pushed to GHCR with two tags:
  - `sha-{commit}` — tied to the exact commit for deterministic rollbacks
  - `latest` — always points to the most recent build
- The build job can never run unless tests pass first via `needs: test`
- Docker layer caching via GitHub Actions means repeat builds are fast

**Rolling back** means redeploying the previous task definition pointing
at the prior SHA tag. Because every image maps to an exact commit you
always know what's running in production.

---

## Tradeoffs

No nginx in the compose stack — it adds complexity for local dev
without much benefit. In production TLS termination and static file
serving would live at the load balancer, not in the app.

Database sessions instead of Redis — Redis is the right answer at
scale but adds a third service to the local setup. Straightforward
to swap in when traffic demands it.

`SECURE_SSL_REDIRECT` removed from Django settings entirely — it
belongs at the infrastructure level where a real certificate exists.
Having it in the app caused Chrome to cache an HTTPS redirect for
localhost, which broke local testing and required a full cache clear
to fix. The load balancer enforces HTTPS before traffic ever reaches
the container.

Worker count is set to 2 workers and 4 threads — a conservative
default that needs tuning against real traffic with load testing.

---

## What I'd do with another day

- `pip-compile` to generate a full transitive dependency lockfile —
  right now only direct dependencies are pinned
- Smoke test in CI: pull the built image and run
  `manage.py check --deploy` to catch misconfiguration before it ships
- Pre-commit hooks so lint failures never reach CI in the first place
- Sentry for the summarize endpoint — it calls a real external service
  and is the most likely source of silent production failures
- Dependabot for automated dependency and CVE updates
- Staging environment that auto-deploys on every main merge, with
  production deploys gated on tagged releases only

---
## How to run

```bash
git clone https://github.com/AbdoulAnounkou10/notesy-app.git
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

Note: developed on macOS 26.3 beta which has a known Docker Desktop
networking quirk — Chrome cached an HTTPS redirect from an earlier
security setting and blocked localhost. Fixed by clearing the browser
cache. The app itself runs correctly and curl confirmed it was
responding the whole time. Won't affect anyone on stable macOS.

---

## Deployment plan

**Where it runs**

ECS Fargate on AWS, us-east-1. Fargate means no servers to manage or
patch — you define the task, AWS runs it. RDS Postgres with Multi-AZ
enabled so there's an automatic failover replica in a second
availability zone. A second region for disaster recovery only makes
sense once there's a real business requirement — not day one complexity.

**How secrets reach the container**

AWS Secrets Manager. Each secret is stored there and referenced by ARN
in the ECS task definition — AWS injects them as environment variables
at startup. Nothing sensitive lives in the image, in the repo, or
visible in plaintext in the AWS console. Automatic 90-day rotation via
Lambda from day one — not something to retrofit later.

**Rollout and rollback**

Blue/green deployments via ECS service updates. New tasks spin up and
must pass health checks before old ones drain traffic. If health checks
fail the rollout stops automatically — old tasks keep running. Rolling
back is straightforward: redeploy the previous task definition, which
points at the prior SHA-tagged image on GHCR. The whole thing takes
under two minutes.

**Migrations**

Run as a one-off ECS task before updating the service — schema changes
land before any new app code starts serving traffic. For migrations
that can't be rolled back, like dropping a column, use the
expand-contract pattern: add the new column and deploy code that writes
to both, then drop the old column in a follow-up release once you're
sure rollback is off the table.

**Observability**

Logs go to CloudWatch Logs via the awslogs driver. Because the app now
uses structured JSON logging, log entries are filterable by field —
finding all failed logins for a user is a query, not a grep.

Alerts via CloudWatch Alarms to SNS to PagerDuty. The three alerts I'd
set up on day one: 5xx error rate above 1%, p99 latency above 2
seconds, and ECS task restart loops. The summarize endpoint is the
highest-risk one — once it's calling a real LLM service I'd add a
specific latency alert for it.

AWS X-Ray for request tracing once we need to diagnose slow requests.

**Before a real user touches it**

Load test with Locust to confirm the gunicorn worker count holds under
expected traffic — 2 workers and 4 threads is a starting point, not a
final answer.

Actually restore an RDS snapshot to a test cluster and verify the app
comes up against it. A backup you've never restored is not a backup.

Runbooks written and linked from the team wiki for the two most likely
incidents: database is down, and app is returning 500s. On-call
rotation defined before launch — not after the first 3am incident.