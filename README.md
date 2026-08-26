# Overture

**Turns a sales discovery-call transcript into a working, cited, grounded demo — in minutes, not days.**

A Solution Engineer runs 5–25 hours a week hand-building demos that speak a prospect's specific language. Overture reads the transcript, extracts what the prospect actually needs (with every claim traceable back to an exact quote), picks the right demo shape, and stands up a live Q&A demo grounded in the prospect's own vocabulary — one that explicitly refuses to answer questions the source material can't actually support.

Built as a portfolio project targeting Solution Engineer / Forward-Deployed Engineer roles. Every architectural decision, every bug found along the way, and the reasoning behind each is logged in [`decisions.md`](decisions.md) — over 45 entries, most of them written the moment a real bug was found and fixed, not after the fact.

## What it actually does

1. **Extract** — a LangGraph pipeline reads a transcript and pulls out pains, constraints, explicit requirements, and vocabulary, running four extraction passes in parallel. Every single item must carry an exact quote pointing back into the source transcript — an item the model can't ground in a real quote is dropped, not kept.
2. **Classify** — each item gets scored in-scope / out-of-scope / needs-clarification, batched for cost, with a strict fallback that never silently misaligns a label to the wrong item.
3. **Compile** — a deterministic scorer (no LLM) picks one of three fixed demo blueprints based on the in-scope language; the LLM only fills in wording, never picks the blueprint or the tools.
4. **Validate** — a config validator with zero LLM calls anywhere in the module (proven by a test that greps its own source) is the only code allowed to mark a demo deployable.
5. **Ingest & retrieve** — the transcript is chunked and embedded (a hand-rolled, zero-cost hashing embedder — deliberately not a third paid API), stored in Postgres via pgvector, retrieved by real cosine similarity.
6. **Demo** — a grounded Q&A runtime answers strictly from retrieved chunks, cites them by position, and says "I don't know" rather than fabricating an answer the source material doesn't support.

The whole thing runs locally for $0, and deploys to Azure (Terraform + Container Apps, OIDC-based CI/CD where the tenant allows it) for a few dollars a month.

## Stack

**Backend:** Python 3.12, FastAPI, Pydantic v2, `uv`, LangGraph, SQLAlchemy + `asyncpg`, Alembic, pgvector, Anthropic SDK (Azure OpenAI as a swappable second backend behind one interface).

**Frontend:** React + TypeScript + Vite, no CSS framework.

**Infrastructure:** Terraform, Azure Container Apps, Postgres Flexible Server, Key Vault, Application Insights, GitHub Container Registry, Docker.

## Try it

```bash
uv sync --all-extras
make up                                    # Postgres + pgvector, local, free
uv run alembic upgrade head
uv run overture extract data/sample_transcripts/manufacturing_vendor_contracts.txt
```

That prints a demo link token. Ask it something:

```bash
uv run overture ask "<the token>" "How long does contract review take?"
```

Or run the full stack with a real browser:

```bash
# terminal 1
uv run uvicorn overture.main:app --reload
# terminal 2
cd frontend && npm install && npm run dev
```

Then open `http://localhost:5173/console`, paste a transcript, and click through to the generated demo.

## Verify everything

```bash
make verify              # backend: ruff + mypy strict + pytest
cd frontend && npm run lint && npm run build   # frontend
```

## The two logs that tell the real story

- **[`decisions.md`](decisions.md)** — every meaningful architectural choice, why it was made, what was rejected and why. Includes real bugs found on live runs: a hallucinated company name traced to a one-line grounding gap, a scope-classification failure diagnosed through batching and later through raw model response inspection, a subscription-policy region restriction discovered mid-`apply`, a genuinely flaky test rooted in base64 encoding and proven with a 200-run loop.
- **[`flow.md`](flow.md)** — how the code actually executes, entry point to entry point, and an honest per-session ledger of what the AI wrote versus what it deliberately didn't decide, plus what was verified by real execution versus reviewed but never run.

## Project layout

```
src/overture/
  config.py          typed settings, single source of config truth
  main.py             FastAPI app construction
  cli.py               overture extract / overture ask
  api/                 HTTP routes: /health, /api/v1/demo, /api/v1/sessions
  graph/                LangGraph extraction pipeline
  poc/                  blueprints, compiler, validator, retrieval, runtime, tokens
  db/                   SQLAlchemy models, repository, migrations support
  providers/            Claude / Azure OpenAI, swappable behind one interface
frontend/
  src/pages/DemoPage.tsx      prospect-facing demo
  src/pages/ConsolePage.tsx   SE console — paste a transcript, generate a demo
terraform/            Azure landing zone: Postgres, Key Vault, Container Apps
tests/                mirrors src/ structure, 75+ tests
decisions.md           why things are the way they are
flow.md                 how the code actually executes
```
