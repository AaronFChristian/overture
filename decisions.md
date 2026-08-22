# Decisions log

One entry per meaningful choice. Newest at the bottom. Nothing gets
edited after the fact — if a decision is reversed, a new entry
supersedes it and links back.

---

## D-0001 — uv over pip/poetry for dependency management

Date: 2026-08-21 · Session 1 · Status: accepted

Context:  Needed a Python package/env manager for a project that will
          later run in CI, in Docker, and on Azure Container Apps.
Decision: Use uv for venv creation, dependency resolution, and running
          commands (`uv run pytest`, etc).
Why:      Single tool for venv + install + lockfile, notably faster
          resolution than pip, and has first-class GitHub Actions
          support (astral-sh/setup-uv) so local and CI environments
          are guaranteed identical. Already the standard in prior
          projects.
Rejected: Poetry (heavier, slower resolver, no real speed advantage
          for a project this size). Bare pip + requirements.txt (no
          lockfile discipline).
Revisit:  Not expected to change.

---

## D-0002 — pydantic-settings as the single config source

Date: 2026-08-21 · Session 1 · Status: accepted

Context:  Every component (DB, LLM provider, later Azure services)
          needs config values from environment variables.
Decision: One `Settings` class in `config.py`, read via a cached
          `get_settings()`. Nothing else calls `os.environ` directly.
Why:      Validates types and required fields at process startup, not
          three requests in. A missing DATABASE_URL fails loudly on
          boot instead of surfacing as a confusing runtime error later.
          Also gives autocomplete/type-checking on every setting.
Rejected: Bare `os.environ.get()` scattered through the codebase —
          this is exactly the anti-pattern that caused the
          "load_dotenv() must be explicitly called" bug class in
          prior projects; centralizing removes the whole failure mode.
Revisit:  When Azure Key Vault integration lands, Settings gains a
          secrets-provider layer — same class, new source.

---

## D-0003 — health endpoint has no DB dependency yet

Date: 2026-08-21 · Session 1 · Status: accepted

Context:  First route in the app; database layer doesn't exist until
          session 2.
Decision: `/health` returns a static 200 with no downstream check.
Why:      Once Postgres is wired in, this will split into liveness
          (process is up) vs readiness (process can reach the DB) —
          conflating them means a container orchestrator restarts a
          perfectly healthy process just because Postgres had a
          momentary blip. Keeping /health dumb now avoids having to
          unwind that conflation later.
Rejected: Adding a DB ping now — premature, and there's no DB
          connection code to ping yet.
Revisit:  Session 2, when the DB layer lands. Split into /health/live
          and /health/ready at that point.

---

## D-0004 — pgvector/pgvector Docker image over vanilla postgres + manual extension install

Date: 2026-08-21 · Session 1 · Status: accepted

Context:  Local dev needs Postgres with the pgvector extension
          available for later embedding storage (session 6).
Decision: Use `pgvector/pgvector:pg16` as the Compose image.
Why:      Ships the extension pre-built; `CREATE EXTENSION vector`
          just works. Avoids a manual apt-get/compile step inside a
          vanilla postgres image, which is a common source of
          "works on my machine" drift.
Rejected: `postgres:16` + manual extension build in a custom
          Dockerfile — more moving parts for no benefit at this stage.
Revisit:  Not expected to change through local dev. Azure Postgres
          Flexible Server also supports pgvector natively, so this
          carries forward to session 7 without a swap.
