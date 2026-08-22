"""What the extraction LLM is allowed to hand back, and how a raw
quote becomes an enforceable SourceSpan.

This module is the actual enforcement point for decisions.md D-0005.
The Requirement schema makes source_span required at the type level;
this module is what stands between "the LLM said something" and "a
Requirement got constructed" -- if the model's quoted_text isn't a
real substring of the transcript, no Requirement is built, full stop.
"""

import json
import re

from pydantic import BaseModel, Field

from overture.schemas import SourceSpan


class ExtractedSignal(BaseModel):
    """One item as the LLM returns it -- not yet a Requirement.

    Missing session_id, category, and scope on purpose: those are
    filled in by the calling node, which knows which extraction pass
    produced this item. The model's only job is quoted_text (verbatim,
    for span-location) and paraphrase (what actually gets stored as
    Requirement.text).
    """

    quoted_text: str = Field(min_length=1)
    paraphrase: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)


_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def strip_code_fences(raw_text: str) -> str:
    """Remove a leading/trailing ```json (or bare ```) fence, if present.

    Shared by parse_signals_response below and by classify_scope in
    nodes.py -- both parse a raw model completion as JSON, and both
    need this. Originally only the former had it; the latter's
    omission is exactly what caused a real 39-item scope-classification
    batch to fail to parse against live Claude output (the model
    fenced its response, json.loads on the raw text threw, and the
    conservative fallback silently marked every item
    needs_clarification). See decisions.md D-0014.
    """
    return _CODE_FENCE.sub("", raw_text.strip()).strip()


def parse_signals_response(raw_text: str) -> list[ExtractedSignal]:
    """Parse the model's raw completion into a list of ExtractedSignal.

    Deliberately lenient about the outer wrapping (models like to add
    ```json fences even when told not to) but strict about item shape:
    an item that doesn't validate against ExtractedSignal is dropped,
    not coerced. A malformed item is exactly the kind of thing that
    should not survive into a Requirement.
    """
    cleaned = strip_code_fences(raw_text)
    try:
        raw_items = json.loads(cleaned)
    except json.JSONDecodeError:
        return []

    if not isinstance(raw_items, list):
        return []

    signals: list[ExtractedSignal] = []
    for item in raw_items:
        try:
            signals.append(ExtractedSignal.model_validate(item))
        except Exception:  # noqa: BLE001 -- one bad item must not sink the batch
            continue
    return signals


def locate_span(transcript: str, quoted_text: str) -> SourceSpan | None:
    """Find `quoted_text` verbatim in `transcript` and return its span.

    Returns None -- never a best-guess or fuzzy match -- if the model
    paraphrased instead of quoting exactly. The caller (nodes.py) is
    responsible for dropping the signal when this returns None; this
    function's job is only to refuse to fabricate a span, not to
    decide what happens next.
    """
    needle = quoted_text.strip()
    if not needle:
        return None
    start = transcript.find(needle)
    if start == -1:
        return None
    end = start + len(needle)
    return SourceSpan(start=start, end=end, quoted_text=needle)
