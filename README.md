# Notesy — DevOps Challenge

Welcome, and thanks for taking the time. Notesy is a small Django + HTMX notes app. It runs locally. **Your job is to make it production-ready.**

This is a real-shaped exercise: the app is the kind of thing a small team would hand you on day one, with all of the rough edges that implies.

---

## Time budget

We're aiming for **~3 hours of focused work**, followed by a **1-hour live walkthrough** with two engineers.

If you find yourself going significantly past 3 hours, stop and write down what you *would* have done in `SUBMISSION.md` — we explicitly value good prioritization over completeness.

## How to submit

1. Fork this repo.
2. Do the work in your fork on a branch.
3. Open a pull request **against your own fork's `main`** so we can see the diff cleanly.
4. Reply to our email with the PR link.

We will read the PR and run your stack locally (and in GitHub Actions on your fork) before the walkthrough.

---

## What you're getting

A working app, with the kind of issues you'd inherit on a real team:

```
.
├── manage.py
├── notesy/                  # Django project (settings, urls, wsgi/asgi)
├── apps/notes/              # the actual app — models, views, templates
│   └── static_src/          # TypeScript source for the small client bundle
├── package.json             # esbuild + tsc toolchain
├── requirements.txt
├── pytest.ini
├── .github/workflows/ci.yml # the existing CI workflow (such as it is)
└── README.md                # you are here
```

## What it does

- Log in (session auth)
- List, create, edit, delete personal notes (HTMX-driven, no full page reloads)
- "Summarize" a note (calls out to an LLM-shaped service — currently stubbed)

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm install
npm run build                        # compiles the TS bundle to static/js/
python manage.py migrate
python manage.py seed                # creates a demo user (demo/demo) + sample notes
python manage.py runserver
```

Then visit http://localhost:8000 and log in as `demo` / `demo`.

---

## Your deliverables

Three tiers, in order. Treat them as a priority queue — get tier 1 solid before climbing.

### Tier 1 — Make the app safe to run

Read through the code as if you've just inherited this. Make the changes you'd want before letting this anywhere near a real environment. We're looking for the kind of fixes that come from production experience, not a checklist.

### Tier 2 — Containerize it

Add the Docker pieces so a teammate can clone, run one command, and have the whole stack up. Postgres should be involved. Anyone running it should not have to set anything up on their host besides Docker.

### Tier 3 — Wire up CI/CD

There's a `.github/workflows/ci.yml` in the repo. It's a starting point, and not a good one. Make it a workflow you'd be willing to merge to `main` behind. We expect the image you build to be pushed to GitHub Container Registry (`ghcr.io`) on merge to `main`, tagged in a way that lets us roll back.

---

## Your `SUBMISSION.md`

Please add a `SUBMISSION.md` at the repo root with:

1. **What you changed and why** — one section per area (app / Docker / CI). Brief is fine.
2. **Tradeoffs you made** — anywhere you chose one option over another, what was the alternative?
3. **What you'd do with another day** — anything you saw and consciously chose not to fix.
4. **How to run your version** — if your `docker compose up` command isn't enough, document it.

We pay more attention to `SUBMISSION.md` than to almost anything else. A small change with great reasoning beats a big change with no narrative.

---

## What we'll cover in the walkthrough

- You demo the stack running and walk us through the architecture
- We dig into 2-3 of your specific choices
- We throw a curveball or two (something breaks, something gets slow — diagnose live)
- We talk about what you'd do next with more time

There is no trick. We are looking for: production sense, calibration ("what matters now vs. later"), and the ability to explain your thinking.

---

## Constraints & rules

- **You can use any tools you like**, including LLMs. We assume you do — we do too. But you own every line you submit. In the walkthrough we will ask you to explain things.
- **Don't rewrite the app code**. Fix what's broken from an ops perspective. You can edit application code where it's necessary to fix a real operational issue (e.g. logging, config), but resist refactoring for taste.
- **Public infrastructure only**. Don't sign up for paid services on our behalf. GHCR via your own GitHub account is fine. AWS / GCP / Datadog accounts are not.
- **No git history rewrites** to hide work. We'd rather see honest commits than a polished single squash.

---

## Questions

If something is genuinely ambiguous or broken in a way that blocks you, email us. We'd rather unblock you than have you spin. If something seems wrong but you can work around it, log it in `SUBMISSION.md` and keep going — that's part of the signal.

Good luck. We're looking forward to talking through it.
