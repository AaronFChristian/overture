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

---

## Open threads for next session

- DB layer (SQLAlchemy models, Alembic) — session 2.
- No auth exists yet. `/health` is intentionally public; every other
  route added from session 2 onward needs an explicit auth decision
  logged before it ships.
