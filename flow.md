# Execution flow

Live map of how the code actually runs. Updated every session — this
file describes what IS, not what's planned (that's the build plan in
chat, not here). If this file and the code disagree, the code wins and
this file is stale until the next session's update.

---

## Entry points

| Entry point | What it is |
|---|---|
| `overture.main:app` | FastAPI ASGI app. Run with `uvicorn overture.main:app --reload`. |

No CLI entry point yet — added when the extraction graph lands
(session 3) so transcripts can be run through the pipeline without
going through HTTP.

---

## Trace: GET /health

```
overture/main.py
  app = FastAPI(...)
  app.include_router(health_router)      -- registers /health at import time

overture/api/health.py
  health()                               -- handler
    returns HealthResponse(status="ok", service="overture")
    no downstream calls -- see decisions.md D-0003
```

---

## Trace: LLM provider selection (not called by any route yet)

```
overture/providers/factory.py
  get_llm_provider(settings=None)
    settings = settings or get_settings()
    if settings.llm_provider == "anthropic":
        -> overture/providers/anthropic_provider.py :: AnthropicProvider(...)
    if settings.llm_provider == "azure_openai":
        -> overture/providers/azure_openai_provider.py :: AzureOpenAIProvider(...)

  Both implementations satisfy overture/providers/base.py :: LLMProvider
  (a Protocol) -- callers depend on that Protocol, never on the concrete
  class. See decisions.md D-0006.
```

No caller exists yet. Session 3's extraction graph nodes are the first
real consumers of `get_llm_provider().complete()`.

---

## Trace: Alembic migration (run manually, not part of app startup)

```
alembic upgrade head
  alembic/env.py
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    imports overture.db.models          -- populates Base.metadata
    run_migrations_online()             -- async, via run_sync bridge
      -> alembic/versions/0001_initial_schema.py :: upgrade()
           creates discovery_sessions, requirements, solution_briefs,
           demo_configs, in that order (FK dependency order)
```

Verified in this environment via `alembic upgrade head --sql`
(offline SQL generation, no live DB required) — confirms the migration
and env.py are structurally correct. NOT yet verified against a live
Postgres instance; that happens on Aaron's machine and gets logged
once confirmed.

---

## Config resolution order

```
overture/config.py
  get_settings()                          -- lru_cache, called once per process
    Settings()                            -- pydantic-settings
      reads .env if present
      falls back to field defaults
      validates types -- raises at import time if a required field
                          is missing or malformed, not at first use
```

Anything needing config imports `get_settings()` — nothing reads
`os.environ` directly anywhere in `src/`.

---

## AI surface by phase

What the AI (me, in this project) was allowed to write or decide, per
session. This is the running answer to "how much of this did you
actually design vs generate."

| Session | AI wrote | AI did not decide |
|---|---|---|
| 1 | Full scaffold: config, health endpoint, Docker Compose, CI, Makefile, this file and decisions.md | Nothing yet gated — no validator exists until session 5. All output reviewed and verified green by Aaron before commit. |
| 2 | Pydantic schemas, SQLAlchemy models, Alembic migration, provider abstraction (both implementations) | Did not decide to make `source_span` optional even though it would have made the schema "easier" to satisfy in early testing — see D-0005. Migration SQL verified offline only; live-DB proof is Aaron's step, not mine. |

---

## Open threads for next session

- Migration not yet proven against live Postgres — first thing to
  verify in session 3, before writing any new model changes on top of
  an unconfirmed schema.
- No auth exists yet. `/health` is intentionally public; every other
  route added from session 3 onward needs an explicit auth decision
  logged before it ships.
- `db/session.py::get_db` exists but nothing depends on it yet —
  session 3's routes are the first real caller.
- No caller of `get_llm_provider()` yet — session 3's extraction graph
  nodes are first.
