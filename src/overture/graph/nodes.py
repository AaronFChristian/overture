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
from overture.text_utils import split_paragraphs


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
    return {"segments": split_paragraphs(raw)}


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


_SCOPE_BATCH_SIZE = 10


def make_classify_scope(
    provider: LLMProvider,
) -> Callable[[ExtractionState], Awaitable[dict[str, list[RequirementSchema]]]]:
    """Build the scope-classification node.

    Splits signals into batches of _SCOPE_BATCH_SIZE rather than one
    call for the whole set. This replaced an earlier single-batch
    design after real evidence (D-0024) that a 33-35 item batch
    reliably drove the model into runaway internal reasoning that
    consumed the entire token budget twice in a row, at two different
    ceilings (4096 and 8192), with zero output either time -- simply
    raising max_tokens a third time was not going to resolve a pattern
    that scaled with whatever ceiling was given. Smaller batches give
    the model a simpler task per call and, as a second benefit, isolate
    failures: if one batch of 10 fails to parse, only those 10 items
    fall back to NEEDS_CLARIFICATION, not the whole transcript's worth.
    """

    async def _classify(state: ExtractionState) -> dict[str, list[RequirementSchema]]:
        signals = state.get("signals", [])
        if not signals:
            return {"scope_classified": []}

        classified: list[RequirementSchema] = []
        for batch_start in range(0, len(signals), _SCOPE_BATCH_SIZE):
            batch = signals[batch_start : batch_start + _SCOPE_BATCH_SIZE]
            classified.extend(await _classify_batch(batch, batch_start, provider))

        return {"scope_classified": classified}

    return _classify


async def _classify_batch(
    batch: list[RequirementSchema], batch_start: int, provider: LLMProvider
) -> list[RequirementSchema]:
    items_text = "\n".join(f"{i}. {req.text}" for i, req in enumerate(batch))
    prompt = SCOPE_CLASSIFICATION_PROMPT.format(count=len(batch), items=items_text)

    result = await provider.complete(
        system="You are a careful, conservative scoping assistant.",
        messages=[Message(role="user", content=prompt)],
        # 2048 is generous for a 10-item batch's JSON array alone
        # (which needs perhaps 100 tokens); the real defense against
        # runaway reasoning is the smaller batch size (D-0024), not a
        # larger ceiling -- see the module docstring above.
        max_tokens=2048,
    )

    labels: list[str] | None = None
    try:
        parsed = json.loads(strip_code_fences(result.text))
        if isinstance(parsed, list) and len(parsed) == len(batch):
            labels = parsed
        else:
            got = len(parsed) if isinstance(parsed, list) else type(parsed).__name__
            print(
                f"[overture] scope classification (items {batch_start}-"
                f"{batch_start + len(batch) - 1}): parsed JSON but got {got} "
                f"items, expected {len(batch)} -- falling back to "
                "needs_clarification for this batch only.\n"
                f"Raw response was:\n{result.text}",
                file=sys.stderr,
            )
    except json.JSONDecodeError as exc:
        print(
            f"[overture] scope classification (items {batch_start}-"
            f"{batch_start + len(batch) - 1}): failed to parse JSON ({exc}) "
            "-- falling back to needs_clarification for this batch only.\n"
            f"Model reported output_tokens={result.output_tokens}, "
            f"input_tokens={result.input_tokens}, "
            f"stop_reason={result.stop_reason!r}, "
            f"content_block_types={result.content_block_types}.\n"
            f"Raw response text was: {result.text!r}",
            file=sys.stderr,
        )
        labels = None

    classified: list[RequirementSchema] = []
    for i, req in enumerate(batch):
        if labels is not None:
            try:
                scope = ScopeClassification(labels[i])
            except ValueError:
                scope = ScopeClassification.NEEDS_CLARIFICATION
        else:
            scope = ScopeClassification.NEEDS_CLARIFICATION
        classified.append(req.model_copy(update={"scope": scope}))

    return classified


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
