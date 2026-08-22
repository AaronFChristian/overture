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

## Trace: overture.graph.builder.build_graph().ainvoke(...)

```
overture/graph/builder.py :: build_graph(provider, checkpointer=None)
  StateGraph(ExtractionState)
    .add_node("segment", segment)
    .add_node("extract_pains", make_signal_extractor(PAIN, ...))
    .add_node("extract_constraints", make_signal_extractor(CONSTRAINT, ...))
    .add_node("extract_requirements", make_signal_extractor(REQUIREMENT, ...))
    .add_node("extract_vocabulary", make_signal_extractor(VOCABULARY, ...))
    .add_node("classify_scope", make_classify_scope(provider))
    .add_node("assemble_brief", assemble_brief)
  .compile(checkpointer=checkpointer)   -- checkpointer=None in tests,
                                            AsyncPostgresSaver in
                                            production (not yet wired
                                            to a real entry point --
                                            see open threads below)

Execution, per .ainvoke({"session_id": ..., "transcript": ...}):

  START -> segment
    overture/graph/nodes.py :: segment(state)
      splits state["transcript"] on blank lines -> state["segments"]

  segment -> [extract_pains, extract_constraints,
              extract_requirements, extract_vocabulary]   (PARALLEL)
    each is the closure returned by make_signal_extractor():
      provider.complete(system=..., messages=[prompt], max_tokens=2048)
        -> overture/graph/llm_output.py :: parse_signals_response(raw_text)
             lenient on ```json fences, strict on item shape --
             invalid items dropped, not coerced
        -> for each ExtractedSignal:
             overture/graph/llm_output.py :: locate_span(transcript, quoted_text)
               returns None if quoted_text isn't a real substring
               -- signal DROPPED here if None (D-0005 enforced)
             else -> Requirement(..., scope=NEEDS_CLARIFICATION placeholder)
      returns {"signals": [...]}  -- four parallel writes, concatenated
                                      via the operator.add reducer in
                                      state.py, not overwritten

  [all four] -> classify_scope
    overture/graph/nodes.py :: make_classify_scope(provider) closure
      batches all of state["signals"] into one call
      response parsed; if len(labels) != len(signals), EVERY
        requirement in the batch falls back to NEEDS_CLARIFICATION
        (D-0012) -- no partial/best-effort index alignment
      returns {"scope_classified": [...]}

  classify_scope -> assemble_brief
    overture/graph/nodes.py :: assemble_brief(state)
      NO LLM CALL -- pure aggregation (D-0010)
      counts by category and by scope -> summary string
      returns {"brief": SolutionBrief(...)}

  assemble_brief -> END
```

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
| 3 | Full extraction graph: 5 node functions, prompts, span-location/parsing logic, graph builder, 4 end-to-end tests against a fake provider | Did not add an LLM call to `assemble_brief` even though a prose summary would look more polished — see D-0010. Did not attempt partial index alignment on a scope-classification length mismatch — see D-0012. Zero real LLM calls made or tested here; all graph logic verified against a FakeProvider, never api.anthropic.com. |

---

## Open threads for next session

- Migration proven against live Postgres (confirmed by Aaron, session
  2 close-out).
- The graph has no real entry point yet — nothing calls
  `build_graph()` with a real `AnthropicProvider` or wires an
  `AsyncPostgresSaver` checkpointer. That's the natural start of
  session 4: either a CLI command or a `POST /api/v1/sessions/{id}/extract`
  route, plus the first real (non-fake) run against the live Anthropic
  API with Aaron's key.
- No auth exists yet. `/health` is intentionally public; every other
  route added from session 4 onward needs an explicit auth decision
  logged before it ships.
- `db/session.py::get_db` exists but nothing depends on it yet —
  session 4's routes are the first real caller. Similarly, nothing
  persists a DiscoverySession, Requirement, or SolutionBrief to
  Postgres yet — the graph produces Pydantic objects in memory only;
  writing them to the db/models.py tables is session 4 work.
- `segment()` currently splits on blank lines only — no
  speaker-attribution awareness. Fine for the synthetic transcripts
  used in testing; real discovery-call transcripts (session 4's
  synthetic data batch) may need a better segmentation heuristic.
