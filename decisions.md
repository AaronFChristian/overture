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

---

## D-0005 — Requirement.source_span is required, not optional

Date: 2026-08-22 · Session 2 · Status: accepted

Context:  The extraction graph (session 3) pulls pains, constraints,
          and requirements out of unstructured transcripts. A
          hallucinated requirement — one the model invented rather
          than found in the transcript — is the single most damaging
          failure mode for this project, since Overture's whole pitch
          is "traceable to what the prospect actually said."
Decision: `source_span: SourceSpan` on the Requirement schema has no
          default and is not `| None`. Pydantic rejects construction
          without it.
Why:      Enforcing this at the type level means the extraction graph
          physically cannot produce a Requirement without a span — a
          node that tries just gets a ValidationError, not a
          requirement that silently ships without provenance. A
          runtime check ("if not span: drop it") is the same rule
          enforced by convention instead of by the type checker, and
          conventions get skipped under deadline pressure.
Rejected: `source_span: SourceSpan | None = None` with a downstream
          filter step — tested this mentally and rejected it: it
          means bad data can exist as a valid Requirement object for
          however long it takes to reach the filter, which is exactly
          the gap a bug hides in.
Revisit:  Not expected to change. If a future requirement type
          genuinely has no single traceable span (e.g. an inferred
          requirement synthesized from multiple pains), that needs a
          new schema, not a loosened constraint on this one.

---

## D-0006 — Claude primary, Azure OpenAI swappable, behind one Protocol

Date: 2026-08-22 · Session 2 · Status: accepted

Context:  The report calls for Azure OpenAI Service as the deployment
          target. Aaron already has working Claude API access and
          usage patterns from prior projects.
Decision: `LLMProvider` is a `typing.Protocol` with one method,
          `complete()`. `AnthropicProvider` and `AzureOpenAIProvider`
          both implement it. `get_llm_provider()` reads
          `settings.llm_provider` and constructs the right one.
          Nothing outside `providers/` imports `anthropic` or `openai`
          directly.
Why:      Two concrete reasons, not just "abstraction is good
          practice." First, cost: local dev (sessions 1-6) runs
          entirely on Claude, so Azure OpenAI — which has no free
          tier at all — never gets touched until session 7-8, and
          even then only enough to prove the abstraction works.
          Second, positioning: a pluggable provider layer is itself
          evidence for the "designs for portability" argument this
          whole project exists to make, and it means the same
          codebase demos honestly to Microsoft (Azure OpenAI path)
          and to Anthropic/OpenAI (Claude path) without a rewrite.
Rejected: Azure-OpenAI-only — faster to build, but ties the whole
          project's LLM cost to a service with a meter running from
          the first token, and undercuts the FDE-facing pitch.
Revisit:  If a third provider is ever needed (e.g. for Crucible's
          multi-vendor comparison), it implements the same Protocol —
          no changes needed to this decision.

---

## D-0007 — Pydantic schemas and SQLAlchemy models share names, different modules

Date: 2026-08-22 · Session 2 · Status: accepted

Context:  Both the API-facing domain types (schemas.py) and the
          database tables (db/models.py) represent the same four
          concepts: DiscoverySession, Requirement, SolutionBrief,
          DemoConfig.
Decision: Same class names in both files. Callers import with a
          module prefix (`from overture.db import models` then
          `models.Requirement`) or an alias, never a bare
          `from overture.db.models import Requirement` alongside a
          bare `from overture.schemas import Requirement` in the same
          file.
Why:      The 1:1 correspondence between "what the API returns" and
          "what's in the database" is the whole point — matching
          names make that correspondence visible at a glance instead
          of requiring a mental lookup table (RequirementSchema maps
          to RequirementORM maps to... ). The cost is import
          discipline, which ruff's import-sorting already partially
          enforces.
Rejected: Suffixing one side (`RequirementORM`, `RequirementModel`) —
          rejected because it's asymmetric for no reason; neither
          side is more canonical than the other.
Revisit:  If this discipline gets violated in a later session (a bare
          double-import slips through), that's a signal to reconsider
          — not before.

---

## D-0008 — Terminal-only for all file operations, including single-file copies

Date: 2026-08-22 · Session 2 (post-hoc, discovered during verification) · Status: accepted

Context:  Session 2's delta was applied by dragging files from the
          unzipped folder into the working repo in Finder, instead of
          `unzip` + `rsync -a` as instructed. Finder's drag-and-drop
          overwrite silently deleted six files it wasn't supposed to
          touch (`main.py`, `api/__init__.py`, `api/health.py`,
          `tests/test_health.py`, and both `__init__.py` files) —
          none of which were part of the session 2 delta and should
          have been left untouched. `make verify` still reported
          green afterward, because ruff/mypy/pytest only check
          whatever files happen to exist; none of them can detect a
          file going missing.
Decision: Every file operation on this repo — copying a delta,
          extracting an archive, moving a single file — goes through
          the terminal (`unzip`, `rsync -a`, `cp`, `mv`), never
          Finder, never drag-and-drop, regardless of how small the
          change looks.
Why:      This is the same failure class already logged from a prior
          project (Finder "Replace" wiping a source directory during
          zip extraction), just triggered a second way. The pattern
          isn't "zips are dangerous" — it's "Finder's copy/overwrite
          operation is not additive-safe in general." Terminal
          commands were chosen specifically because they're either
          additive-only (`rsync -a` without `--delete`) or their
          blast radius is explicit and visible in the command itself,
          unlike a Finder drag whose scope isn't inspectable before
          it runs.
