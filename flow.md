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

## Trace: overture extract <transcript.txt> (CLI entry point)

```
$ uv run overture extract data/sample_transcripts/manufacturing_vendor_contracts.txt

overture/cli.py :: main()
  argparse dispatches to run_extract(Path(...))

overture/cli.py :: run_extract(transcript_path)
  transcript = transcript_path.read_text()
  session_id = uuid.uuid4()

  overture/providers/factory.py :: get_llm_provider(settings)
    -> real AnthropicProvider (or AzureOpenAIProvider), per
       settings.llm_provider -- FIRST REAL PROVIDER INSTANCE in the
       codebase; every prior test used a FakeProvider

  overture/graph/builder.py :: build_graph(provider)
    -> compiled graph, checkpointer=None (still no Postgres
       checkpointer wired -- see open threads)

  graph.ainvoke({"session_id": ..., "transcript": ...})
    -> full trace already documented above -- unchanged, just now
       running against real Claude output instead of a fixture

  prints brief.summary and every Requirement with its source quote
    directly to stdout -- this is the point where a bad real-world
    extraction becomes visible immediately, before anything is saved

  overture/db/session.py :: get_sessionmaker()
    -> FIRST REAL CALLER of this function; sessions 1-3 built it but
       nothing used it

  overture/db/repository.py :: persist_extraction_result(db, session, brief)
    db.add(DiscoverySession ORM row)
    db.add(Requirement ORM row) -- once per brief.requirements item
    db.add(SolutionBrief ORM row)
    -- does NOT commit; cli.py commits once after this returns, so a
       failure mid-persist leaves nothing partially written

  overture/poc/compiler.py :: select_blueprint(brief)
    PURE, DETERMINISTIC, NO LLM CALL -- scores brief's in-scope
    requirement text against each Blueprint's capability_tags,
    returns the highest-scoring one (D-0017)

  overture/poc/compiler.py :: fill_config(brief, blueprint, provider)
    provider.complete(...) -- ONE LLM call, writes system_prompt and
      sample_questions content only; blueprint_id and tools come from
      the Blueprint object selected above, never from this call
    -> DemoConfig(status=DRAFT)

  overture/poc/validator.py :: validate_config(demo_config)
    NO LLM CALL ANYWHERE IN THIS MODULE (D-0018, enforced by a test
    that greps the module's own source)
    checks: blueprint_id known, every tool in TOOL_ALLOWLIST,
      token_budget in range, system_prompt non-empty,
      >=1 sample question
    -> DemoConfig(status=VALIDATED, validation_errors=[])  on pass
    -> DemoConfig(status=REJECTED, validation_errors=[...])  on fail
       (every failure reported, not just the first)

  prints brief.summary and every Requirement with its source quote,
    then the selected blueprint and the validated (or rejected)
    DemoConfig's system prompt and sample questions -- all before
    anything is saved

  overture/db/session.py :: get_sessionmaker()
    -> FIRST REAL CALLER of this function; sessions 1-3 built it but
       nothing used it

  overture/db/repository.py :: persist_demo_config(db, demo_config)
    db.add(DemoConfig ORM row) -- staged in the SAME transaction as
      persist_extraction_result above, so a session's requirements
      and its demo config either both land or neither does

  db.commit()   -- FIRST REAL WRITE to Postgres from application code
                    (the Alembic migration created the tables; this is
                    the first row ever written to them by the app)
```

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
| 4 | Persistence layer (pure mapping function + async writer), CLI entry point, 3 synthetic transcripts, 2 tests for the pure mapping function | Did not write a test claiming to prove `persist_extraction_result` works against real Postgres — it can't be, from this environment. Did not wire an `AsyncPostgresSaver` checkpointer — deferred, see open threads. Zero real Claude calls made from this environment; the CLI is verified structurally (help text, argument validation, missing-file handling) but not against api.anthropic.com — that first real call is Aaron's step. A real bug was found on Aaron's first live run (D-0014, missing code-fence stripping in classify_scope) and fixed with a proven regression test, plus a second real gap (D-0015, stale `.env` DATABASE_URL) that was a process issue, not code — both closed out by session's end. |
| 5 | Blueprint catalog (3 fixed blueprints), deterministic scoring (`select_blueprint`), LLM-assisted slot filling (`fill_config`), the LLM-free config validator (`validate_config`), persistence for DemoConfig, CLI wiring, 18 new tests | Did not let the LLM choose which blueprint to use, or which tools attach to one — see D-0017. Did not put validation logic inside `fill_config` even though it would have been fewer files — see D-0018. Wrote a test that greps `validator.py`'s own source to prove it never imports a provider, rather than trusting a comment to stay true. `fill_config`'s real-API behavior is untested here — same gap as sessions 1-4's first LLM-touching code, closed by Aaron's next live run. |

---

## Open threads for next session

- `fill_config` and the validator have never run against real Claude
  output — same verification gap every new LLM-touching module in
  this project has had at the point it's handed off. Aaron's next
  `overture extract` run is what closes it, the same way session 4's
  did for extraction and scope classification.
- `persist_demo_config` has never run against a live database in this
  environment — same gap as `persist_extraction_result` before it,
  closed the same way (Aaron's terminal, not mine).
- No `AsyncPostgresSaver` checkpointer wired into `build_graph()` yet
  — `cli.py` still calls it with `checkpointer=None`, so a failure
  mid-extraction can't currently be resumed, it just fails and the
  whole transcript needs re-running.
- No auth exists yet. `/health` is intentionally public; the CLI has
  no auth model at all (it's local-only, reads Aaron's own `.env`).
  The first HTTP route (session 6) needs an explicit auth decision
  logged before it ships.
- `segment()` currently splits on blank lines only — no
  speaker-attribution awareness. Fine for the synthetic transcripts
  used in testing; real discovery-call transcripts (session 4's
  synthetic data batch) may need a better segmentation heuristic.
