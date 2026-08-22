# Overture

Discovery-transcript to deployable tailored POC generator.

See `decisions.md` for why things are built the way they are, and
`flow.md` for how the code actually executes.

## Setup (macOS)

```bash
# from inside the overture/ directory
uv sync --all-extras
```

## Run the database

```bash
make up      # starts Postgres+pgvector, waits for healthy
make down    # stops it
```

## Run the app

```bash
uv run uvicorn overture.main:app --reload
```

Then in another terminal:

```bash
curl http://localhost:8000/health
```

## Verify everything

```bash
make verify    # lint + typecheck + test, in that order
```

## Project layout

```
src/overture/
  config.py       typed settings, single source of config truth
  main.py          FastAPI app construction
  api/health.py    health check route
tests/             mirrors src/ structure
decisions.md        why things are the way they are
flow.md             how the code actually executes
```
