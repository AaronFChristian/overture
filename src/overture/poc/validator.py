"""Deterministic config validator.

This is the single most important architectural claim in the whole
project: NO LLM call happens anywhere in this module. `validate_config`
is the only function in the codebase with authority to set a
DemoConfig's status to VALIDATED. Everything upstream (extraction,
scope classification, blueprint selection, slot filling) can be wrong
in ways an LLM call can be wrong; this module cannot, because it
doesn't call one. See decisions.md D-0018.
"""

from overture.poc.blueprints import ALL_BLUEPRINTS
from overture.schemas import DemoConfig, DemoConfigStatus

_KNOWN_BLUEPRINT_IDS = frozenset(bp.id for bp in ALL_BLUEPRINTS)

# Every tool any blueprint is allowed to attach. A blueprint's
# default_tools should always be a subset of this -- if a future
# blueprint definition adds a tool here that isn't allowlisted, this
# validator is what catches it, not a code review.
TOOL_ALLOWLIST = frozenset(
    {"document_search", "citation_lookup", "classifier", "review_queue", "field_extractor"}
)

MAX_TOKEN_BUDGET = 200_000
MIN_SAMPLE_QUESTIONS = 1


def validate_config(config: DemoConfig) -> DemoConfig:
    """Validate a DemoConfig and return a new one with status set accordingly.

    Never mutates the input (Pydantic models here are treated as
    immutable data) -- returns a copy via model_copy with status and
    validation_errors updated. On any failure, status becomes
    REJECTED and every failure reason is recorded, not just the
    first one, so a caller sees the whole picture in one pass rather
    than fixing issues one at a time across repeated runs.
    """
    errors: list[str] = []

    if config.blueprint_id not in _KNOWN_BLUEPRINT_IDS:
        errors.append(f"unknown blueprint_id: {config.blueprint_id!r}")

    unknown_tools = [tool for tool in config.tools if tool not in TOOL_ALLOWLIST]
    if unknown_tools:
        errors.append(f"tools not in allowlist: {unknown_tools}")

    if not (0 < config.token_budget <= MAX_TOKEN_BUDGET):
        errors.append(
            f"token_budget {config.token_budget} outside allowed range (0, {MAX_TOKEN_BUDGET}]"
        )

    if not config.system_prompt.strip():
        errors.append("system_prompt is empty")

    if len(config.sample_questions) < MIN_SAMPLE_QUESTIONS:
        errors.append(
            f"fewer than {MIN_SAMPLE_QUESTIONS} sample question(s) "
            f"(got {len(config.sample_questions)})"
        )

    if errors:
        return config.model_copy(
            update={"status": DemoConfigStatus.REJECTED, "validation_errors": errors}
        )

    return config.model_copy(
        update={"status": DemoConfigStatus.VALIDATED, "validation_errors": []}
    )
