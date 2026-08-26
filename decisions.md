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

---

## D-0021 — hand-rolled hashing embedder instead of a third paid API

Date: 2026-08-22 · Session 6 · Status: accepted

Context:  Retrieval needs vectors to compare. Claude has no embeddings
          endpoint. The obvious options were Voyage AI (Anthropic's
          recommended embeddings partner) or Azure OpenAI's
          text-embedding-3-small.
Decision: `poc/embeddings.py` implements the classic feature-hashing
          trick (the same technique behind scikit-learn's
          HashingVectorizer) by hand: tokenize, hash each token to a
          fixed-width vector index via sha256, sum, L2-normalize.
          Zero network calls, zero API cost, fully deterministic.
Why:      This project already carries two LLM provider options
          (Anthropic, Azure OpenAI) specifically to stay portable and
          cheap during development (D-0006). Adding a third paid API
          purely for embeddings, during a phase where the whole
          point is iterating cheaply on a portfolio project, works
          against that same reasoning. The hashing trick is a real,
          well-established technique -- not toy code -- and is
          honestly explainable in an interview as a deliberate
          cost/quality tradeoff, not a corner cut out of ignorance.
          It is also trivially deterministic, which made writing real
          unit tests (exact-match assertions, not "roughly similar")
          possible in a way a live embeddings API never would be.
Rejected: Voyage AI or Azure OpenAI embeddings now -- both are
          reasonable choices, genuinely better retrieval quality, and
          explicitly the intended swap-in later: `Embedder` is a
          Protocol for exactly this reason, mirroring `LLMProvider`.
          The swap is a new class implementing `.embed()`, not a
          rewrite of retrieval.py, ingestion.py, or the demo route.
Revisit:  Session 7-8, once Azure infrastructure exists anyway --
          swapping in Azure OpenAI embeddings behind the same
          Protocol is a natural, low-cost upgrade once that spend is
          already committed for other reasons.

---

## D-0022 — two-tier access: signed share tokens for demo consumption, Entra ID deferred for the console

Date: 2026-08-22 · Session 6 · Status: accepted (partial -- console auth still deferred)

Context:  This is the auth decision flow.md has flagged as open since
          session 1's `/health` endpoint. The first real route
          (`POST /api/v1/demo/{token}/ask`) needed an access model
          before it could ship.
Decision: Prospect-facing demo access uses a signed, time-limited
          token (`poc/tokens.py`, itsdangerous `URLSafeTimedSerializer`)
          embedding the session_id -- no login, no account, just
          possession of a link. The SE console that will eventually
          create and manage these sessions gets real Entra ID
          (OIDC/PKCE via MSAL) once session 8 stands up Azure
          infrastructure to authenticate against -- that piece
          remains explicitly deferred, not built here.
Why:      These are two different trust models for two different
          people. A prospect clicking a link a salesperson sent them
          is proving they received the link, not proving an identity
          -- exactly matching the original report's "leave-behind
          sandbox link the prospect can revisit" requirement. An SE
          creating and managing sessions needs real account-level
          auth. Building a full OIDC flow now, before there's an
          Entra ID tenant to authenticate against (that's session 7-8
          Azure work), would mean building against nothing real to
          test against. itsdangerous is a tiny, well-audited,
          dependency-light library -- appropriate weight for "proves
          possession of a link," not "proves identity."
Rejected: Building the console's Entra ID auth now, ahead of having
          Azure infrastructure to point it at -- would be
          unverifiable exactly the way the session 2 Alembic
          migration was unverifiable before a live database existed,
          except with no clear "verify on Aaron's machine" path
          since Entra ID requires an actual tenant, not just Docker.
Revisit:  Session 8, when Azure infrastructure exists and Entra ID
          app registration becomes possible to actually test against.

---

## D-0023 — max_tokens for classify_scope raised to 8192 after evidenced truncation