Rejected: Trusting Finder for "just this once, it's a small change" —
          this is precisely the reasoning that led to it happening
          twice.
Revisit:  Not expected to change. If a GUI file operation is ever
          genuinely necessary, verify file counts (`find ... | wc -l`
          or equivalent) immediately after, before running `make
          verify` — a passing test suite is not evidence that no
          files went missing.

---

## D-0009 — one factory function for all four extraction categories

Date: 2026-08-22 · Session 3 · Status: accepted

Context:  Pain, constraint, requirement, and vocabulary extraction
          (the four parallel fan-out nodes) are structurally
          identical: call the LLM with a category-specific prompt,
          parse the response, locate each quote's span, build
          Requirements, drop anything that doesn't locate.
Decision: `make_signal_extractor(category, prompt_template, provider)`
          is a factory returning one node function. Called four times
          in builder.py with different arguments, instead of four
          separate near-duplicate async functions.
Why:      Any future fix to the shared logic — a parsing edge case, a
          retry policy, a change to how spans are located — applies
          in one place. Four copy-pasted functions drift: a fix
          applied to three of four during a rushed session is a real
          failure mode, not a hypothetical one.
Rejected: Four separate functions (`extract_pains`, `extract_constraints`,
          etc.) — more obviously named at the call site, but the
          duplication cost outweighs that; the factory call sites in
          builder.py are still self-documenting via their arguments.
Revisit:  If a category ever needs genuinely different logic (not just
          a different prompt), that category gets pulled out of the
          factory into its own function — not before.

---

## D-0010 — assemble_brief has no LLM call

Date: 2026-08-22 · Session 3 · Status: accepted

Context:  The final graph node turns classified requirements into a
          SolutionBrief with a summary.
Decision: The summary is composed from counts (category breakdown,
          in/out/needs-clarification totals) in plain Python — no
          model call.
Why:      Consistent with the project's spine (AI proposes,
          deterministic code writes — see D-0009 in the original
          architecture discussion, and the config validator planned
          for session 5). The requirements were already extracted and
          classified by the nodes upstream; composing them into a
          countable summary is aggregation, not generation, and
          aggregation done deterministically is both cheaper and
          impossible to hallucinate.
Rejected: An LLM-written prose summary — more polished output, but it
          would be the one place in the graph where the final
          artifact's accuracy depends on the model correctly
          summarizing its own upstream output rather than on
          arithmetic. Not worth the risk for what's fundamentally a
          count.
Revisit:  If user-facing polish on the summary becomes a real
          requirement (session 6+, when this reaches the demo UI),
          consider a presentation-layer LLM rewrite of the
          deterministic summary — as a display transform, not a
          replacement for how the brief itself is assembled.

---

## D-0011 — scoped type: ignore on StateGraph.add_node calls

Date: 2026-08-22 · Session 3 · Status: accepted

Context:  LangGraph 1.2.11's type stubs for `StateGraph.add_node`
          resolve the node-callable overloads against `Never` for our
          usage pattern (a plain `async def (state) -> dict` closure
          returned from a factory function), even after explicitly
          parametrizing `StateGraph[ExtractionState, Any, Any]`. The
          graph runs correctly at runtime — this is purely a static
          typing mismatch in a library that recently overhauled its
          generics.
Decision: Six `# type: ignore[arg-type]` comments on the `add_node`
          calls in builder.py, each on the exact line the mismatch
          occurs, not a blanket file-level ignore.
Why:      mypy strict is a real gate elsewhere in this codebase — the
          alternative to a scoped ignore here is either downgrading
          mypy strictness project-wide (unacceptable, loses real
          coverage everywhere else) or fighting a third-party stub
          bug with no guarantee of a clean resolution. A narrow,
          commented ignore keeps the gate meaningful for every other
          line while being honest about the one spot it can't help.
Rejected: `# type: ignore` at file level — too broad, would silently
          swallow a real type error introduced anywhere else in this
          file later.
Revisit:  Re-check on the next LangGraph version bump — if the stubs
          fix this, remove the ignores; mypy will flag them as
          unused ignores if so, which is itself the signal to revisit.

---

## D-0012 — scope classification is batched, with strict fallback on mismatch

Date: 2026-08-22 · Session 3 · Status: accepted

Context:  Every extracted requirement needs a scope label
          (in_scope / out_of_scope / needs_clarification). Calling the
          LLM once per requirement doesn't scale — a 30-requirement
          transcript would mean 30 round trips for what's a fairly
          simple classification task.
Decision: One call classifies the entire batch, matched back to
          requirements strictly by array index. If the model returns
          a different number of labels than requirements sent, every
          requirement in that batch falls back to
          NEEDS_CLARIFICATION rather than attempting a partial or
          best-effort alignment.
Why:      A length mismatch means the response can't be trusted to be
          positionally aligned — attempting to zip a 28-item response
          against 30 requirements risks silently mislabeling two
          requirements with someone else's scope, which is worse than
          an honest "needs clarification" on all of them. Fail loud
          and conservative, not quiet and wrong.
Rejected: Per-requirement classification calls — correct and simple,
          but doesn't scale on cost or latency for longer transcripts.
          Fuzzy/partial index alignment on mismatch — rejected for the
          reason above.
Revisit:  If batch sizes grow large enough to risk the single
          response exceeding a reasonable token budget, consider
          chunking into multiple batched calls rather than reverting
          to per-item calls.
