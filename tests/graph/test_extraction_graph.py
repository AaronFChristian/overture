import json
import re
import uuid

import pytest

from overture.graph.builder import build_graph
from overture.providers.base import CompletionResult, Message

TRANSCRIPT = (
    "We're a mid-size manufacturer.\n\n"
    "Legal review takes three weeks for every vendor contract.\n\n"
    "We are an M365 shop, so it needs to work with SharePoint.\n\n"
    "Can it also search across our German subsidiary's contracts?"
)


class FakeProvider:
    """Stands in for a real LLMProvider in tests.

    Branches on distinctive phrases from each prompt template rather
    than tracking call order, so tests don't depend on the (not
    guaranteed) order in which parallel extraction nodes complete.
    """

    def __init__(self, mismatched_scope: bool = False) -> None:
        self.calls: list[str] = []
        self._mismatched_scope = mismatched_scope

    async def complete(
        self, *, system: str, messages: list[Message], max_tokens: int = 1024
    ) -> CompletionResult:
        prompt = messages[0].content
        self.calls.append(prompt)

        if "business pains" in prompt:
            text = json.dumps(
                [
                    {
                        "quoted_text": "Legal review takes three weeks for every vendor contract.",
                        "paraphrase": "Legal review is slow",
                        "confidence": 0.9,
                    }
                ]
            )
        elif "extracting constraints" in prompt:
            text = json.dumps(
                [
                    {
                        "quoted_text": "We are an M365 shop, so it needs to work with SharePoint.",
                        "paraphrase": "Must integrate with SharePoint/M365",
                        "confidence": 0.95,
                    },
                    {
                        # Not a real substring of the transcript -- this
                        # is the case that must get dropped, not kept.
                        "quoted_text": "this text does not appear anywhere in the transcript",
                        "paraphrase": "should be dropped",
                        "confidence": 0.5,
                    },
                ]
            )
        elif "explicit requirements" in prompt:
            text = "[]"
        elif "domain vocabulary" in prompt:
            text = json.dumps(
                [
                    {
                        "quoted_text": "SharePoint",
                        "paraphrase": "SharePoint (M365 document platform)",
                        "confidence": 0.8,
                    }
                ]
            )
        elif "scoping a list" in prompt:
            match = re.search(r"exactly (\d+) elements", prompt)
            n = int(match.group(1)) if match else 0
            count = max(n - 1, 0) if self._mismatched_scope else n
            text = json.dumps(["in_scope"] * count)
        else:
            text = "[]"

        return CompletionResult(text=text, input_tokens=10, output_tokens=10, model="fake")


@pytest.mark.asyncio
async def test_extraction_graph_end_to_end() -> None:
    provider = FakeProvider()
    graph = build_graph(provider)
    session_id = str(uuid.uuid4())

    result = await graph.ainvoke({"session_id": session_id, "transcript": TRANSCRIPT})
    brief = result["brief"]

    assert brief is not None
    # 1 pain + 1 valid constraint (1 dropped for a bad quote) + 0 requirements + 1 vocabulary
    assert len(brief.requirements) == 3
    for req in brief.requirements:
        assert req.scope.value == "in_scope"
        # every surviving requirement's span is a real substring of the transcript --
        # this is D-0005 proven, not just asserted
        assert req.source_span.quoted_text in TRANSCRIPT
        start, end = req.source_span.start, req.source_span.end
        assert TRANSCRIPT[start:end] == req.source_span.quoted_text


@pytest.mark.asyncio
async def test_invalid_quote_is_dropped_not_kept() -> None:
    provider = FakeProvider()
    graph = build_graph(provider)
    session_id = str(uuid.uuid4())

    result = await graph.ainvoke({"session_id": session_id, "transcript": TRANSCRIPT})
    texts = [r.text for r in result["brief"].requirements]

    assert "should be dropped" not in texts


@pytest.mark.asyncio
async def test_scope_mismatch_falls_back_to_needs_clarification() -> None:
    provider = FakeProvider(mismatched_scope=True)
    graph = build_graph(provider)
    session_id = str(uuid.uuid4())

    result = await graph.ainvoke({"session_id": session_id, "transcript": TRANSCRIPT})
    brief = result["brief"]

    assert len(brief.requirements) == 3
    assert all(r.scope.value == "needs_clarification" for r in brief.requirements)


@pytest.mark.asyncio
async def test_summary_reports_correct_counts() -> None:
    provider = FakeProvider()
    graph = build_graph(provider)
    session_id = str(uuid.uuid4())

    result = await graph.ainvoke({"session_id": session_id, "transcript": TRANSCRIPT})
    summary = result["brief"].summary

    assert "3 in scope" in summary
    assert "0 out of scope" in summary
