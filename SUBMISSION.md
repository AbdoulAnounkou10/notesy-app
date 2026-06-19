# Submission

> Rename this file to `SUBMISSION.md` and fill it in. Keep it as long as it needs to be — no longer.

## What I changed and why

Before making any changes I read through the files in order of operational risk: settings (secrets, debug mode, database config),
requirements (dependency hygiene), 
CI (quality gates), 
views (application behavior). I skipped boilerplate files like urls.py, asgi.py, and wsgi.py they're rarely where inherited risk lives.

### App

**`settings.py`**

Four issues, all in the first 12 lines:

- `SECRET_KEY` was hardcoded in the repo. Moved to a required env var
  — the app now refuses to start without it
- `DEBUG = True` was hardcoded. Made it an env var defaulting to False
  so production is safe by default
- `ALLOWED_HOSTS = ["*"]` opens the door to host header injection.
  Locked to an env var
- File-based sessions don't survive in containers — two instances means
  users randomly lose their session. Switched to database-backed sessions

**`requirements.txt`**

- Pinned all packages. Unpinned deps mean different versions on every
  install — what works today breaks tomorrow
- `requests==2.20.0` is a 2018 release with known CVEs. Updated to current
- Added `dj-database-url` to support the DATABASE_URL pattern in settings

**`views.py`**

- Replaced every `print()` with proper `logger` calls. print() has no
  log level or timestamp and can't be alerted on
- Removed `time.sleep(8)` from the summarize view — it was blocking a
  gunicorn thread for 8 seconds per request, which starves other traffic
  with just 2 simultaneous requests
- Wrapped summarize in try/except with a graceful fallback instead of
  returning a 500

**`ci.yml`**

- Removed `|| true` from pytest — CI was always green even when every
  test failed. This is the most dangerous line in the repo
- Scoped triggers to main and PRs only, not every branch
- Added a real Postgres service container so tests run against the same
  database engine as production
- Added pip caching — shaves ~2 minutes off every run

---
-

### Docker

Tier 2 was about making the app runnable by anyone with just Docker installed. The Dockerfile uses a multi-stage build so the final image has no Node or build tools in it — just Python and the compiled assets. The entrypoint handles migrations automatically so there are no manual steps. The compose file wires up Postgres with a healthcheck so the app never starts before the database is ready. Anyone on the team can clone the repo, copy the env file, and be running in one command."
-
**Dockerfile**

Used a multi-stage build with two stages:

- **Stage 1 (Node)**: compiles the TypeScript bundle. This stage exists
  only to build the frontend assets — Node, npm, and all build tools
  are thrown away after and never end up in the final image
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
pointed at a broken schema, and fail in a much harder to debug way.

This means `docker compose up --build` is the only command a teammate
needs — no manual migration steps, no setup on their machine besides
Docker.

**docker-compose.yml**

Wires up two containers on the same network so Django can reach
Postgres:

- `db`: Postgres 16 with a named volume so data persists across
  container restarts
- `web`: the Django app with all required environment variables injected

The `depends_on` with `condition: service_healthy` is important — it
makes Docker wait until Postgres actually passes its healthcheck before
starting the app. Without this the app crashes on boot because it tries
to connect to a database that isn't ready yet.

**`.env.example`**

Documents every environment variable the app needs with placeholder
values. Safe to commit — no real secrets. Anyone cloning the repo runs
`cp .env.example .env`, fills in their values, and they're ready.

Also noticed the original `.gitignore` was missing `.env` — added it
so real credentials can't be accidentally committed to the repo.

### CI

-

## Tradeoffs

-

## What I'd do with another day

-

## How to run

```bash
# the command(s) a reviewer should run
```

## Deployment plan

> How would you take this from `docker compose up` on your laptop to a safe, production-ready deployment? You do not need to actually deploy it — we want your reasoning. Cover at least: where it runs, how secrets reach it, rollout + rollback, migrations, logs/metrics/alerts, and anything you'd want in place before a real user touched it.

-
