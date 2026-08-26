# Publishing to Copilot Studio (conceptual path, not implemented)

This document is intentionally short and honest: **this integration
has not been built or tested**, unlike everything else in this
project. Session 10 ran out of scope to actually implement and verify
it, and Anthropic's sandbox this project was built in has no way to
reach Copilot Studio's environment to test against regardless.

## The real path, if this gets picked up later

Copilot Studio can call an external API via a **custom connector**
(an OpenAPI-described HTTP action a Copilot topic can invoke). The
existing `POST /api/v1/demo/{token}/ask` route is already a plausible
target for this with zero changes:

1. Generate an OpenAPI schema for that one route (FastAPI does this
   automatically at `/openapi.json` — filtering it down to just this
   route is the actual work).
2. Import that schema as a custom connector in Copilot Studio.
3. Build a Copilot Studio topic that collects a question, calls the
   connector with a fixed demo token, and surfaces the `answer` and
   `citations` fields back to the user.

## Why this wasn't built now

- No Microsoft 365 / Copilot Studio tenant access from this
  environment to actually create and test a connector or a topic.
- The existing `/ask` route already returns exactly the shape a
  connector action would need (`answer`, `citations`) — the backend
  work is arguably already done; what's missing is the Copilot
  Studio-side configuration, which has no code representation to
  write and verify the way everything else in this project does.

## What this project can still demonstrate honestly

The architecture supports this path without modification. That's a
legitimate thing to say in an interview — "the API is already shaped
for this, I didn't build the Copilot Studio side because I couldn't
verify it without tenant access I don't have" is a more credible
answer than claiming a working integration that was never actually
tested.
