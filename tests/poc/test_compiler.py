import json
import uuid

import pytest

from overture.poc.blueprints import GROUNDED_DOCUMENT_QA
from overture.poc.compiler import fill_config
from overture.providers.base import CompletionResult, Message
from overture.schemas import (
    DemoConfigStatus,
    Requirement,
    RequirementCategory,
    ScopeClassification,
    SolutionBrief,
    SourceSpan,
)


class FakeSlotFillProvider:
    def __init__(self, raw_response: str) -> None:
        self._raw_response = raw_response
        self.last_prompt: str | None = None

    async def complete(
        self, *, system: str, messages: list[Message], max_tokens: int = 1024
    ) -> CompletionResult:
        self.last_prompt = messages[0].content
        return CompletionResult(
            text=self._raw_response, input_tokens=10, output_tokens=10, model="fake"
        )


def _req(text: str, category: RequirementCategory) -> Requirement:
    return Requirement(
        session_id=uuid.uuid4(),
        category=category,
        scope=ScopeClassification.IN_SCOPE,
        text=text,
        source_span=SourceSpan(start=0, end=len(text), quoted_text=text),
    )


@pytest.mark.asyncio
async def test_fill_config_populates_from_valid_llm_response() -> None:
    brief = SolutionBrief(
        session_id=uuid.uuid4(),
        requirements=[
            _req("Query contracts expiring soon", RequirementCategory.REQUIREMENT),
            _req("SharePoint", RequirementCategory.VOCABULARY),
        ],
    )
    response = json.dumps(
        {
            "system_prompt": "You help procurement find contract terms in SharePoint.",
            "sample_questions": ["Which contracts expire this quarter?"],
        }
    )
    provider = FakeSlotFillProvider(response)

    config = await fill_config(brief, GROUNDED_DOCUMENT_QA, provider)

    assert config.blueprint_id == "grounded_document_qa"
    assert config.status == DemoConfigStatus.DRAFT  # not validated -- that's a separate step
    assert config.system_prompt == "You help procurement find contract terms in SharePoint."
    assert config.sample_questions == ["Which contracts expire this quarter?"]
    assert list(config.tools) == list(GROUNDED_DOCUMENT_QA.default_tools)


@pytest.mark.asyncio
async def test_fill_config_handles_fenced_response() -> None:
    brief = SolutionBrief(session_id=uuid.uuid4(), requirements=[])
    fenced = "```json\n" + json.dumps({"system_prompt": "Hi", "sample_questions": ["Q1"]}) + "\n```"
    provider = FakeSlotFillProvider(fenced)

    config = await fill_config(brief, GROUNDED_DOCUMENT_QA, provider)

    assert config.system_prompt == "Hi"
    assert config.sample_questions == ["Q1"]


@pytest.mark.asyncio
async def test_fill_config_degrades_gracefully_on_unparseable_response() -> None:
    # Not this function's job to fail loudly -- an empty system_prompt
    # and empty sample_questions is exactly what the validator (tested
    # separately) is built to catch and reject.
    brief = SolutionBrief(session_id=uuid.uuid4(), requirements=[])
    provider = FakeSlotFillProvider("this is not json at all")

    config = await fill_config(brief, GROUNDED_DOCUMENT_QA, provider)

    assert config.system_prompt == ""
    assert config.sample_questions == []
    assert config.status == DemoConfigStatus.DRAFT


@pytest.mark.asyncio
async def test_fill_config_truncates_excess_sample_questions_to_blueprint_count() -> None:
    brief = SolutionBrief(session_id=uuid.uuid4(), requirements=[])
    response = json.dumps(
        {
            "system_prompt": "Hi",
            "sample_questions": [f"Q{i}" for i in range(20)],  # way more than requested
        }
    )
    provider = FakeSlotFillProvider(response)

    config = await fill_config(brief, GROUNDED_DOCUMENT_QA, provider)

    assert len(config.sample_questions) == GROUNDED_DOCUMENT_QA.sample_question_count


@pytest.mark.asyncio
async def test_fill_config_grounds_vocabulary_with_actual_quoted_terms() -> None:
    # Regression test for a real hallucination found via live-API testing
    # (D-0019): fill_config originally sent only the paraphrased label
    # ("Company name") for vocabulary items, never the actual term
    # ("Meridian Fabrication Group") -- the model, handed a label with
    # nothing after it, invented a plausible-sounding company name that
    # never appeared anywhere in the source transcript.
    company_name_req = Requirement(
        session_id=uuid.uuid4(),
        category=RequirementCategory.VOCABULARY,
        scope=ScopeClassification.IN_SCOPE,
        text="Company name",  # the paraphrased label -- deliberately vague
        source_span=SourceSpan(start=0, end=25, quoted_text="Meridian Fabrication Group"),
    )
    brief = SolutionBrief(session_id=uuid.uuid4(), requirements=[company_name_req])
    provider = FakeSlotFillProvider(json.dumps({"system_prompt": "Hi", "sample_questions": ["Q1"]}))

    await fill_config(brief, GROUNDED_DOCUMENT_QA, provider)

    assert provider.last_prompt is not None
    assert "Meridian Fabrication Group" in provider.last_prompt