Date: 2026-08-22 · Session 6 (post-hoc, found via Aaron's live run) · Status: fixed

Context:  D-0016's diagnostic logging (added in session 4) paid off
          directly here: a live run against a 35-item batch reported
          `output_tokens=4096, Raw response text was: ''` -- output
          tokens exactly at the (then) max_tokens ceiling, with zero
          extracted text. That specific combination -- full token
          budget consumed, nothing in the text-typed content block --
          points at one cause: the model spent its entire budget on
          internal reasoning for this moderately complex 35-item
          classification and was cut off before ever emitting the
          JSON answer. This is different from D-0014 (a code-fence
          the parser didn't strip) and different from D-0016's first
          empty-response sighting (which self-resolved on retry,
          plausibly a transient generation issue) -- this run gave
          hard evidence of a specific, repeatable cause.
Decision: Raised `max_tokens` for the classify_scope call from 4096 to
          8192. Also sharpened the diagnostic: when a JSONDecodeError
          fires AND output_tokens is at or above the (new) ceiling,
          the printed message now says so explicitly -- "likely
          truncated mid-reasoning before any JSON was emitted" --
          instead of leaving that inference to be re-derived by hand
          each time, the way it had to be this time.
Why:      This is the direct payoff of investing in diagnostics
          (D-0016) instead of guessing again (the lesson from D-0014).
          The fix itself is simple -- more headroom -- but it's a
          fix grounded in specific evidence from a real run, not
          speculation. The sharpened diagnostic means the next time
          this exact signature appears (if 8192 ever proves
          insufficient for a larger batch), it's self-diagnosing on
          the first read instead of requiring another round of
          "what does the raw output actually look like."
Rejected: Retrying automatically on empty response -- a reasonable
          idea in general, but premature here: adding retry logic
          before confirming whether 8192 tokens resolves the issue
          would make it harder to tell, on the next occurrence,
          whether the retry masked a real problem or the token
          increase actually fixed it. Worth reconsidering if 8192
          proves insufficient.
Revisit:  If this exact "output_tokens at ceiling, empty text" pattern
          recurs even at 8192, that's a strong signal to either batch
          scope-classification into smaller chunks (fewer items per
          call, more calls) or investigate whether the Anthropic SDK
          call should explicitly disable extended thinking for this
          specific, low-creativity classification task.

---

## D-0024 — scope classification batched into groups of 10, replacing the single-call design

Date: 2026-08-22 · Session 6 (post-hoc, found via a second live run) · Status: fixed

Context:  D-0023 raised max_tokens from 4096 to 8192 on the theory
          that the model needed more room to reason before emitting
          JSON. Aaron's very next run reproduced the identical
          signature -- output_tokens exactly at the ceiling (8192
          this time, 4096 the time before), text empty -- on a
          33-item batch. Two occurrences at two different ceilings,
          both landing exactly on the ceiling, is strong evidence that
          "not enough tokens" was the wrong diagnosis: the model's
          reasoning appears to scale to consume whatever budget it's
          given for a batch this size, rather than converging and
          leaving headroom. Raising the number a third time had no
          principled reason to behave differently.
Decision: `make_classify_scope` now splits `signals` into batches of
          `_SCOPE_BATCH_SIZE = 10` and calls the model once per batch
          (`_classify_batch`), each with its own 2048-token budget --
          smaller, not larger, than the single-batch design's ceiling.
          A batch that fails to parse only marks that batch's ~10
          items as NEEDS_CLARIFICATION; other batches are unaffected.
          Proven with a test that fails one specific batch out of
          three (25 items total) and asserts the other two batches'
          items came through correctly classified.
Why:      A smaller task per call is a more direct fix for "the model
          is over-deliberating" than a bigger budget -- if the
          runaway reasoning scales with item count or with the
          cognitive complexity of judging many nuanced items at once,
          shrinking the batch attacks the actual mechanism instead of
          just giving it more room to do the same thing. The fault
          isolation is a genuine secondary benefit, not just a side
          effect: previously, one malformed response meant every
          single extracted item in the whole transcript lost its real
          scope classification; now a bad batch costs at most 10
          items, and every other batch's real, useful classification
          survives.
Rejected: Raising max_tokens a third time (e.g. to 16384) -- rejected
          specifically because the evidence (two failures, two
          different ceilings, both exactly at the ceiling) argues
          against "more budget" being the actual fix, not merely
          "not yet tried enough."
Revisit:  If batches of 10 still occasionally hit their 2048-token
          ceiling with empty output, that would be strong evidence the
          issue isn't item count at all, and worth investigating
          whether the Anthropic SDK call needs to explicitly disable
          extended thinking for this task, rather than continuing to
          shrink batch size indefinitely.

---

## D-0025 — local Terraform state, no remote backend

Date: 2026-08-26 · Session 7 · Status: accepted

Context:  Terraform needs somewhere to store state (its record of
          what it created and with what configuration). The standard
          production pattern is a remote backend -- an Azure Storage
          Account with blob versioning and state locking.
Decision: State stays local, on Aaron's machine, in
          `terraform/.terraform/` and `terraform/terraform.tfstate`
          (both gitignored).
Why:      A remote backend's entire value is enabling safe
          collaboration and preventing state loss across a team and
          across machines. This project has one operator, on one
          machine, running an ephemeral build -> record -> destroy
          cycle where the infrastructure mostly doesn't exist between
          sessions. Provisioning a Storage Account purely to hold
          state for infrastructure that's about to be destroyed
          anyway adds a persistent resource (and a small ongoing
          cost) to solve a collaboration problem that doesn't exist
          here.
Rejected: Azure Storage Account remote backend -- the standard,
          correct choice for a real team project; explicitly not
          this project's situation.
Revisit:  If this project ever needs multi-machine or
          multi-collaborator access (unlikely for a portfolio piece),
          revisit immediately -- local state actively breaks that use
          case, not just under-serves it.

---

## D-0026 — Terraform never manages secrets it didn't generate itself

Date: 2026-08-26 · Session 7 · Status: accepted

Context:  Key Vault needs to hold real secrets eventually: the
          Postgres password, and Aaron's actual Anthropic API key.
Decision: `keyvault.tf` creates exactly one `azurerm_key_vault_secret`
          resource -- the Postgres admin password, generated by
          Terraform's own `random_password` resource. The Anthropic
          API key (and Azure OpenAI credentials, if ever used) are
          never referenced anywhere in any `.tf` or `.tfvars` file.
          They're added post-`apply` via `az keyvault secret set`,
          documented in terraform/README.md.
Why:      Terraform state files store resource values, including
          secret values, in plaintext by default -- that's simply how
          the tool works, not a bug. A secret Terraform manages lives
          in the state file whether or not the file itself is
          encrypted at rest. For a password Terraform generated
          specifically for this environment, that's an acceptable,
          well-understood tradeoff. For Aaron's actual, reusable
          Anthropic API key -- a credential with value far outside
          this one Azure environment -- adding it as a Terraform
          variable creates a second place it could leak from (a
          committed `.tfvars`, a shared state file) for zero benefit,
          since it needs to be set manually in Key Vault exactly once
          either way.
Rejected: A `anthropic_api_key` Terraform variable, marked
          `sensitive = true` -- `sensitive` only suppresses the value
          from CLI output; it does not remove it from the state file
          on disk, which is the actual risk being managed against.
Revisit:  Not expected to change. This boundary (Terraform manages
          infrastructure-generated secrets; humans manage
          externally-issued credentials) is a durable rule, not a
          situational one.

---

## D-0027 — Postgres reachable via public IP allowlist, not private networking

Date: 2026-08-26 · Session 7 · Status: accepted

Context:  Postgres Flexible Server needs to be reachable both from
          Aaron's laptop (to run migrations and the CLI against it)
          and, eventually, from the Container App (session 8).
Decision: Public network access, restricted by firewall rule to
          Aaron's current IP plus Azure's own "allow Azure services"
          special range -- not a VNet with private endpoints.
Why:      Private networking (VNet integration, private DNS zones,
          private endpoints) is the correct answer for a real
          production deployment, and it costs real, ongoing money
          (a VNet Gateway or equivalent) for protection this project
          doesn't need: there's no sensitive customer data here, the
          environment is destroyed at the end of every session, and
          the actual attack surface is "a strong generated password
          plus an IP allowlist," which is adequate for a portfolio
          demo. Minimum-resources principle, applied to network
          architecture the same way it's been applied to compute and
          storage choices all along.
Rejected: VNet + private endpoints -- the right call in production;
          explicitly not proportionate here. Worth naming as the
          "what I'd do differently for production" answer in an
          interview, precisely because the tradeoff was made
          consciously, not skipped.
Revisit:  If this project's Azure infrastructure is ever left running
          continuously (rather than destroyed each session) or starts
          handling anything resembling real customer data, revisit
          immediately.

---

## D-0028 — $25/month budget alert, three thresholds

Date: 2026-08-26 · Session 7 · Status: accepted

Context:  Needed a concrete number for the Azure Consumption Budget
          alert, and a decision on how many thresholds.
Decision: $25/month, with separate email notifications at 50%, 80%,
          and 100% of that amount.
Why:      $25 matches the per-project cap discussed during initial
          cost planning, before any Azure resource in this project
          existed -- well under the $100 total credit, leaving room
          for the other two planned Microsoft portfolio projects.
          Three thresholds instead of one means a warning arrives at
          $12.50 and $20, not just a single alert after the cap is
          already blown -- the whole point of a budget alert is
          advance warning, and one threshold at the limit provides
          none.
Rejected: A single 100%-only alert -- technically satisfies "there's
          a budget alert" but provides no lead time to react before
          the threshold is crossed.
Revisit:  Not expected to change unless the per-project cost math
          from planning turns out to be wrong in practice, in which
          case the number itself (not the three-threshold pattern)
          gets revisited.

---

## D-0029 — region changed from westus2 to westus3 after a real subscription-policy rejection

Date: 2026-08-26 · Session 7 (post-hoc, found via Aaron's first `terraform apply`) · Status: fixed

Context:  The original `location` default, `westus2`, was a reasonable
          general-purpose choice with no reason to expect a problem --
          but it was never actually checked against this specific
          subscription's constraints, because I had no way to query
          Azure from my environment (no network access to any Azure
          endpoint). Aaron's first `terraform apply` failed on four of
          the six resources it reached, every failure carrying the
          identical message: `RequestDisallowedByAzure: ... best
          available regions where your subscription can deploy
          resources`. This is a real Azure Policy restriction on the
          Azure for Students subscription, not a Terraform or config
          error.
Decision: Queried the actual allowed regions directly --
          `az policy assignment list` surfaces the policy's
          `listOfAllowedLocations` parameter -- and switched the
          `location` variable's default from `westus2` to `westus3`,
          the closest of the five allowed regions
          (westus3, mexicocentral, canadacentral, centralus, eastus)
          to San Diego.
Why:      Guessing a second region without checking risked repeating
          the exact same failure a second time for no better reason
          than the first guess. Querying the policy directly gives a
          confirmed-correct answer in one command instead of another
          round of apply-and-see. This is the same discipline used
          throughout the app-code sessions (D-0014, D-0019, D-0023,
          D-0024) applied to infrastructure: when something fails
          against real infrastructure, get the actual evidence before
          proposing a fix, rather than iterating by hypothesis.
Rejected: Trying `eastus` (the most commonly-used "safe default" in
          most Azure tutorials) on the theory that it's more likely to
          be allowed -- would have worked by luck here, but "worked by
          luck" isn't a standard this project has held itself to for
          six sessions; the policy query took one command and removed
          the guesswork entirely.
Revisit:  If Aaron changes Azure subscriptions or tenants later (e.g.
          for a future employer's Azure environment), re-run the
          policy query before assuming any region default is valid --
          this constraint is specific to this one subscription, not a
          general Azure rule.

---

## D-0030 — removed explicit Postgres zone pin after an unexplained InternalServerError

Date: 2026-08-26 · Session 7 (post-hoc, found via Aaron's second `terraform apply`) · Status: fixed (hypothesis-based)

Context:  The first `apply` attempt in the corrected `westus3` region
          got substantially further than the `westus2` attempt --
          resource group, managed identity, Log Analytics, and Key
          Vault (with both access policies) all succeeded -- but three
          resources failed, each for a different reason. Two had clear
          causes (an Application Insights read-after-write race,
          documented below as expected to self-resolve on retry; and
          a missing `Microsoft.App` resource provider registration,
          a one-time subscription-level fix, not a code issue). The
          third, Postgres Flexible Server, failed with a bare
          `InternalServerError` and no further detail from Azure's
          API -- the least diagnosable failure type this project has
          hit, since there's no specific error message to root-cause
          against, unlike every prior bug this project has fixed.
Decision: Removed the explicit `zone = "1"` argument from
          `azurerm_postgresql_flexible_server.main`, letting Azure
          choose an available zone automatically instead.
Why:      With no specific error to diagnose, the next best move is
          removing the one concrete, plausible variable in the
          config rather than just re-running the same request and
          hoping. Pinning to zone 1 specifically assumes that exact
          zone has capacity for this SKU in this region on this
          subscription -- an assumption with no verification behind
          it, in a region (`westus3`) this subscription had never
          provisioned into before this session. This is a genuinely
          different situation from every other bug fix in this
          project: there is no test that can prove this was the
          actual cause the way, say, D-0019's reverted-code test
          proved the vocabulary grounding bug. It's an informed guess,
          labeled as one.
Rejected: Retrying the identical config unchanged -- a legitimate
          first thing to try for a genuinely transient error, but
          worth pairing with removing the zone pin at the same time
          rather than spending a second full apply cycle (each
          costing real minutes and, for Postgres specifically, real
          spend during provisioning) on an unmodified retry first.
Revisit:  If Postgres still fails with the same InternalServerError
          after this change, that's real evidence the zone pin was
          NOT the cause, and the next step is opening an Azure support
          request or checking Azure's status page for the region --
          at that point it's more likely an Azure-side issue than
          anything in this configuration.

---

## D-0031 — OIDC federated credential scoped to a single branch, not the whole repo

Date: 2026-08-26 · Session 8 · Status: accepted

Context:  GitHub's OIDC subject format supports several scopes --
          whole-repo, specific branch, specific environment, pull
          requests, tags. `azuread_application_federated_identity_credential`
          needed a `subject` pattern.
Decision: `subject = "repo:${var.github_repo}:ref:refs/heads/main"` --
          only workflow runs triggered on the `main` branch can
          exchange a GitHub OIDC token for an Azure one. A workflow
          run from a feature branch, a fork, or a pull request gets no
          token and cannot deploy, full stop, at the identity-provider
          level -- not by convention, by construction.
Why:      This project has one branch and one deploy target;
          restricting to `main` costs nothing and closes an entire
          class of risk (a PR from a compromised or malicious fork
          attempting to trigger a deploy) for free. Scoping tightly by
          default and widening only if a real need appears is the
          same posture as D-0022's tokens (a link proves possession,
          not identity) and D-0018's validator (deterministic checks,
          narrowly scoped).
Rejected: A whole-repo subject pattern (`repo:owner/name:*`) -- looser
          than necessary for a single-branch project, and the tighter
          pattern doesn't cost anything to set up correctly the first
          time.
Revisit:  If this project ever adopts a branching workflow (feature
          branches deploying to a staging environment, say), add
          additional federated credentials scoped to those specific
          patterns rather than loosening this one.

---

## D-0032 — GitHub Actions deploy identity uses "Contributor," not a narrower role

Date: 2026-08-26 · Session 8 · Status: accepted, acknowledged tradeoff

Context:  The GitHub Actions OIDC identity needs enough Azure
          permission to run `az containerapp update`. Azure has more
          specific built-in roles for this, but their exact names
          have shifted across Azure API versions and I could not
          verify a specific narrower role name from this environment
          (no Azure network access -- same limitation as all of
          session 7's Terraform).
Decision: `azurerm_role_assignment` grants the built-in `Contributor`
          role, scoped to just this one resource group -- not
          subscription-wide.
Why:      `Contributor` is guaranteed to exist under that exact name
          on every Azure subscription; a more specific but
          possibly-misnamed role risks a repeat of session 7's
          region/provider-registration debugging cycle, this time on
          a role name I have no way to verify from here. Given the
          resource group this scopes to is destroyed at the end of
          every session (same ephemeral-infrastructure reasoning as
          D-0025), the actual blast radius of "broader role than
          strictly necessary" is low -- there's nothing long-lived for
          excess permission to threaten.
Rejected: A narrowly-scoped custom role or a more specific built-in
          role name -- more correct in principle, genuinely worth
          doing if this environment ever stops being destroyed every
          session, but not worth risking an unverifiable role name on
          a resource group with a multi-hour lifespan.
Revisit:  If this project's Azure environment is ever left running
          continuously rather than destroyed each session, revisit
          immediately and scope down to the minimum role actually
          needed for `containerapp update`.

---

## D-0033 — GHCR over ACR, public image, manually-triggered deploy

Date: 2026-08-26 · Session 8 · Status: accepted

Context:  The deployed container image needs to live somewhere
          Container Apps can pull it from. Azure Container Registry
          is the "native" choice with managed-identity pull support
          and no public-visibility tradeoff; GitHub Container Registry
          is free and needs no new Azure resource, but Container Apps
          has no managed-identity pull mechanism for it -- only
          registry username/password, which would mean storing a
          GitHub PAT as yet another secret.
Decision: GitHub Container Registry (ghcr.io), with the package set to
          **public** after the first push, so Container Apps pulls it
          with no registry credential at all. Paired with a
          **manually-triggered** (`workflow_dispatch`, not
          on-push) deploy workflow -- see the workflow file's own
          comment for the reasoning shared with D-0025's
          ephemeral-infrastructure pattern.
Why:      A public image carries no meaningful risk here specifically
          because of how this project already handles secrets: nothing
          sensitive is ever baked into the image at build time --
          `Settings`/`get_settings()` reads everything at runtime from
          environment variables sourced from Key Vault (D-0026). A
          public image is just public application code, which the
          private GitHub repo's source already implies isn't a secret
          in the first place (the code itself isn't the confidential
          part; the API keys and DB credentials are, and those never
          enter the image). Avoiding ACR avoids a new billed Azure
          resource, consistent with the minimum-resources principle
          this project has held to since before session 1 began.
Rejected: Azure Container Registry -- the more "correct" production
          answer (private by default, managed-identity pull, no manual
          visibility toggle to remember), explicitly not worth its
          cost for a portfolio project with this usage pattern.
          Storing a GHCR PAT as a Container App secret to keep the
          package private -- rejected because it reintroduces exactly
          the kind of stored credential the whole OIDC design (D-0031)
          exists to avoid, just for a lower-value target.
Revisit:  If this project is ever demoed continuously rather than
          torn down each session, or if the app ever bakes in anything
          sensitive at build time (it shouldn't, but if that ever
          changes), revisit toward ACR immediately.

---

## D-0034 — Terraform never touches the running container image after first apply

Date: 2026-08-26 · Session 8 · Status: accepted

Context:  `azurerm_container_app.main` needs some initial image to be
          valid at first `apply`, before any real deploy has ever run
          -- but after that, GitHub Actions should be the only thing
          that changes which image is live.
Decision: The container block's `image` field starts pointing at a
          public Microsoft quickstart image, and
          `lifecycle { ignore_changes = [template[0].container[0].image] }`
          tells Terraform to never revert it on subsequent applies.
Why:      Without this, every `terraform apply` (say, to add an
          unrelated resource later) would silently roll the running
          app back to the placeholder image, undoing whatever the
          most recent GitHub Actions deploy had shipped. This is the
          infrastructure equivalent of D-0034's sibling concern
          elsewhere in this project: two different systems (Terraform,
          GitHub Actions) each need clear, non-overlapping ownership
          of what they're allowed to change, the same way D-0018 draws
          a hard line between what the LLM proposes and what the
          deterministic validator decides.
Rejected: Having Terraform manage the image tag directly (e.g. via a
          variable GitHub Actions would need to update via `terraform
          apply` on every deploy) -- adds a second deploy mechanism
          for no benefit; `az containerapp update` is simpler, faster,
          and doesn't require the deploy pipeline to touch Terraform
          state at all.
Revisit:  Not expected to change. This ownership split is a durable
          architectural line, not a situational choice.

---

## D-0035 — azure-monitor-opentelemetry over hand-rolled OTLP exporters

Date: 2026-08-26 · Session 8 · Status: accepted

Context:  The original stack design (before session 1) named
          OpenTelemetry → Application Insights as the observability
          path. Needed to actually wire it up.
Decision: `azure-monitor-opentelemetry`, Microsoft's own turnkey
          distribution -- `configure_azure_monitor(connection_string=...)`
          plus `FastAPIInstrumentor.instrument_app(app)`, gated behind
          `if settings.app_insights_connection_string:` in main.py so
          local dev and the entire test suite never make an Azure
          network call just by importing the app (proven by two real
          tests, not just a comment -- see test_observability.py).
Why:      Hand-rolling the OTel SDK, a manual OTLP exporter, and
          resource-detector configuration is meaningfully more code
          for the same outcome Microsoft's own package already
          provides pre-wired and pre-tested against Application
          Insights specifically. This is the same reasoning as D-0006
          (use the SDK, don't hand-roll what a maintained library
          already does correctly) applied to observability instead of
          LLM providers.
Rejected: Manual OTel SDK wiring with a generic OTLP exporter --
          more portable in principle (works with any OTLP-compatible
          backend, not just App Insights), but this project has one
          observability backend and no near-term need to swap it;
          paying the extra integration code for portability nothing
          currently needs isn't worth it.
Revisit:  If this project's observability backend ever needs to be
          swappable (e.g. demoing the same app against a different
          company's observability stack), revisit toward a generic
          OTLP exporter behind a similar Protocol-based swap point as
          providers/base.py's LLMProvider.

---

## D-0036 — SDSU's Entra ID tenant blocks application registration for this account

Date: 2026-08-26 · Session 8 (post-hoc, found via Aaron's real apply) · Status: confirmed, not fixable by this project

Context:  `terraform apply` failed to create `azuread_application.github_actions`
          with `Authorization_RequestDenied: Insufficient privileges
          to complete the operation.` Rather than assume this was a
          Terraform config problem, Aaron ran a direct, unrelated
          test -- `az ad app create --display-name
          permission-test-delete-me` -- outside Terraform entirely.
          It failed with the identical error.
Decision: Treat this as confirmed: SDSU's Entra ID tenant has a
          directory-level policy preventing student accounts from
          registering applications at all. Not a Terraform bug, not a
          misconfigured resource, not something achievable by
          adjusting this project's code.
Why:      The direct `az ad app create` test is what makes this a
          confirmed fact rather than a guess -- an identical failure
          on a command with zero relationship to this project's
          Terraform proves the restriction is account/tenant-level,
          not something specific to the `azuread_application` resource
          or its configuration. This is the same evidentiary standard
          every other real bug in this project has been held to
          (D-0014, D-0019, D-0023/D-0024, D-0029, D-0030): don't fix
          what you haven't confirmed is actually broken.
Rejected: Continuing to retry `terraform apply` hoping it resolves --
          would have wasted apply cycles (and, for the resources that
          succeed alongside the failing one, real provisioning time)
          on a problem no code change can fix.
Revisit:  If Aaron ever requests and receives the Application
          Developer role from SDSU IT, or runs this project against a
          personal (non-institutional) Azure subscription/tenant, this
          restriction lifts and D-0037's toggle can simply be flipped
          to `true`.

---

## D-0037 — OIDC deploy made optional via a variable; manual deploy is this session's real path

Date: 2026-08-26 · Session 8 · Status: accepted

Context:  D-0036 confirmed GitHub Actions OIDC cannot work on this
          tenant with this account. The rest of the landing zone
          (everything except the four `azuread_*`/OIDC-dependent
          resources) has no relationship to that restriction and
          should still deploy normally.
Decision: `enable_github_actions_oidc` (default `false`) gates all
          four OIDC-related resources behind `count`. The GitHub
          Actions workflow file stays in the repo unchanged --
          correct and ready for a tenant that permits app
          registration. `scripts/manual-deploy.sh` provides this
          session's actual working deploy path: build and push the
          image using Aaron's own authenticated `docker`/`az`
          sessions, which face no such restriction (registering an
          app and having Contributor-level resource permissions are
          different things -- Aaron's account has the latter, not the
          former).
Why:      Deleting the OIDC code because it can't run on this one
          tenant would throw away correct, working design for a
          reason that has nothing to do with whether the design is
          right. Toggling it off, documented with a real, confirmed
          reason, keeps the automated path demonstrable in an
          interview ("here's the OIDC design, here's why it's off by
          default, here's the manual fallback it degrades to") rather
          than silently absent with no explanation.
Rejected: Deleting oidc.tf and deploy.yml entirely -- throws away
          real, correct work over an external constraint, and removes
          the more sophisticated half of this session's story for no
          benefit.
Revisit:  Flip `enable_github_actions_oidc = true` (as a `.tfvars`
          override, not a changed default, to keep the safe default
          for this tenant) the moment either D-0036's conditions
          change or this project runs against a subscription without
          this restriction.

---

## D-0038 — Postgres `zone` needs `ignore_changes`, not just an absent argument

Date: 2026-08-26 · Session 8 (post-hoc, found via Aaron's real apply) · Status: fixed

Context:  D-0030 (session 7) removed the explicit `zone = "1"` from
          the Postgres config, reasoning that letting Azure choose
          automatically would remove one plausible cause of an
          unexplained InternalServerError. That worked -- Postgres
          provisioned successfully in session 7 and again fresh in
          session 8. But omitting the argument doesn't mean Azure's
          server ends up with no zone; Azure still assigns a real one
          (zone 1, both times). On this session's second `apply`
          (targeting just the newly-added Container App), Terraform
          saw "config has no zone value, live server has zone=1" and
          tried to reconcile by clearing it -- which the Postgres
          Flexible Server API rejects outright: a zone can only be
          changed via a specific high-availability zone-swap
          operation, not a plain update. The apply failed on this,
          not on anything related to the Container App itself.
Decision: Added `lifecycle { ignore_changes = [zone] }` to the
          Postgres resource. The argument itself stays absent from
          the config (D-0030's reasoning is unchanged and still
          correct) -- this just tells Terraform to stop trying to
          reconcile that one field against whatever Azure actually
          assigned.
Why:      This is the same shape of problem D-0034 already solved for
          the container image, just discovered in a second place:
          Azure fills in a real value for something we deliberately
          left unspecified, and a later `apply` shouldn't treat that
          as drift to correct. `ignore_changes` says "Azure owns this
          field after creation," which is the actually-true statement
          -- D-0030 was right that we shouldn't pin a specific zone
          value; it just didn't yet account for Terraform still
          wanting to reconcile the field's *absence*.
Rejected: Explicitly setting `zone = "1"` in the config now that we
          know that's what Azure picked -- would resolve this specific
          plan cleanly, but re-introduces a hardcoded assumption about
          which zone is correct, the exact thing D-0030 removed for a
          good reason. `ignore_changes` gets the benefit of both
          decisions at once.
Revisit:  If this project's Postgres server is ever managed across
          multiple regions or needs explicit HA zone control, this
          `ignore_changes` entry is exactly what would need to come
          back out.

---

## D-0039 — Docker builds pinned to linux/amd64 for Apple Silicon → Azure deploys

Date: 2026-08-26 · Session 8 (post-hoc, found via a real failed Container App deployment) · Status: fixed

Context:  The manually-built and pushed image failed to deploy with
          `no child with platform linux/amd64 in index`. Aaron is on
          an Apple Silicon Mac (arm64). `docker build` with no
          `--platform` flag builds for the host's own architecture by
          default -- the pushed image only contained an arm64 layer,
          and Azure Container Apps' infrastructure is amd64-only, so
          there was nothing for it to pull and run.
Decision: Added `--platform linux/amd64` to the `docker build` call in
          `scripts/manual-deploy.sh`, and pinned `--platform=linux/amd64`
          on both `FROM` lines in the Dockerfile itself, so the
          correct target platform holds regardless of which command
          actually triggers the build.
Why:      This is a genuinely common cross-platform gotcha (build on
          Apple Silicon, deploy to x86 cloud), not something specific
          to a misconfiguration -- worth fixing at both the script
          and the Dockerfile level since either could be the actual
          entry point for a future build (a GitHub Actions runner,
          for instance, already builds on amd64 hardware by default
          and wouldn't have hit this at all, but a human running
          `docker build .` directly on this Mac, without the script,
          would hit it again if only the script were fixed).
Rejected: Fixing only the script -- leaves a trap for any future
          direct `docker build` invocation that bypasses the script.
          Fixing only the Dockerfile -- technically sufficient, but
          the script's own flag is cheap, explicit documentation of
          the constraint right where the build actually happens.
Revisit:  Not expected to change unless this project's build pipeline
          moves to amd64-native hardware (e.g. GitHub Actions' default
          runners, once D-0036/D-0037's tenant restriction lifts and
          OIDC deploy is usable), at which point the pin becomes
          unnecessary but remains harmless to keep.
