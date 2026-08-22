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

---

## D-0013 — CLI entry point before an HTTP route

Date: 2026-08-22 · Session 4 · Status: accepted

Context:  Sessions 1-3 built the extraction graph and persistence
          model, but nothing had ever called them with a real
          provider or a real database yet. Something had to be the
          first real entry point.
Decision: `overture extract <transcript.txt>`, a CLI command (wired
          via `[project.scripts]` in pyproject.toml), not a FastAPI
          route.
Why:      This is specifically the moment the project needs to prove
          real Claude output survives contact with
          `parse_signals_response()` and `locate_span()` — code that
          has, so far, only ever seen a scripted fake. A CLI prints
          every extracted requirement with its source quote directly
          to the terminal on every run, which makes a bad extraction
          immediately visible without needing to inspect a JSON
          response or attach a debugger. It also matches how this
          project has been verified from session 1 onward — real
          terminal output, pasted back, checked line by line — rather
          than introducing a new verification surface (curl, an HTTP
          client, a running server) for what's fundamentally a
          one-shot diagnostic step.
Rejected: A FastAPI route (`POST /api/v1/sessions/{id}/extract`) —
          this is still coming, it's the natural session 6 runtime
          entry point once a demo needs to serve prospects over HTTP.
          Building it now, before a single real Claude call has been
          made, would mean debugging two new things at once (the live
          API behavior AND the route/request-handling code) instead
          of one.
Revisit:  Session 6, when the demo runtime needs an HTTP-facing
          extraction trigger. The CLI doesn't get deleted at that
          point — it stays as the fast local diagnostic path.

---

## D-0014 — real bug found via live API: classify_scope missing code-fence stripping

