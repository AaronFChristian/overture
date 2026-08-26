import json
import re
import uuid

import pytest

from overture.graph.nodes import make_classify_scope
from overture.providers.base import CompletionResult, Message
from overture.schemas import Requirement, RequirementCategory, ScopeClassification, SourceSpan


def _make_requirements(n: int) -> list[Requirement]:
    return [
        Requirement(
            session_id=uuid.uuid4(),
            category=RequirementCategory.REQUIREMENT,
            scope=ScopeClassification.NEEDS_CLARIFICATION,
            text=f"requirement number {i}",
            source_span=SourceSpan(start=0, end=10, quoted_text=f"req{i:03d}xx"),
        )
        for i in range(n)
    ]


class BatchAwareFakeProvider:
    """Tracks which call number it's on and can be told to fail one
    specific call, to prove batches are handled independently."""

    def __init__(self, fail_on_call_index: int | None = None) -> None:
        self.calls: list[str] = []
        self._fail_on_call_index = fail_on_call_index

    async def complete(
        self, *, system: str, messages: list[Message], max_tokens: int = 1024
    ) -> CompletionResult:
        prompt = messages[0].content
        call_index = len(self.calls)
        self.calls.append(prompt)

        match = re.search(r"exactly (\d+) elements", prompt)
        n = int(match.group(1)) if match else 0

        if self._fail_on_call_index is not None and call_index == self._fail_on_call_index:
            text = "this is not valid json at all"
        else:
            text = json.dumps(["in_scope"] * n)

        return CompletionResult(text=text, input_tokens=10, output_tokens=10, model="fake")


@pytest.mark.asyncio
async def test_large_signal_set_is_split_into_batches_of_ten() -> None:
    requirements = _make_requirements(25)
    provider = BatchAwareFakeProvider()
    classify = make_classify_scope(provider)

    result = await classify({"signals": requirements})  # type: ignore[typeddict-item]

    # 25 items at batch size 10 -> 3 calls (10, 10, 5), not 1
    assert len(provider.calls) == 3
    assert len(result["scope_classified"]) == 25


@pytest.mark.asyncio
async def test_a_failing_batch_does_not_affect_other_batches() -> None:
    requirements = _make_requirements(25)
    # Batch 1 (items 10-19, the second call, index 1) fails to parse;
    # batches 0 and 2 succeed.
    provider = BatchAwareFakeProvider(fail_on_call_index=1)
    classify = make_classify_scope(provider)

    result = await classify({"signals": requirements})  # type: ignore[typeddict-item]
    classified = result["scope_classified"]

    assert len(classified) == 25
    # Items 0-9 (batch 0) and 20-24 (batch 2) succeeded -> in_scope
    for item in classified[0:10]:
        assert item.scope == ScopeClassification.IN_SCOPE
    for item in classified[20:25]:
        assert item.scope == ScopeClassification.IN_SCOPE
    # Items 10-19 (batch 1) failed to parse -> needs_clarification,
    # and ONLY those items -- this is the fault-isolation guarantee
    # that motivated D-0024 in the first place.
    for item in classified[10:20]:
        assert item.scope == ScopeClassification.NEEDS_CLARIFICATION


@pytest.mark.asyncio
async def test_small_signal_set_uses_a_single_batch() -> None:
    requirements = _make_requirements(3)
    provider = BatchAwareFakeProvider()
    classify = make_classify_scope(provider)

    await classify({"signals": requirements})  # type: ignore[typeddict-item]

    assert len(provider.calls) == 1
