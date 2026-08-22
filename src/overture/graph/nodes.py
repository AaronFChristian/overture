"""Extraction graph nodes.

One design choice worth calling out: `make_signal_extractor` is a
factory, not four separate functions. Pain, constraint, requirement,
and vocabulary extraction are structurally identical -- call the LLM
with a category-specific prompt, parse the response, locate each
quote's span, build Requirements, drop anything that doesn't locate.
Writing that out four times would mean any future fix (a parsing edge
case, a retry policy) has to be applied in four places and will
eventually only get applied in three. See decisions.md D-0009.
"""

import json
import sys
from collections.abc import Awaitable, Callable

from overture.graph.llm_output import locate_span, parse_signals_response, strip_code_fences
from overture.graph.prompts import SCOPE_CLASSIFICATION_PROMPT
from overture.graph.state import ExtractionState
from overture.providers.base import LLMProvider, Message
from overture.schemas import (
    Requirement as RequirementSchema,
)
from overture.schemas import (
    RequirementCategory,
    ScopeClassification,
    SolutionBrief,
)


async def segment(state: ExtractionState) -> dict[str, list[str]]:
    """Split the transcript into paragraph-sized segments.

    Deliberately simple: blank-line-separated chunks. This exists so
    later sessions can swap in speaker-attribution-aware segmentation
    without touching any downstream node -- everything after this node
    consumes `state["segments"]`, not the raw transcript directly,
    except the extractors, which currently still work off the full
    transcript for maximum context. See flow.md open threads.
    """
    raw = state["transcript"]
    segments = [chunk.strip() for chunk in raw.split("\n\n") if chunk.strip()]
    return {"segments": segments or [raw.strip()]}


def make_signal_extractor(
    category: RequirementCategory, prompt_template: str, provider: LLMProvider
) -> Callable[[ExtractionState], Awaitable[dict[str, list[RequirementSchema]]]]:
    """Build a node function for one extraction category.

    Returns an async function with the LangGraph node signature
    `(state) -> dict`. The four call sites in builder.py each pass a
    different (category, prompt_template) pair and the same provider.
    """

    async def _extract(state: ExtractionState) -> dict[str, list[RequirementSchema]]:
        transcript = state["transcript"]
        session_id = state["session_id"]
        prompt = prompt_template.format(transcript=transcript)

        result = await provider.complete(
            system="You are a precise information-extraction assistant. "
            "Follow the output format exactly.",
            messages=[Message(role="user", content=prompt)],
            max_tokens=2048,
        )

        extracted = parse_signals_response(result.text)

        requirements: list[RequirementSchema] = []
        for signal in extracted:
            span = locate_span(transcript, signal.quoted_text)
            if span is None:
                # The model paraphrased instead of quoting verbatim --
                # dropped, not kept. This is D-0005 enforced in practice.
                continue
            requirements.append(
                RequirementSchema(
                    session_id=session_id,  # type: ignore[arg-type]
                    category=category,
                    scope=ScopeClassification.NEEDS_CLARIFICATION,  # overwritten below
                    text=signal.paraphrase,
                    source_span=span,
                    confidence=signal.confidence,
                )
            )
        return {"signals": requirements}

    return _extract


def make_classify_scope(
    provider: LLMProvider,
) -> Callable[[ExtractionState], Awaitable[dict[str, list[RequirementSchema]]]]:
    """Build the scope-classification node.

    Batches all extracted signals into a single call rather than one
    call per requirement -- a transcript producing 30 requirements
    would otherwise mean 30 round trips. The response is matched back
    to requirements strictly by index; if the model returns the wrong
    number of labels, every requirement falls back to
    NEEDS_CLARIFICATION rather than risk a silent off-by-one
    misalignment between label and requirement.
    """

    async def _classify(state: ExtractionState) -> dict[str, list[RequirementSchema]]:
        signals = state.get("signals", [])
        if not signals:
            return {"scope_classified": []}

        items_text = "\n".join(f"{i}. {req.text}" for i, req in enumerate(signals))
        prompt = SCOPE_CLASSIFICATION_PROMPT.format(count=len(signals), items=items_text)

        result = await provider.complete(
            system="You are a careful, conservative scoping assistant.",
            messages=[Message(role="user", content=prompt)],
            # 39 short labels needs very few tokens, but this is sized
            # generously (not the original 1024) specifically so any
            # stray explanation text the model adds despite
            # instructions doesn't truncate the JSON array mid-response
            # -- a truncated array is a JSONDecodeError, which looks
            # identical to a fenced response until you print the raw
            # text (see the diagnostic logging below, added after this
            # exact failure mode was hit on a real 39-item batch).
            max_tokens=4096,
        )

        labels: list[str] | None = None
        try:
            parsed = json.loads(strip_code_fences(result.text))
            if isinstance(parsed, list) and len(parsed) == len(signals):
                labels = parsed
            else:
                got = len(parsed) if isinstance(parsed, list) else type(parsed).__name__
                print(
                    f"[overture] scope classification: parsed JSON but got {got} "
                    f"items, expected {len(signals)} -- falling back to "
                    "needs_clarification for all items in this batch.\n"
                    f"Raw response was:\n{result.text}",
                    file=sys.stderr,
                )
        except json.JSONDecodeError as exc:
            print(
                f"[overture] scope classification: failed to parse JSON ({exc}) "
                "-- falling back to needs_clarification for all items in this "
                f"batch.\nRaw response was:\n{result.text}",
                file=sys.stderr,
            )
            labels = None

        classified: list[RequirementSchema] = []
        for i, req in enumerate(signals):
            if labels is not None:
                try:
                    scope = ScopeClassification(labels[i])
                except ValueError:
                    scope = ScopeClassification.NEEDS_CLARIFICATION
            else:
                scope = ScopeClassification.NEEDS_CLARIFICATION
            classified.append(req.model_copy(update={"scope": scope}))

        return {"scope_classified": classified}

    return _classify


async def assemble_brief(state: ExtractionState) -> dict[str, SolutionBrief]:
    """Assemble the final SolutionBrief.

    No LLM call here, on purpose. This is the same "AI proposes,
    deterministic code writes" pattern used throughout the project
    (see decisions.md D-0009): the requirements were already produced
    by the extraction nodes above; assembling them into a brief with a
    counted summary is pure aggregation and doesn't need -- or
    benefit from -- another model call.
    """
    requirements = state.get("scope_classified", [])
    session_id = state["session_id"]

    counts: dict[str, int] = {}
    for req in requirements:
        counts[req.category.value] = counts.get(req.category.value, 0) + 1

    in_scope = sum(1 for r in requirements if r.scope == ScopeClassification.IN_SCOPE)
    out_of_scope = sum(1 for r in requirements if r.scope == ScopeClassification.OUT_OF_SCOPE)
    needs_clarification = sum(
        1 for r in requirements if r.scope == ScopeClassification.NEEDS_CLARIFICATION
    )

    summary_parts = [f"{count} {category}" for category, count in sorted(counts.items())]
    summary = (
        f"Extracted {len(requirements)} items ({', '.join(summary_parts) or 'none'}). "
        f"Scope: {in_scope} in scope, {out_of_scope} out of scope, "
        f"{needs_clarification} need clarification."
    )

    brief = SolutionBrief(
        session_id=session_id,  # type: ignore[arg-type]
        summary=summary,
        requirements=requirements,
    )
    return {"brief": brief}