Date: 2026-08-22 · Session 4 (post-hoc, found via Aaron's first live run) · Status: fixed

Context:  Aaron's first real `overture extract` run against live
          Claude, on the manufacturing transcript, extracted 39
          genuinely correct requirements with verbatim, traceable
          source quotes — the extraction side worked perfectly. But
          all 39 came back scope-classified as `needs_clarification`,
          which is not a plausible real result for that transcript.
          Root cause: `parse_signals_response()` in llm_output.py
          strips ```json code fences before parsing, but
          `make_classify_scope()`'s parsing in nodes.py never got the
          same treatment — it called `json.loads()` on the raw
          response. Claude wrapped the 39-item scope response in a
          code fence (far more likely at that batch size than in the
          small 3-item fake-provider test fixtures), `json.loads`
          threw, and D-0012's conservative mismatch fallback silently
          absorbed the failure — technically working as designed, but
          masking a real parsing bug behind a safety net meant for a
          different failure mode (wrong item count, not unparseable
          JSON).
Decision: Extracted the fence-stripping regex into a shared
          `strip_code_fences()` function in llm_output.py, used by
          both `parse_signals_response` and `classify_scope`. Added a
          regression test with a fenced FakeProvider scope response,
          and proved it fails against the pre-fix code before
          confirming it passes against the fix (not just written and
          assumed correct).
Why:      This is exactly the class of bug a fake provider can never
          surface on its own — every existing test fixture returned
          hand-written, unwrapped JSON because that's what the test
          author typed. It took a real, live Claude call to expose
          the gap between "what we assumed the model would return"
          and "what it actually returns at a batch size the fake
          tests never exercised." This is the concrete payoff of
          D-0013 (CLI before route, so real-API testing happens early
          and cheaply) — the bug surfaced on the very first live run,
          not three sessions later while debugging something else.
Rejected: Leaving the fallback as the "fix" — it was never broken as
          a safety net, but treating "always falls back" as
          acceptable behavior would mean scope classification never
          actually works, which defeats the feature.
Revisit:  Worth deliberately testing other real-API-only divergences
          (extra prose before/after JSON, trailing commentary) the
          same way — via a real run first, then a regression test
          that's proven to fail pre-fix — rather than trying to
          preemptively guess every way a live model might diverge
          from a hand-written fixture.

---

## D-0015 — .env is gitignored, so .env.example changes don't propagate

Date: 2026-08-22 · Session 4 (post-hoc) · Status: noted, not a code fix

Context:  Aaron's live `overture extract` run failed with
          `ModuleNotFoundError: No module named 'psycopg2'` when
          persisting to Postgres. Root cause: his actual `.env` file
          (created early, likely right after session 1) still had the
          original `DATABASE_URL=postgresql://...` value from before
          session 2 added the `+asyncpg` driver requirement to
          `.env.example`'s default. Because `.env` is gitignored by
          design (D-0002 exists specifically so real secrets never
          land in git), a change to `.env.example` in a later session
          has no way to reach a `.env` file a person already created
          — there's no mechanism that re-syncs them.
Decision: No code change. This is a process gap, not a code bug:
          `.env.example` is the template, `.env` is a one-time copy
          the person owns and must update themselves when the
          template changes in a way that matters.
Why:      Keeping `.env` out of git is correct and not up for
          revisiting (D-0002) — the alternative (committing secrets)
          is strictly worse. The real fix is procedural: whenever a
          session changes what `.env.example` expects, say so
          explicitly and tell Aaron to diff his real `.env` against
          it, rather than assuming a `cp` from session 1 is still
          accurate several sessions later.
Rejected: Adding a startup check that validates `DATABASE_URL` starts
          with `postgresql+asyncpg://` and fails fast with a clear
          message — a reasonable idea, genuinely worth doing, but
          scoped as a session 5+ improvement rather than a reactive
          patch bolted on immediately after hitting this once.
Revisit:  Session 5 — add that startup validation to Settings as a
          proper field validator, not a special-cased error message.

---

## D-0016 — print the raw response on scope-classification parse failure

Date: 2026-08-22 · Session 4 (post-hoc) · Status: added

Context:  After fixing D-0014 (missing code-fence stripping), Aaron's
          next live run against the same 39-item transcript still
          produced 39/39 needs_clarification. Two guesses in a row
          without seeing the actual raw model response is one too
          many — continuing to hypothesize blind wastes a live-API
          call each time and doesn't converge any faster than just
          looking at the real text.
Decision: On both failure paths in `classify_scope` (JSON that parses
          but has the wrong length, and JSON that fails to parse
          entirely), print the raw response text to stderr before
          falling back. Also raised `max_tokens` for this call from
          1024 to 4096 -- 39 short labels barely need any tokens, but
          if the model adds explanation text despite instructions,
          1024 tokens is tight enough to genuinely risk truncating the
          JSON array mid-response, which produces the exact same
          symptom (JSONDecodeError -> fallback) as the fence-stripping
          bug did.
Why:      This turns "the fallback silently fired again, guess why"
          into "here is the exact text that failed to parse, and
          here is exactly why." The fallback itself is correct and
          stays (D-0012) -- what was missing was visibility into what
          it was falling back *from*. Bumping max_tokens is a cheap,
          low-risk change that removes one entire plausible cause
          before even needing the new diagnostic output.
Rejected: Continuing to iterate by hypothesis without adding
          visibility -- already tried once (D-0014) and cost a full
          extra live-API round trip to discover it wasn't the whole
          story.
Revisit:  Once scope classification is confirmed working reliably
          across a few real transcripts, consider downgrading this
          from print-to-stderr to proper structured logging (the
          project has no logging framework wired in yet) -- stderr
          printing is the right amount of ceremony for now, while
          this exact code path is still being actively debugged.

---

## D-0017 — blueprints are a closed, hardcoded catalog; selection is scored, not chosen by the model

Date: 2026-08-22 · Session 5 · Status: accepted

Context:  A POC demo needs a shape -- what tools it has, what it's
          allowed to do. There are exactly three shapes this project
          supports (grounded document Q&A, triage/routing, structured
          extraction), matching the report's original architecture.
Decision: `poc/blueprints.py` defines all three as frozen dataclasses
          in a fixed tuple, `ALL_BLUEPRINTS`. `select_blueprint()` in
          `poc/compiler.py` scores a SolutionBrief's in-scope
          requirement text against each blueprint's capability_tags
          (case-insensitive substring counting) and picks the highest
          score, ties broken by declaration order. No LLM call
          anywhere in selection.
Why:      This is the same principle as D-0005 and D-0010 applied to
          infrastructure instead of extracted data: letting the model
          choose the blueprint means letting it choose which tools a
          demo gets, which is a security/scope decision, not a
          content-generation one. A deterministic scorer is also
          trivially unit-testable (see test_blueprints.py) in a way
          "ask the LLM which blueprint fits" never could be --
          same input always produces the same blueprint, forever.
Rejected: LLM-based blueprint selection (e.g. "given this brief, which
          of these three blueprints fits best?") -- more flexible on
          paper, but non-deterministic, harder to test, and gives the
          model influence over tool attachment that the validator
          (D-0018) is specifically designed to keep out of its hands.
Revisit:  If a fourth blueprint is ever added, it goes into
          `ALL_BLUEPRINTS` alongside the other three -- the scoring
          mechanism doesn't change, just the catalog it scores against.

---

## D-0018 — the config validator is the only code with authority to mark a DemoConfig VALIDATED

Date: 2026-08-22 · Session 5 · Status: accepted

Context:  A DemoConfig assembled by `fill_config` (blueprint + LLM
          slot content) needs a final check before anything downstream
          could ever deploy it — the original architecture's headline
          claim from session 0 planning: "the validator is the only
          component with write authority over a manifest."
Decision: `poc/validator.py`'s `validate_config()` is a pure function:
          takes a DemoConfig, returns a new one with `status` and
          `validation_errors` set. It checks blueprint_id against the
          known catalog, every tool against a hardcoded
          `TOOL_ALLOWLIST`, token_budget against a ceiling,
          system_prompt non-empty, and at least one sample question.
          Zero imports of anthropic, openai, or the provider Protocol
          anywhere in the file — enforced by a test that greps the
          module's own source for those strings.
Why:      Every failure mode this module catches is a failure mode
          `fill_config` (which does call an LLM) could plausibly
          produce: an empty or malformed system prompt from a bad
          parse, a hallucinated tool name, a runaway token budget.
          The validator's entire value is that it cannot inherit any
          of the LLM's failure modes, because it never talks to one.
          Testing that claim with a real test (not just a comment)
          means the invariant breaks loudly (a failing test) the
          moment someone imports a provider into this file for a
          shortcut, rather than silently eroding over time.
Rejected: Folding validation into `fill_config` itself, as a
          post-processing step in the same function — rejected
          because it blurs exactly the line this project's whole
          pitch depends on: AI proposes, deterministic code decides
          what ships. Keeping them in separate modules, one of which
          is proven LLM-free, makes that line an architectural fact,
          not a convention someone could accidentally violate.
Revisit:  Not expected to change. If validation rules grow complex
          enough to want a JSON Schema library instead of hand-written
          checks, the "no LLM import" constraint carries forward
          unchanged regardless of what validates the shape.

---

## D-0019 — fill_config must ground on quoted_text, not the paraphrased label, for vocabulary items

Date: 2026-08-22 · Session 5 (post-hoc, found via Aaron's live run) · Status: fixed

Context:  Aaron's first live run of the compiler produced a system
          prompt opening with "Harlow Contract Intelligence assistant
          ... Harlow Industrial Group's vendor contracts." The real
          transcript never mentions any company but "Meridian
          Fabrication Group." The model also invented contract
          categories ("facilities services," "IT/software licensing")
          and numeric thresholds ("$1M," "60-day notice") that appear
          nowhere in the source. Root cause: `fill_config` built its
          vocabulary section from `Requirement.text`, which for
          VOCABULARY-category items is a paraphrased LABEL the
          extraction graph writes (e.g. "Company name"), not the
          actual term -- the real value only lives in
          `source_span.quoted_text`. The prompt handed the model
          "Company name" with nothing after it, and the model filled
          the gap with something plausible-sounding, exactly as an
          LLM will when given an incomplete pattern to complete.
Decision: `vocabulary` in `fill_config` now formats each item as
          `f'"{r.source_span.quoted_text}" ({r.text})'` -- the actual
          quoted term first, the paraphrased label as parenthetical
          context. A regression test captures the prompt sent to a
          fake provider and asserts the real quoted value appears in
          it; proven to fail against the pre-fix code (reproducing
          the exact "In-scope needs:\n- Company name" gap) before
          being confirmed to pass against the fix.
Why:      This is more serious than a cosmetic bug: it's the compiler
          actively contradicting the project's core architectural
          claim -- that generated content stays grounded in what a
          prospect actually said. It slipped past every existing test
          because the FakeSlotFillProvider tests never checked prompt
          *content*, only response parsing; nothing verified what was
          actually sent to the model until this test did.
Rejected: Leaving Requirement.text as the only vocabulary signal and
          instead trying to make the extraction prompts (session 3)
          write a better paraphrase -- doesn't fix the root cause,
          which is that fill_config was discarding a field
          (source_span.quoted_text) that already had the real answer.
Revisit:  Worth auditing whether `in_scope` (pain/constraint/requirement
          text, not vocabulary) has a milder version of this same
          risk -- those paraphrases are generally more complete
          sentences than vocabulary labels, but a systematic pass
          checking every prompt-building function for "am I passing
          the paraphrase where I should be passing the source" would
          be a reasonable session 6 audit item.

---

## D-0020 — the validator checks structure, not factual grounding, and that's a known limit

Date: 2026-08-22 · Session 5 (post-hoc) · Status: noted, scoping decision

Context:  D-0019's hallucination (a fabricated company name) shipped
          through `validate_config` with status VALIDATED before the
          bug was found. The validator correctly checked that
          system_prompt was non-empty, tools were allowlisted, and
          sample_questions existed -- it had no way to know "Harlow
          Industrial Group" wasn't a real term from the brief, because
          checking that would require re-reading the brief's content
          and reasoning about factual consistency, which is exactly
          the kind of judgment call D-0018 keeps out of the validator
          on purpose (no LLM calls allowed in that module).
Decision: No change to the validator's scope. This is logged
          explicitly so "validated" is never overclaimed in a demo or
          interview as "fact-checked" or "hallucination-free" -- it
          means "structurally well-formed and within policy," nothing
          more.
Why:      A deterministic validator that could actually catch semantic
          hallucination would need to either call an LLM (reintroducing
          the exact failure mode it exists to guard against) or do
          fragile string-matching against extracted vocabulary terms
          (high false-negative rate -- paraphrasing legitimately
          changes wording). Neither is worth adding speculatively.
          D-0019's fix (ground the prompt properly) addresses the
          actual root cause; this decision just names the residual
          risk honestly rather than pretending the validator closes it.
Revisit:  If this class of bug recurs after D-0019's fix, a narrow,
          specific check might be worth adding -- e.g., confirming
          every proper-noun-looking token in system_prompt appears
          somewhere in the brief's source spans. Not worth building
          speculatively before there's evidence it's still needed.
